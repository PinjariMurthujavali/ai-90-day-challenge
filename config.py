# ============================================
# Day 10: config.py
# Shared constants: personality presets used by chat
# creation, the AI system prompt, and badge colors.
# ============================================

PERSONALITIES = {
    "mentor":         {"prompt": "You are a friendly, motivating coding mentor.",  "emoji": "🧑‍🏫", "color": "#4F8BF9"},
    "comedian":       {"prompt": "You are a witty, funny comedian.",               "emoji": "😂",   "color": "#F59E0B"},
    "strict_teacher": {"prompt": "You are a strict but fair teacher.",             "emoji": "📐",   "color": "#EF4444"},
    "zen_master":     {"prompt": "You are a calm, wise zen master.",               "emoji": "🧘",   "color": "#10B981"},
    "enthusiast":     {"prompt": "You are an overly enthusiastic tech enthusiast!", "emoji": "🚀",  "color": "#A855F7"},
}


def personality_info(personality):
    return PERSONALITIES.get(personality, PERSONALITIES["mentor"])


def personality_label(personality):
    return (personality or "mentor").replace("_", " ").title()
