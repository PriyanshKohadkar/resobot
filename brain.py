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
        print("🚨 DEBUG: GROQ_API_KEY is EMPTY or NONE!")
    else:
        # Key ki pehli 4 aur last 4 digits print karega logs mein security ke liye
        print(f"✅ DEBUG: Key found! Starts with: {GROQ_API_KEY[:4]}... Ends with: {GROQ_API_KEY[-4:]}")
        client = Groq(api_key=GROQ_API_KEY)
        print("✅ DEBUG: Groq Client object created.")
except Exception as e:
    client = None
    print(f"🚨 DEBUG: Client Init Error: {str(e)}")

sessions = {}

def get_chat_response(user_id, user_input):
    global client
    
    # Check 1: Key Check
    if not GROQ_API_KEY:
        return "❌ Error: Render ke environment variables mein 'GROQ_API_KEY' nahi mili!"

    # Check 2: Client Check
    if client is None:
        return "❌ Error: Groq client initialize nahi ho paya. Render logs check karo."

    # Session management
    if user_id not in sessions:
        sessions[user_id] = [{"role": "system", "content": "You are a chill friend speaking Hinglish."}]
    
    sessions[user_id].append({"role": "user", "content": user_input})

    try:
        print(f"⏳ DEBUG: Calling Groq API for user {user_id}...")
        
        # Check 3: API Call (Using a very stable model name)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=sessions[user_id],
            timeout=25.0
        )
        
        bot_reply = response.choices[0].message.content
        print("✅ DEBUG: API Response received successfully!")
        
        sessions[user_id].append({"role": "assistant", "content": bot_reply})
        return bot_reply

    except Exception as e:
        # --- THE ULTIMATE DEBUG MESSAGE ---
        error_type = type(e).__name__
        error_detail = str(e)
        
        # Ye message seedha Discord pe jayega
        debug_report = (
            f"⚠️ **AI Error Report** ⚠️\n"
            f"**Type:** `{error_type}`\n"
            f"**Detail:** `{error_detail}`\n"
            f"**Hint:** {'API Key galat hai' if '401' in error_detail else 'Check Render Logs'}"
        )
        print(f"🚨 DEBUG: {debug_report}")
        return debug_report
