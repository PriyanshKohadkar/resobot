import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Groq Client
# Get your key from: https://console.groq.com/keys
client = Groq(api_key=GROQ_API_KEY)

# Dictionary to store history (Simulating Gemini's Chat Session)
sessions = {}

def get_chat_response(user_id, user_input):
    # If no session, create a new one with a System Prompt
    if user_id not in sessions:
        sessions[user_id] = [
            {
                "role": "system", 
                "content": "You are a genius AI friend. Speak Hinglish for casual chat, but if the user asks a Math or Science question, provide a detailed step-by-step solution in English. Use LaTeX format for equations if necessary."
            }
        ]
    
    # Add User Message to history
    sessions[user_id].append({"role": "user", "content": user_input})

    try:
        # Calling Groq (Llama 3.3 70B is very smart and free)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=sessions[user_id],
            temperature=0.2,
            max_tokens=2000
        )
        
        bot_reply = response.choices[0].message.content
        
        # Add Assistant Reply to history for context/memory
        sessions[user_id].append({"role": "assistant", "content": bot_reply})
        
        # Memory Management: Keep only last 10 messages to avoid lag
        if len(sessions[user_id]) > 12:
            sessions[user_id] = [sessions[user_id][0]] + sessions[user_id][-10:]

        return bot_reply

    except Exception as e:
        print(f"Groq Error: {e}")
        return "Bhai, dimaag ki batti gul ho gayi hai. Ek minute baad try kar!"

def reset_chat(user_id):
    """Function to clear memory if needed"""
    if user_id in sessions:
        del sessions[user_id]
