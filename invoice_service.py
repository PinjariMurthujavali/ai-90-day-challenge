# ============================================
# invoice_service.py — REWRITTEN
#
# BUGS THIS FIXES (found while wiring Day 24 refunds on top of this file):
#
# 1. The old version connected with raw `sqlite3.connect("chatbot.db")`
#    instead of the app's shared `database.get_connection()`. When Turso
#    (remote DB) is configured — which it is for this project — every
#    other file writes there, but this file was silently writing to a
#    throwaway LOCAL file instead. On Streamlit Cloud that local file is
#    wiped on every redeploy, so invoices would vanish, disconnected from
#    the real database the rest of the app uses.
#
# 2. create_invoice() did `user_id[:3]` assuming user_id is a string, but
#    every caller (razorpay_service.py, chatbot.py) passes it as the
#    integer it actually is everywhere else in this codebase. This would
#    crash with `TypeError: 'int' object is not subscriptable` the moment
#    a real payment tried to create its invoice — i.e. every real payment.
#
# 3. chatbot.py calls invoice_service.get_payment() and
#    generate_invoice_pdf() — neither existed. Viewing/downloading an
#    invoice would crash the app.
#
# 4. stripe_service.py calls invoice_service.record_payment(...) with a
#    named-argument signature — also didn't exist. A completed Stripe
#    payment would crash right after the money was already charged.
#
# This version uses the `payments` table that database.py already
# defines correctly (Turso-safe), adds the 3 missing functions with the
# exact signatures/shapes callers already expect, and adds Day 24 refund
# support on top.
# ============================================

from datetime import datetime

import streamlit as st

from database import get_connection


def _invoice_number(user_id):
    # Second-level timestamps alone can collide if two payments for the
    # same user land within the same second (caught this in testing —
    # two quick payments crashed on the invoices.invoice_number UNIQUE
    # constraint). Microseconds make that practically impossible.
    return f"INV-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}-{int(user_id):04d}"


def record_payment(user_id, gateway, plan, amount, currency="INR",
                    gateway_order_id=None, gateway_payment_id=None, status="paid"):
    """The canonical way a real charge becomes an invoice row. Called by
    both stripe_service.py (webhook) and create_invoice() below (Razorpay)."""
    invoice_number = _invoice_number(user_id)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO payments (user_id, gateway, plan, amount, currency,
                                   gateway_order_id, gateway_payment_id, status, invoice_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, gateway, plan, amount, currency,
              gateway_order_id, gateway_payment_id, status, invoice_number))
        conn.commit()
        get_user_payments.clear()
        return {"success": True, "invoice_number": invoice_number, "id": cursor.lastrowid}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def create_invoice(user_id, order_id, amount, plan, payment_id=None):
    """Backward-compatible wrapper — this is the exact name/signature
    razorpay_service.py already calls after a verified payment."""
    return record_payment(
        user_id=user_id, gateway="razorpay", plan=plan, amount=amount,
        currency="INR", gateway_order_id=order_id, gateway_payment_id=payment_id,
        status="paid",
    )


@st.cache_data(ttl=10)
def get_user_payments(user_id):
    """Returns (id, gateway, plan, amount, currency, status, invoice_number,
    created_at) tuples — this exact shape is destructured directly in
    chatbot.py's billing-history loop, so don't reorder these columns
    without updating that loop too."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, gateway, plan, amount, currency, status, invoice_number, created_at
        FROM payments WHERE user_id = ? ORDER BY created_at DESC, id DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_payment(payment_id, user_id=None):
    """Fetch one payment as a dict. Pass user_id to enforce that a user
    can only ever look up their OWN invoices (chatbot.py always passes
    it); admin-side refund tooling can omit it."""
    conn = get_connection()
    cursor = conn.cursor()
    if user_id is not None:
        cursor.execute("SELECT * FROM payments WHERE id = ? AND user_id = ?", (payment_id, user_id))
    else:
        cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
    row = cursor.fetchone()
    cols = [d[0] for d in cursor.description] if hasattr(cursor, "description") and cursor.description else [
        "id", "user_id", "gateway", "plan", "amount", "currency", "gateway_order_id",
        "gateway_payment_id", "status", "invoice_number", "created_at",
        "refund_status", "refund_reason", "refunded_amount", "refund_requested_at", "refunded_at",
    ]
    conn.close()
    if not row:
        return None
    return dict(zip(cols, row))


def generate_invoice_pdf(payment_row):
    """payment_row is the dict returned by get_payment(). Returns raw PDF
    bytes for st.download_button. Uses fpdf2's core Helvetica font, so
    amounts are shown as 'Rs. 499.00' rather than the ₹ glyph — the core
    PDF fonts are latin-1 only and would either crash or render ₹ as a
    black box otherwise (same constraint export_utils.py already works
    around for chat exports)."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    if not payment_row:
        raise ValueError("No payment found for this invoice.")

    pdf = FPDF()
    pdf.add_page()

    pdf.set_fill_color(108, 99, 255)  # brand violet
    pdf.rect(0, 0, 210, 30, style="F")
    pdf.set_xy(10, 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "Murthu AI Chatbot", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Payment Invoice", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_text_color(30, 32, 44)
    pdf.set_xy(10, 40)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, payment_row.get("invoice_number", ""), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 100)
    created_at = str(payment_row.get("created_at", ""))[:19]
    pdf.cell(0, 6, f"Date: {created_at}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    rows = [
        ("Plan", str(payment_row.get("plan", "")).title()),
        ("Payment method", str(payment_row.get("gateway", "")).title()),
        ("Amount", f"{payment_row.get('currency', 'INR')} {float(payment_row.get('amount', 0)):.2f}"),
        ("Status", str(payment_row.get("status", "")).title()),
    ]
    if payment_row.get("refund_status") not in (None, "none"):
        rows.append(("Refund status", str(payment_row["refund_status"]).title()))
    if payment_row.get("gateway_payment_id"):
        rows.append(("Transaction ID", payment_row["gateway_payment_id"]))

    pdf.set_text_color(30, 32, 44)
    for label, value in rows:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(45, 8, label, border="B")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, value, border="B", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(140, 140, 150)
    pdf.multi_cell(0, 5, "This is a system-generated invoice. For billing questions, contact support "
                          "through the app.")

    return bytes(pdf.output())


# ============================================
# Day 24: Refunds
# Request -> admin approval pattern, same honesty rule as Day 20 upgrades:
# nothing here pretends money moved until it actually did. Approving a
# Razorpay payment's refund calls the REAL Razorpay refund API (already
# built in razorpay_service.refund_payment) so approving here really does
# return the money — this isn't just a status-flip.
# ============================================

def request_refund(payment_id, user_id, reason):
    payment = get_payment(payment_id, user_id=user_id)
    if not payment:
        return False, "Invoice not found."
    if payment["status"] != "paid":
        return False, "Only paid invoices can be refunded."
    if payment.get("refund_status") not in (None, "none"):
        return False, "A refund has already been requested for this invoice."

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE payments SET refund_status = 'requested', refund_reason = ?,
                             refund_requested_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
    ''', (reason, payment_id, user_id))
    conn.commit()
    conn.close()
    get_user_payments.clear()
    get_pending_refunds.clear()
    return True, "Refund requested — an admin will review it shortly."


@st.cache_data(ttl=10)
def get_pending_refunds():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.invoice_number, u.username, p.plan, p.amount, p.currency,
               p.gateway, p.gateway_payment_id, p.refund_reason, p.refund_requested_at, p.user_id
        FROM payments p
        JOIN users u ON u.id = p.user_id
        WHERE p.refund_status = 'requested'
        ORDER BY p.refund_requested_at ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows


def approve_refund(payment_id):
    """Approves a pending refund. If it's a Razorpay payment and Razorpay
    is configured, calls the real refund API first — only marks the DB
    row refunded if that actually succeeds (or if there's no gateway to
    call, e.g. a manually-recorded payment)."""
    payment = get_payment(payment_id)
    if not payment or payment.get("refund_status") != "requested":
        return False, "No pending refund request found."

    gateway = payment.get("gateway")
    gateway_payment_id = payment.get("gateway_payment_id")

    if gateway == "razorpay" and gateway_payment_id:
        import razorpay_service
        if razorpay_service.razorpay.is_configured():
            result = razorpay_service.razorpay.refund_payment(gateway_payment_id)
            if result.get("error"):
                return False, f"Razorpay refund failed: {result['error']}"
    elif gateway == "stripe" and gateway_payment_id:
        import stripe_service
        if stripe_service.is_configured():
            ok, msg = stripe_service.refund_payment(gateway_payment_id)
            if not ok:
                return False, f"Stripe refund failed: {msg}"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE payments SET refund_status = 'approved', status = 'refunded',
                             refunded_amount = amount, refunded_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (payment_id,))
    conn.commit()
    conn.close()
    get_user_payments.clear()
    get_pending_refunds.clear()
    return True, "Refund approved and processed."


def reject_refund(payment_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE payments SET refund_status = 'rejected' WHERE id = ?", (payment_id,))
    conn.commit()
    conn.close()
    get_pending_refunds.clear()


# ============================================
# Backward-compat shim: old code imported a module-level `invoice_service`
# instance and called methods on it (invoice_service.create_invoice(...)
# etc). Keep that working without touching every caller.
# ============================================
class _InvoiceServiceShim:
    create_invoice = staticmethod(create_invoice)
    record_payment = staticmethod(record_payment)
    get_user_payments = staticmethod(get_user_payments)
    get_payment = staticmethod(get_payment)
    generate_invoice_pdf = staticmethod(generate_invoice_pdf)
    request_refund = staticmethod(request_refund)


invoice_service = _InvoiceServiceShim()
