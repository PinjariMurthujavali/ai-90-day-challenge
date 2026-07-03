# ============================================
# Day 2: AI Chatbot with Memory (Conversation History)
# ============================================

import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)


# STEP 1: Conversation history store cheyadaniki oka "list" create cheyadam
conversation_history = []
# ↑ "list" ante - multiple items ni oka order lo store cheyadaniki
# empty list [] tho start chestunnam, prathi question/answer ni ikkada add chestam
# Idi lekapote, AI ki "past" gurthu undadu - prathi question isolated ga treat chestundi


# STEP 2: Welcome message
print("🤖 AI Chatbot (with Memory) Ready! ('exit' ani type chesthe chat aagipotundi)\n")


# STEP 3: Loop start cheyadam
while True:

    user_question = input("Ni question enti? : ")

    if user_question.lower() == "exit":
        print("Chat end ayyindi. Bye bro! 👋")
        break

    # STEP 4: User question ni conversation_history list ki add cheyadam
    conversation_history.append({"role": "user", "content": user_question})
    # ↑ .append() → list chivarki oka kotha item add chestundi
    # {"role": "user", "content": user_question} → idi oka "dictionary"
    # (chinna data package - "evaru matladaru" + "em matladaru" ani cheputundi)
    # Ippudu conversation_history lo:
    # [{"role": "user", "content": "hi"}] ala untundi


    # STEP 5: AI ki REQUEST pampేటప్పుడు - ఒక్క question కాదు, MEMORY MOTHAM pampadam
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=conversation_history
        # ↑ Idi Day 1 lo maarindi! Munupu manam matrame single question pampam:
        # messages=[{"role": "user", "content": user_question}]
        # Ippudu manam POORA conversation_history list pampistunnam
        # Ala AI ki "past" antha kanipistundi, context tho better answers isthundi
    )


    ai_reply = response.choices[0].message.content


    # STEP 6: AI answer ni kuda conversation_history lo add cheyadam
    conversation_history.append({"role": "assistant", "content": ai_reply})
    # ↑ "role": "assistant" → idi AI ichina reply ani cheputundi
    # (role "user" ante manam, role "assistant" ante AI)
    # Ippudu AI ki full back-and-forth conversation gurthu untundi
    # next question adiginappudu, ee full history malli pampistam


    print("\nAI Answer:", ai_reply, "\n")