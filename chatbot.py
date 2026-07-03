# ============================================
# Day 3: AI Personality (System Prompt) + Save Chat to File
# ============================================

import os
from dotenv import load_dotenv
from groq import Groq
from datetime import datetime
# ↑ "datetime" ante - Python built-in library, current date/time
# తీసుకోవడానికి వాడుతాం (chat save చేసేటప్పుడు timestamp కోసం)

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)


# STEP 1: SYSTEM PROMPT - AI కి "personality/role" ఇవ్వడం
system_prompt = "You are a friendly, motivating coding mentor who explains things simply and encourages the user like a supportive friend."
# ↑ Idi oka plain text - AI కి "నువ్వు ఎవరు, ఎలా behave చేయాలి" ani చెప్తుంది
# Idi marchi, AI ni "career coach", "funny comedian", "strict teacher"
# ఇలా ఏదైనా personality గా మార్చుకోవచ్చు - ప్రయత్నించి చూడు!


# STEP 2: Conversation history - kani ippudu SYSTEM message tho START avutundi
conversation_history = [
    {"role": "system", "content": system_prompt}
    # ↑ "role": "system" - idi user కాదు, AI కాదు, ఇది "instructions"
    # ఇది AI కి conversation start అయ్యేముందే ఇచ్చే "rule book"
    # List లో మొదటి item గా ఉండాలి, ఎందుకంటే idi context set చేస్తుంది
]


print("🤖 AI Chatbot (with Personality + Memory) Ready!")
print("'exit' ani type chesthe chat aagi, file lo save avutundi.\n")


# STEP 3: Loop start cheyadam (ade lాగే)
while True:
    user_question = input("Ni question enti? : ")

    if user_question.lower() == "exit":
        # STEP 4: Exit ayyaka, chat ni FILE lo SAVE cheyadam
        # ============================================

        # STEP 4a: File పేరు కి timestamp add cheyadam (unique file kosam)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # ↑ datetime.now() → ఇప్పుడు exact date & time తీసుకుంటుంది
        # .strftime("%Y-%m-%d_%H-%M-%S") → దాన్ని readable text format కి మారుస్తుంది
        # Example output: "2026-07-03_14-30-45"
        # Idi enduku? → prathi chat session ki వేరే file name వచ్చేలా,
        # పాత chat overwrite avvakుండా

        filename = f"chat_history_{timestamp}.txt"
        # ↑ "f" string ante - variable value ni string లోపల insert cheయడం
        # Example: filename = "chat_history_2026-07-03_14-30-45.txt"

        # STEP 4b: File open చేసి, రాయడం (write mode)
        with open(filename, "w", encoding="utf-8") as file:
            # ↑ open(filename, "w") → ఈ పేరుతో ఒక కొత్త file create చేస్తుంది
            # "w" mode ante "write" - ఖాళీ file గా start అవుతుంది
            # encoding="utf-8" → emojis/special characters సరిగ్గా save అవ్వడానికి
            # "with...as file" → file ని safely open చేసి, పని అయ్యాక
            # automatic గా close చేస్తుంది (మనం మర్చిపోయినా సరే)

            for message in conversation_history:
                # ↑ conversation_history list లో ప్రతి item మీద loop run అవుతుంది
                # (system message కూడా కలిపి)

                if message["role"] == "system":
                    continue
                    # ↑ "continue" → ఈ loop cycle ని skip చేసి next కి వెళ్తుంది
                    # system message ని file లో రాయము (అది AI instructions మాత్రమే)

                role = message["role"]
                content = message["content"]
                file.write(f"{role.upper()}: {content}\n\n")
                # ↑ file.write() → file లో text రాస్తుంది
                # role.upper() → "user"/"assistant" ni "USER"/"ASSISTANT" గా మారుస్తుంది
                # \n\n → రెండు new lines (readability కోసం gap)

        print(f"\n Chat saved to: {filename}")
        print("Chat end ayyindi. Bye bro! ")
        break

    # STEP 5: User question ni history కి add చేయడం (ade లాగే)
    conversation_history.append({"role": "user", "content": user_question})

    # STEP 6: AI కి POORA history (system prompt తో సహా) పంపడం
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=conversation_history
        # ↑ Ippudu ఇందులో system prompt + full conversation history
        # రెండూ ఉంటాయి, కాబట్టి AI దాని "personality" ని గుర్తుపెట్టుకుంటూనే
        # past messages కూడా గుర్తుంచుకుంటుంది
    )

    ai_reply = response.choices[0].message.content
    conversation_history.append({"role": "assistant", "content": ai_reply})

    print("\nAI Answer:", ai_reply, "\n")