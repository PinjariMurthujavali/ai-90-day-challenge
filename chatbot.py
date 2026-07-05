# ============================================
# Day 4: CLI Arguments + Multiple AI Personalities
# ============================================

import os
from dotenv import load_dotenv
from groq import Groq
from datetime import datetime
import sys
# ↑ "sys" → Python system module, command-line arguments తీసుకోవడానికి
# Terminal నుండి arguments pass చేస్తాం, ఇక్కడ access చేస్తాం

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)


# STEP 1: Multiple Personalities Dictionary Create చేయడం
personalities = {
    "mentor": "You are a friendly, motivating coding mentor who explains things simply and encourages the user like a supportive friend.",
    
    "comedian": "You are a witty, funny comedian who makes jokes and uses humor while still being helpful. Keep responses light and entertaining.",
    
    "strict_teacher": "You are a strict but fair teacher who doesn't tolerate nonsense. Be direct, no-nonsense, and demand excellence. Correct mistakes harshly but fairly.",
    
    "zen_master": "You are a calm, wise zen master who speaks in philosophical terms and uses metaphors. Help users see the bigger picture and find inner peace through coding.",
    
    "enthusiast": "You are an overly enthusiastic tech enthusiast who gets excited about everything! Use lots of emojis and exclamation marks. Hype up the user!",
}
# ↑ "dictionary" ante - key:value pairs లో data store చేయడం
# ఇక్కడ key = personality names ("mentor", "comedian", etc)
# value = system prompt text (ee personality кoసam instructions)


# STEP 2: Default Personality Set చేయడం
default_personality = "mentor"
# ↑ User ఏ personality specify చేయకపోతే, ఈ default use చేస్తాం


# STEP 3: Command-line Arguments నుండి Personality Choose చేయడం
selected_personality = default_personality
# ↑ మొదట default గా set చేస్తాం

# STEP 4: sys.argv చెక్ చేయడం
if len(sys.argv) > 1:
    # ↑ sys.argv[0] = script name ("chatbot.py")
    # sys.argv[1] = first argument (if user passes)
    # "if len(sys.argv) > 1" → user 1+ argument pass చేసినా ani check
    
    requested_personality = sys.argv[1].lower()
    # ↑ sys.argv[1] → terminal నుండి first argument తీసుకుంటుంది
    # .lower() → caps undaina vundaina, lowercase గా convert చేస్తుంది
    # Example: user "python chatbot.py MENTOR" type చేస్తే → "mentor" అవుతుంది
    
    if requested_personality in personalities:
        # ↑ "if ... in dictionary" → ఆ key dictionary లో ఉందా ani check
        selected_personality = requested_personality
        print(f"✅ Personality selected: {selected_personality.upper()}\n")
    else:
        # ↑ User invalid personality type చేస్తే
        print(f"❌ Personality '{requested_personality}' not found!")
        print(f"Available personalities: {', '.join(personalities.keys())}")
        print(f"Using default: {default_personality}\n")
        selected_personality = default_personality
else:
    print(f"💡 Tip: Run with --help for personality options or: python chatbot.py <personality_name>\n")
    print(f"Available: {', '.join(personalities.keys())}\n")


# STEP 5: Selected Personality నుండి System Prompt తీసుకోవడం
system_prompt = personalities[selected_personality]
# ↑ dictionary[key] → ఆ key కోసం value తీసుకుంటుంది
# Example: personalities["mentor"] → mentor personality system prompt


# STEP 6: Conversation History with System Prompt
conversation_history = [
    {"role": "system", "content": system_prompt}
]


# STEP 7: Welcome Message (personality tho together)
personality_emoji = {
    "mentor": "🎓",
    "comedian": "🤣",
    "strict_teacher": "👨‍🏫",
    "zen_master": "🧘",
    "enthusiast": "🤩",
}
# ↑ Personality కోసం emoji — visual indication

print(f"{personality_emoji.get(selected_personality, '🤖')} AI Chatbot ({selected_personality.upper()}) Ready!")
print("Type 'exit' to end chat and save.\n")


# STEP 8: Main Loop
while True:
    user_question = input("Nీ question enti? : ")

    if user_question.lower() == "exit":
        # File Save Logic (Day 3 నుండి same)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"chat_history_{selected_personality}_{timestamp}.txt"
        # ↑ File name lo personality name కూడా include చేస్తాం
        # Example: chat_history_comedian_2026-07-04_...txt
        
        with open(filename, "w", encoding="utf-8") as file:
            file.write(f"PERSONALITY: {selected_personality.upper()}\n")
            file.write("=" * 50 + "\n\n")
            # ↑ File header లో personality mention చేస్తాం
            
            for message in conversation_history:
                if message["role"] == "system":
                    continue
                
                role = message["role"]
                content = message["content"]
                file.write(f"{role.upper()}: {content}\n\n")

        print(f"\n💾 Chat saved to: {filename}")
        print("Chat end ayyindi. Bye bro! 👋")
        break

    # Add User Message
    conversation_history.append({"role": "user", "content": user_question})

    # AI Response
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=conversation_history
    )

    ai_reply = response.choices[0].message.content
    conversation_history.append({"role": "assistant", "content": ai_reply})

    print("\nAI Answer:", ai_reply, "\n")