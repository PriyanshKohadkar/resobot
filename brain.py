import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

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


BASE_SYSTEM_PROMPT = """You are Resobot, a chill and helpful Discord bot for the ResoDrippers server.
You remember conversations with each user separately.
Sometimes you may be given context from another user's conversation — use it naturally if relevant.
Keep replies concise and conversational. You can be a little witty.
Always follow any special instructions listed under 'User Preferences' below — these are set by the server and must be respected."""

MAX_HISTORY = 10

# --- STORAGE ---
user_histories: dict[str, list] = {}
user_preferences: dict[str, dict] = {}
# e.g. { "shravan": {"nickname": "DADDY", "language": "hindi"} }


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
    """Rebuild system prompt in history after preferences change."""
    history = get_user_history(username)
    history[0] = {"role": "system", "content": build_system_prompt(username)}


# ---------- HISTORY HELPERS ----------

def get_user_history(username: str) -> list:
    if username not in user_histories:
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
    for name in user_histories.keys():
        if name.lower() in lower:
            mentioned.append(name)
    return mentioned


def build_cross_session_context(mentioned_users: list, requester: str) -> str:
    context_parts = []
    for name in mentioned_users:
        if name == requester:
            continue
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


# ---------- INSTRUCTION DETECTOR ----------

async def detect_and_apply_instructions(requester: str, user_input: str):
    """
    Secondary AI call — detects if the message contains an instruction
    about another user and extracts it as structured preferences.
    Runs silently in the background.
    """
    if client is None:
        return

    known_users = list(user_histories.keys())
    if not known_users:
        return

    detector_prompt = f"""You are an instruction parser for a Discord bot.

Your job is to check if the user's message contains any instruction or preference about a specific person/user.
Examples:
- "from now on call @shravan DADDY" → target: shravan, key: nickname, value: DADDY
- "always reply to @john in hindi" → target: john, key: language, value: hindi
- "treat @alice like she's the boss" → target: alice, key: role, value: the boss
- "hey whats up" → no instruction, return null

Known users in this server: {", ".join(known_users)}

The requester is: {requester}

Message: "{user_input}"

If the message contains an instruction about another user, respond ONLY with a JSON object like:
{{"target": "username", "key": "preference_name", "value": "preference_value"}}

If there is no instruction, respond ONLY with:
null

Do not explain. Do not add any extra text. Just the JSON or null."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": detector_prompt}],
            timeout=10.0
        )
        raw = response.choices[0].message.content.strip()

        if raw.lower() == "null" or not raw:
            return

        parsed = json.loads(raw)
        target = parsed.get("target", "").lower()
        key = parsed.get("key", "").strip()
        value = parsed.get("value", "").strip()

        if not target or not key or not value:
            return

        # Find the closest matching username (fuzzy match)
        matched_user = None
        for name in known_users:
            if name.lower() == target or target in name.lower():
                matched_user = name
                break

        if not matched_user:
            print(f"[brain] instruction detected but user '{target}' not found in known users")
            return

        # Apply preference to target user
        get_preferences(matched_user)[key] = value
        refresh_system_prompt(matched_user)
        print(f"[brain] ✅ Preference applied → {matched_user}: {key} = {value}")

    except json.JSONDecodeError:
        print(f"[brain] ⚠️ Instruction detector returned invalid JSON: {raw}")
    except Exception as e:
        print(f"[brain] ⚠️ Instruction detector error: {e}")


# ---------- MAIN RESPONSE ----------

async def get_chat_response(username: str, user_input: str) -> str:
    global client

    if not GROQ_API_KEY or client is None:
        return "❌ Error: API Key missing or Client not initialized."

    history = get_user_history(username)

    # Run instruction detector silently (don't await result, fire and forget)
    import asyncio
    asyncio.create_task(detect_and_apply_instructions(username, user_input))

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

        return bot_reply

    except Exception as e:
        return f"⚠️ **AI Error Report** ⚠️\n**Detail:** `{str(e)}`"
