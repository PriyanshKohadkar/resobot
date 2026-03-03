import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Step 1: Check if key is actually loading
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
print(f"DEBUG: Key loaded length: {len(GROQ_API_KEY) if GROQ_API_KEY else '0 (NOT FOUND)'}")

# Step 2: Initialize client inside a try block
try:
    client = Groq(api_key=GROQ_API_KEY)
    print("DEBUG: Groq Client Initialized Successfully")
except Exception as e:
    print(f"DEBUG: Client Init Failed: {e}")

sessions = {}

def get_chat_response(user_id, user_input):
    if not GROQ_API_KEY:
        return "Bhai, Render ko teri API key nahi mil rahi. Environment variables check kar!"

    if user_id not in sessions:
        sessions[user_id] = [{"role": "system", "content": "You are a chill friend."}]
    
    sessions[user_id].append({"role": "user", "content": user_input})

    try:
        print(f"DEBUG: Attempting API call for user {user_id}")
        
        # Step 3: Use a smaller model for testing (8B is faster and less likely to timeout)
        response = client.chat.completions.create(
            model="llama3-8b-8192", 
            messages=sessions[user_id],
            timeout=20.0
        )
        
        bot_reply = response.choices[0].message.content
        print("DEBUG: API Call Success!")
        
        sessions[user_id].append({"role": "assistant", "content": bot_reply})
        return bot_reply

    except Exception as e:
        # Is baar hum poora error message bhejenge Discord pe
        error_msg = f"🚨 Error Type: {type(e).__name__} | Details: {str(e)}"
        print(f"DEBUG: {error_msg}")
        return f"Bhai, dimaag garam ho gaya! Reason: {error_msg}"
