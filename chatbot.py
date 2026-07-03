# ============================================
# Day 1: My First AI Chatbot (with continuous chat loop)
# ============================================

# STEP 1: Required libraries import cheyadam
# "import" ante - already install chesina packages ni ee file lo vadukovadam

import os
# os = Operating System library
# Idi environment variables (like .env lo unna key) ni read cheyadaniki use avutundi

from dotenv import load_dotenv
# dotenv library nunchi "load_dotenv" ane function tీskuntunnam
# Idi .env file ni chadivi, andulo unna values ni python ki andistundi

from groq import Groq
# groq library nunchi "Groq" ane class tీskuntunnam
# Idi AI ki connect avvadaniki maku kavalasina "tool/object"


# STEP 2: .env file load cheyadam
load_dotenv()
# Ee line run ayyinappudu, .env file lo unna
# GROQ_API_KEY=xxxx ane line ni chadivi
# దానిని python "memory" లోకి తీసుకుంటుంది (env variable గా)


# STEP 3: API Key ni safely tీskovadam
api_key = os.getenv("GROQ_API_KEY")
# os.getenv() → .env file nunchi "GROQ_API_KEY" name tho unna
# value ni tీskuni "api_key" ane variable lo store chestundi
# (Idi hardcode cheyakapoyina, safe ga key ni access cheyadam)


# STEP 4: Groq client create cheyadam
client = Groq(api_key=api_key)
# "client" ante - AI tho matladataniki maku unna "phone" laantidi
# Ee client object ni vadi manam AI ki questions pampistam,
# AI nunchi answers tీskuntam


# STEP 5: Welcome message print cheyadam (one-time, loop bayata)
print("🤖 AI Chatbot Ready! ('exit' ani type chesthe chat aagipotundi)\n")


# STEP 6: Infinite loop start cheyadam - continuous chat kosam
while True:
    # ↑ "while True" ante - condition eppudu True ga untundi kabatti
    # ee loop eppatiki aagadu (manam manual ga stop chesse daaka)

    user_question = input("Nీ question enti? : ")
    # input() → terminal lo user type chesina text ni
    # "user_question" ane variable lo store chestundi
    # Ee line prathi loop cycle lo malli malli run avutundi,
    # kabatti prathi sari kotha question adagagalam

    # STEP 7: Exit condition - user "exit" ani type chesthe loop aapadam
    if user_question.lower() == "exit":
        # ↑ .lower() → user Exit/EXIT/exit ela type chesina
        # anni chinna letters ki convert chesi check chestundi
        print("Chat end ayyindi. Bye bro! 👋")
        break
        # ↑ "break" → ee loop ni ikkadithe aapestundi, script exit avutundi

    # STEP 8: AI ki request pampadam (idi prathi loop cycle lo repeat avutundi)
    response = client.chat.completions.create(
        # ↑ Idi "AI ki message pampu, reply తీసుకో" ane function

        model="llama-3.3-70b-versatile",
        # ↑ Ee AI "model" (brain) ni vadamantunnam
        # Groq lo ee model fast + free

        messages=[
            # ↑ "messages" ante conversation history
            # AI ki context ivvadaniki list format lo pampali

            {"role": "user", "content": user_question}
            # "role": "user" → ee message evaru pampistunnaro cheputundi (manam/user)
            # "content": user_question → manam adigina actual question
        ]
    )
    # Ee full block "AI ki call chesi, response kosam wait chey" ani chestundi

    # STEP 9: AI reply ni extract chesi print cheyadam
    ai_reply = response.choices[0].message.content
    # response ante AI nunchi vachina "full package" (data + metadata)
    # "choices[0]" → AI ichina first (best) answer
    # ".message.content" → aa answer లోని actual TEXT matrame తీసుకుంటుంది

    print("\nAI Answer:", ai_reply, "\n")
    # print() → terminal lo AI answer ni display chestundi
    # "\n" → new lines add chestundi (clean ga కనిపించడానికి, next question mundu)