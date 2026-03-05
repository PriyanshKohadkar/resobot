import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# --- STEP 1: KEY LOADING CHECK ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- STEP 2: CLIENT INITIALIZATION ---
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

# --- SHARED SESSION STORAGE ---
# Only one list for everyone. 
# Started with the system prompt.
shared_history = [{"role": "system", "content": "You are a chill friend speaking Hinglish. Multiple users are talking to you in a group. Use their names to address them if needed."}]

def get_chat_response(username, user_input):
    global client, shared_history
    
    if not GROQ_API_KEY or client is None:
        return "❌ Error: API Key missing or Client not initialized."

    # 1. Format input to include the Username
    # This helps the AI know WHO is talking since the session is shared.
    formatted_input = f"{username}: {user_input}"
    
    shared_history.append({"role": "user", "content": formatted_input})

    # 2. Memory Management (Keep only last 8 messages + 1 system prompt)
    # We keep index 0 (system prompt) and the last 8 messages.
    if len(shared_history) > 9:
        shared_history = [shared_history[0]] + shared_history[-8:]

    try:
        print(f"⏳ DEBUG: Calling Groq for {username} (Shared Session)...")
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=shared_history,
            timeout=25.0
        )
        
        bot_reply = response.choices[0].message.content
        
        # 3. Save bot reply to shared history
        shared_history.append({"role": "assistant", "content": bot_reply})
        
        return bot_reply

    except Exception as e:
        error_detail = str(e)
        return f"⚠️ **AI Error Report** ⚠️\n**Detail:** `{error_detail}`"
