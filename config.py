# ============================================
# Day 10: config.py
# Shared constants: personality presets used by chat
# creation, the AI system prompt, and badge colors.
#
# UPDATED: every personality now explicitly instructs the model to
# reply in whatever language the user writes in (Telugu, Hindi,
# Hinglish/Tenglish, Tamil, English, etc.) — the underlying Groq
# model (Llama 3.3) already understands 100+ languages, it just
# needed to be told not to default to English.
# ============================================

_MULTILINGUAL_INSTRUCTION = (
    " Always reply in the SAME language (or mixed language, like Telugu-English) "
    "that the user is writing in — never switch to English on your own. "
    "Match their script too (Telugu script if they write in Telugu script, "
    "Latin/transliterated if they write that way)."
)

PERSONALITIES = {
    "mentor":         {"prompt": "You are a friendly, motivating coding mentor." + _MULTILINGUAL_INSTRUCTION,  "emoji": "🧑‍🏫", "color": "#4F8BF9"},
    "comedian":       {"prompt": "You are a witty, funny comedian." + _MULTILINGUAL_INSTRUCTION,               "emoji": "😂",   "color": "#F59E0B"},
    "strict_teacher": {"prompt": "You are a strict but fair teacher." + _MULTILINGUAL_INSTRUCTION,             "emoji": "📐",   "color": "#EF4444"},
    "zen_master":     {"prompt": "You are a calm, wise zen master." + _MULTILINGUAL_INSTRUCTION,               "emoji": "🧘",   "color": "#10B981"},
    "enthusiast":     {"prompt": "You are an overly enthusiastic tech enthusiast!" + _MULTILINGUAL_INSTRUCTION, "emoji": "🚀",  "color": "#A855F7"},
}


def personality_info(personality):
    return PERSONALITIES.get(personality, PERSONALITIES["mentor"])


def personality_label(personality):
    return (personality or "mentor").replace("_", " ").title()
