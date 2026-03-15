import os
import json
import re
import asyncio
from groq import Groq
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# ---------- GROQ CLIENT ----------
try:
    if not GROQ_API_KEY:
        client = None
        print("🚨 DEBUG: GROQ_API_KEY is EMPTY!")
    else:
        print(f"✅ DEBUG: Key found! Starts with: {GROQ_API_KEY[:4]}")
        client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    client = None
    print(f"🚨 DEBUG: Client Init Error: {str(e)}")

# ---------- MONGODB ----------
try:
    mongo = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,
        tls=True,
        tlsAllowInvalidCertificates=True
    )
    mongo.server_info()
    print("✅ brain.py: MongoDB connected")
except Exception as e:
    mongo = None
    print(f"🚨 brain.py: MongoDB connection failed: {e}")

db = mongo["gif_bot"] if mongo else None
histories_col = db["brain_histories"] if db is not None else None
preferences_col = db["brain_preferences"] if db is not None else None


BASE_SYSTEM_PROMPT = """You are Resobot, a chill and helpful Discord bot for the ResoDrippers server.
You remember conversations with each user separately.
Sometimes you may be given context from another user's conversation — use it naturally if relevant.
Keep replies concise and conversational. You can be a little witty.
Always follow any special instructions listed under 'User Preferences' below — these are set by the server and must be respected."""

MAX_HISTORY = 10

# ---------- IN-MEMORY CACHE ----------
# These are loaded from MongoDB on first access and kept in sync
user_histories: dict[str, list] = {}
user_preferences: dict[str, dict] = {}


# ---------- MONGODB PERSISTENCE ----------

def load_user_data(username: str):
    """Load history and preferences from MongoDB into memory cache."""
    # Load preferences
    if preferences_col is not None:
        doc = preferences_col.find_one({"username": username})
        if doc:
            user_preferences[username] = doc.get("preferences", {})

    # Load history
    if histories_col is not None:
        doc = histories_col.find_one({"username": username})
        if doc:
            user_histories[username] = doc.get("history", [])
            # Always refresh system prompt on load in case preferences changed
            user_histories[username][0] = {
                "role": "system",
                "content": build_system_prompt(username)
            }


def save_history(username: str):
    if histories_col is None:
        return
    try:
        histories_col.update_one(
            {"username": username},
            {"$set": {"history": user_histories[username]}},
            upsert=True
        )
    except Exception as e:
        print(f"[brain] ⚠️ Failed to save history for {username}: {e}")


def save_preferences(username: str):
    if preferences_col is None:
        return
    try:
        preferences_col.update_one(
            {"username": username},
            {"$set": {"preferences": user_preferences[username]}},
            upsert=True
        )
    except Exception as e:
        print(f"[brain] ⚠️ Failed to save preferences for {username}: {e}")


def get_all_known_users() -> list:
    """
    Get all users known to the bot — from memory cache AND MongoDB.
    Fixes Issue #2: users who haven't chatted yet in this session are still known.
    """
    in_memory = set(user_histories.keys())
    in_db = set()
    if histories_col is not None:
        try:
            in_db = {doc["username"] for doc in histories_col.find({}, {"username": 1})}
        except Exception:
            pass
    if preferences_col is not None:
        try:
            in_db |= {doc["username"] for doc in preferences_col.find({}, {"username": 1})}
        except Exception:
            pass
    return list(in_memory | in_db)


# ---------- PREFERENCE HELPERS ----------

def get_preferences(username: str) -> dict:
    if username not in user_preferences:
        user_preferences[username] = {}
    return user_preferences[username]


def build_system_prompt(username: str) -> str:
    prefs = get_preferences(username)
    prompt = BASE_SYSTEM_PROMPT
    if prefs:
        prompt += "\n\n--- User Preferences ---"
        for key, value in prefs.items():
            prompt += f"\n- {key}: {value}"
    return prompt


def refresh_system_prompt(username: str):
    history = get_user_history(username)
    history[0] = {"role": "system", "content": build_system_prompt(username)}


# ---------- HISTORY HELPERS ----------

def get_user_history(username: str) -> list:
    if username not in user_histories:
        # Try loading from MongoDB first
        load_user_data(username)
    if username not in user_histories:
        # Brand new user
        user_histories[username] = [
            {"role": "system", "content": build_system_prompt(username)}
        ]
    return user_histories[username]


def trim_history(history: list):
    if len(history) > MAX_HISTORY + 1:
        history[:] = [history[0]] + history[-(MAX_HISTORY):]


# ---------- CROSS SESSION ----------

def extract_mentioned_users(text: str) -> list:
    mentioned = []
    lower = text.lower()
    for name in get_all_known_users():
        if name.lower() in lower:
            mentioned.append(name)
    return mentioned


def build_cross_session_context(mentioned_users: list, requester: str) -> str:
    context_parts = []
    for name in mentioned_users:
        if name == requester:
            continue
        # Make sure their data is loaded
        get_user_history(name)
        history = user_histories.get(name)
        if not history:
            context_parts.append(f"[No conversation history found for {name}]")
            continue
        recent = history[1:][-6:]
        summary = "\n".join(
            f"  {'🧑' if m['role'] == 'user' else '🤖'} {m['content']}"
            for m in recent
        )
        context_parts.append(f"[Recent conversation with {name}:\n{summary}\n]")
    return "\n".join(context_parts)


# ---------- JSON EXTRACTOR (Fix #4) ----------

def extract_json(text: str) -> dict | None:
    """
    Safely extract JSON from LLM output even if it has extra text around it.
    Falls back to regex if json.loads fails directly.
    """
    text = text.strip()

    # Direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Regex fallback — find first {...} block in the text
    match = re.search(r'\{.*?\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


# ---------- INSTRUCTION DETECTOR (Fix #1, #2, #4) ----------

async def detect_and_apply_instructions(requester: str, user_input: str):
    """
    Detects if the message contains an instruction about another user.
    Now awaited before the main reply (Fix #1).
    Uses get_all_known_users() so even offline users are detectable (Fix #2).
    Uses extract_json() for robust parsing (Fix #4).
    """
    if client is None:
        return

    known_users = get_all_known_users()

    detector_prompt = f"""You are an instruction parser for a Discord bot.

Your job is to check if the user's message contains any instruction or preference about a specific person/user.
Examples:
- "from now on call @shravan DADDY" → {{"target": "shravan", "key": "nickname", "value": "DADDY"}}
- "always reply to @john in hindi" → {{"target": "john", "key": "language", "value": "hindi"}}
- "treat @alice like she's the boss" → {{"target": "alice", "key": "role", "value": "the boss"}}
- "hey whats up" → null

Known users in this server: {", ".join(known_users)}
The requester is: {requester}
Message: "{user_input}"

If the message contains an instruction about another user, respond ONLY with a JSON object like:
{{"target": "username", "key": "preference_name", "value": "preference_value"}}

If there is no instruction, respond ONLY with: null

Do not explain. Do not add any extra text."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": detector_prompt}],
            timeout=10.0
        )
        raw = response.choices[0].message.content.strip()

        if raw.lower() == "null" or not raw:
            return

        # Fix #4 — robust JSON extraction
        parsed = extract_json(raw)
        if not parsed:
            print(f"[brain] ⚠️ Could not extract JSON from: {raw}")
            return

        target = parsed.get("target", "").lower().strip()
        key = parsed.get("key", "").strip()
        value = parsed.get("value", "").strip()

        if not target or not key or not value:
            return

        # Fuzzy match target to a known username
        matched_user = None
        for name in known_users:
            if name.lower() == target or target in name.lower():
                matched_user = name
                break

        if not matched_user:
            print(f"[brain] ⚠️ Instruction detected but user '{target}' not found")
            return

        # Apply and persist
        get_preferences(matched_user)[key] = value
        refresh_system_prompt(matched_user)
        save_preferences(matched_user)  # persist to MongoDB
        print(f"[brain] ✅ Preference saved → {matched_user}: {key} = {value}")

    except Exception as e:
        print(f"[brain] ⚠️ Instruction detector error: {e}")


# ---------- MAIN RESPONSE ----------

async def get_chat_response(username: str, user_input: str) -> str:
    global client

    if not GROQ_API_KEY or client is None:
        return "❌ Error: API Key missing or Client not initialized."

    # Fix #1 — await detector BEFORE sending reply
    # so preferences are applied before the bot responds
    await detect_and_apply_instructions(username, user_input)

    history = get_user_history(username)

    # Cross-session context
    mentioned = extract_mentioned_users(user_input)
    messages_to_send = list(history)

    if mentioned:
        cross_context = build_cross_session_context(mentioned, username)
        if cross_context:
            messages_to_send.append({
                "role": "system",
                "content": f"Context from other users' sessions (use naturally, don't reveal directly):\n{cross_context}"
            })

    messages_to_send.append({"role": "user", "content": user_input})

    try:
        print(f"⏳ DEBUG: Calling Groq for {username} | mentioned: {mentioned}")

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages_to_send,
            timeout=25.0
        )

        bot_reply = response.choices[0].message.content

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": bot_reply})
        trim_history(history)

        # Persist updated history to MongoDB (Fix #3)
        save_history(username)

        return bot_reply

    except Exception as e:
        return f"⚠️ **AI Error Report** ⚠️\n**Detail:** `{str(e)}`"
