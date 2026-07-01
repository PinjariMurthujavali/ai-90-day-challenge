# ============================================
# Day 1: My First AI Chatbot
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


# STEP 5: User nunchi question tీskovadam
user_question = input("Nీ question enti? : ")
# input() → terminal lo user type chesina text ni
# "user_question" ane variable lo store chestundi
# Example: nuvvu "Python ante enti?" ani type cheste,
# adi ee variable lo save avutundi


# STEP 6: AI ki request pampadam
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
# Ee full block "AI ki call చేసి, response కోసం wait చేయ్యి" ani chestundi


# STEP 7: AI reply ni extract chesi print cheyadam
ai_reply = response.choices[0].message.content
# response ante AI nunchi vachina "full package" (data + metadata)
# "choices[0]" → AI ichina first (best) answer
# ".message.content" → aa answer లోని actual TEXT matrame తీసుకుంటుంది

print("\nAI Answer:", ai_reply)
# print() → terminal lo AI answer ni display chestundi
# "\n" → oka new line add chestundi (clean ga కనిపించడానికి)