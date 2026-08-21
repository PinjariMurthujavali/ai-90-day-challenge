# ============================================
# Day 10: export_utils.py
# JSON + branded PDF export for a chat transcript.
# (Carried over from Day 8, unchanged in behavior.)
# ============================================

import json
from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos


def _pdf_safe(text):
    # Core PDF fonts only support latin-1; replace unsupported chars (emojis etc.)
    text = text or ""
    return text.encode('latin-1', 'replace').decode('latin-1')


def export_chat_json(title, personality, history):
    data = {
        "title": title or "Untitled",
        "personality": personality,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "messages": [{"role": r, "content": c} for r, c in history],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


# Brand palette used across the app (Streamlit UI + PDF export share these colors)
BRAND = {
    "coral": (255, 90, 95),      # primary accent
    "coral_dark": (214, 61, 66),
    "ink": (30, 32, 44),
    "muted": (110, 116, 138),
    "bubble_user": (255, 236, 234),
    "bubble_ai": (238, 241, 250),
    "line": (230, 232, 240),
}


class ChatPDF(FPDF):
    """A themed PDF report for an exported chat, with a colored header,
    chat-bubble-style message blocks, and a footer with page numbers."""

    def __init__(self, title, personality):
        super().__init__()
        self.chat_title = title or "Untitled Chat"
        self.personality = personality
        self.set_auto_page_break(auto=True, margin=18)

    def header(self):
        self.set_fill_color(*BRAND["coral"])
        self.rect(0, 0, self.w, 24, style="F")

        self.set_xy(10, 6)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 8, _pdf_safe(f"Murthu AI Chatbot - {self.chat_title}"),
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_xy(10, 15)
        self.set_font("Helvetica", "", 10)
        label = self.personality.replace("_", " ").title() if self.personality else "Mentor"
        self.cell(0, 6, _pdf_safe(f"Personality: {label}"),
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_y(30)
        self.set_text_color(*BRAND["ink"])

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*BRAND["muted"])
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def message_bubble(self, role, content):
        is_user = role == "user"
        label = "You" if is_user else "AI Assistant"
        fill = BRAND["bubble_user"] if is_user else BRAND["bubble_ai"]

        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*(BRAND["coral_dark"] if is_user else BRAND["muted"]))
        self.cell(0, 6, _pdf_safe(label), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_font("Helvetica", "", 11)
        text = _pdf_safe(content)
        line_height = 6
        available_width = self.w - self.l_margin - self.r_margin - 8
        lines = self.multi_cell(available_width, line_height, text,
                                 dry_run=True, output="LINES")
        block_height = max(len(lines), 1) * line_height + 6

        x, y = self.l_margin, self.get_y()
        self.set_fill_color(*fill)
        self.rect(x, y, self.w - self.l_margin - self.r_margin, block_height, style="F")

        self.set_xy(x + 4, y + 3)
        self.set_text_color(*BRAND["ink"])
        self.multi_cell(available_width, line_height, text,
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_y(y + block_height + 4)


def export_chat_pdf(title, personality, history):
    pdf = ChatPDF(title, personality)
    pdf.add_page()

    for role, content in history:
        pdf.message_bubble(role, content)

    output = pdf.output()
    return bytes(output) if not isinstance(output, str) else output.encode('latin-1')
