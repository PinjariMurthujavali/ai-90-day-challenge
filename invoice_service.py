# ============================================
# Day 22: Invoice Management Service
# Generate and manage payment invoices
# ============================================

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

DATABASE = "chatbot.db"

class InvoiceService:
    """Day 22: Invoice generation and management"""
    
    def __init__(self):
        self.conn = None
    
    def init_db(self):
        """Initialize invoice tables"""
        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            
            # Invoices table
            c.execute('''
                CREATE TABLE IF NOT EXISTS invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_number TEXT UNIQUE,
                    user_id TEXT NOT NULL,
                    order_id TEXT,
                    payment_id TEXT,
                    amount REAL,
                    currency TEXT DEFAULT 'INR',
                    plan TEXT,
                    status TEXT DEFAULT 'pending',
                    issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    due_date TIMESTAMP,
                    paid_date TIMESTAMP,
                    notes TEXT,
                    metadata TEXT
                )
            ''')
            
            # Invoice items table
            c.execute('''
                CREATE TABLE IF NOT EXISTS invoice_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id INTEGER,
                    description TEXT,
                    quantity INTEGER DEFAULT 1,
                    unit_price REAL,
                    tax_rate REAL DEFAULT 0,
                    total REAL,
                    FOREIGN KEY (invoice_id) REFERENCES invoices (id)
                )
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Invoice DB init error: {e}")
    
    def create_invoice(self, user_id: str, order_id: str, amount: float, plan: str, payment_id: Optional[str] = None) -> Dict:
        """
        Day 22 Feature: Create a new invoice
        
        Args:
            user_id: User ID
            order_id: Razorpay order ID
            amount: Amount in INR
            plan: Payment plan
            payment_id: Razorpay payment ID
        
        Returns:
            Invoice details
        """
        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            
            invoice_number = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}-{user_id[:3].upper()}"
            issue_date = datetime.now()
            due_date = issue_date + timedelta(days=30)
            
            c.execute('''
                INSERT INTO invoices 
                (invoice_number, user_id, order_id, payment_id, amount, plan, status, issue_date, due_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (invoice_number, user_id, order_id, payment_id or "", amount, plan, "pending", issue_date, due_date))
            
            conn.commit()
            invoice_id = c.lastrowid
            conn.close()
            
            return {
                "success": True,
                "invoice_id": invoice_id,
                "invoice_number": invoice_number,
                "user_id": user_id,
                "amount": amount,
                "plan": plan,
                "status": "pending",
                "issue_date": issue_date.isoformat(),
                "due_date": due_date.isoformat()
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def add_invoice_item(self, invoice_id: int, description: str, quantity: int, unit_price: float, tax_rate: float = 0) -> Dict:
        """
        Day 22 Feature: Add line item to invoice
        
        Args:
            invoice_id: Invoice ID
            description: Item description
            quantity: Quantity
            unit_price: Unit price
            tax_rate: Tax rate (%)
        
        Returns:
            Item details
        """
        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            
            total = quantity * unit_price
            tax_amount = total * (tax_rate / 100)
            total_with_tax = total + tax_amount
            
            c.execute('''
                INSERT INTO invoice_items 
                (invoice_id, description, quantity, unit_price, tax_rate, total)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (invoice_id, description, quantity, unit_price, tax_rate, total_with_tax))
            
            conn.commit()
            item_id = c.lastrowid
            conn.close()
            
            return {
                "success": True,
                "item_id": item_id,
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "tax_rate": tax_rate,
                "total": total_with_tax
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_invoice(self, invoice_id: int) -> Dict:
        """
        Day 22 Feature: Get invoice details
        
        Args:
            invoice_id: Invoice ID
        
        Returns:
            Invoice details with items
        """
        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            
            c.execute('SELECT * FROM invoices WHERE id = ?', (invoice_id,))
            invoice = c.fetchone()
            
            if not invoice:
                return {"success": False, "error": "Invoice not found"}
            
            c.execute('SELECT * FROM invoice_items WHERE invoice_id = ?', (invoice_id,))
            items = c.fetchall()
            
            conn.close()
            
            return {
                "success": True,
                "invoice": {
                    "id": invoice[0],
                    "invoice_number": invoice[1],
                    "user_id": invoice[2],
                    "order_id": invoice[3],
                    "payment_id": invoice[4],
                    "amount": invoice[5],
                    "currency": invoice[6],
                    "plan": invoice[7],
                    "status": invoice[8],
                    "issue_date": invoice[9],
                    "due_date": invoice[10],
                    "paid_date": invoice[11],
                    "notes": invoice[12]
                },
                "items": [
                    {
                        "id": item[0],
                        "description": item[2],
                        "quantity": item[3],
                        "unit_price": item[4],
                        "tax_rate": item[5],
                        "total": item[6]
                    } for item in items
                ]
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def mark_paid(self, invoice_id: int, payment_id: str) -> Dict:
        """
        Day 22 Feature: Mark invoice as paid
        
        Args:
            invoice_id: Invoice ID
            payment_id: Razorpay payment ID
        
        Returns:
            Update status
        """
        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            
            paid_date = datetime.now()
            
            c.execute('''
                UPDATE invoices 
                SET status = 'paid', paid_date = ?, payment_id = ?
                WHERE id = ?
            ''', (paid_date, payment_id, invoice_id))
            
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "invoice_id": invoice_id,
                "status": "paid",
                "paid_date": paid_date.isoformat()
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_user_invoices(self, user_id: str) -> List[Dict]:
        """
        Day 22 Feature: Get all invoices for a user
        
        Args:
            user_id: User ID
        
        Returns:
            List of user invoices
        """
        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            
            c.execute('SELECT * FROM invoices WHERE user_id = ? ORDER BY issue_date DESC', (user_id,))
            invoices = c.fetchall()
            
            conn.close()
            
            return [
                {
                    "id": inv[0],
                    "invoice_number": inv[1],
                    "amount": inv[5],
                    "plan": inv[7],
                    "status": inv[8],
                    "issue_date": inv[9],
                    "due_date": inv[10],
                    "paid_date": inv[11]
                } for inv in invoices
            ]
        
        except Exception as e:
            return []
    
    def generate_invoice_html(self, invoice_id: int) -> str:
        """
        Day 22 Feature: Generate invoice as HTML
        
        Args:
            invoice_id: Invoice ID
        
        Returns:
            HTML invoice
        """
        try:
            invoice_data = self.get_invoice(invoice_id)
            
            if not invoice_data["success"]:
                return "<h1>Invoice not found</h1>"
            
            inv = invoice_data["invoice"]
            items = invoice_data["items"]
            
            total_amount = sum(item["total"] for item in items)
            
            html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .header {{ text-align: center; margin-bottom: 30px; }}
                    .invoice-number {{ color: #2c3e50; font-size: 24px; margin: 10px 0; }}
                    .invoice-date {{ color: #7f8c8d; font-size: 12px; }}
                    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                    th {{ background-color: #34495e; color: white; padding: 10px; text-align: left; }}
                    td {{ padding: 8px; border-bottom: 1px solid #bdc3c7; }}
                    .total {{ font-weight: bold; font-size: 18px; color: #27ae60; }}
                    .status {{ padding: 5px 10px; border-radius: 3px; font-weight: bold; }}
                    .status.paid {{ background-color: #d5f4e6; color: #27ae60; }}
                    .status.pending {{ background-color: #fdebd0; color: #d68910; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>Invoice</h1>
                    <div class="invoice-number">{inv['invoice_number']}</div>
                    <div class="invoice-date">Issue Date: {inv['issue_date'][:10]}</div>
                </div>
                
                <div>
                    <strong>Invoice Details:</strong><br>
                    User ID: {inv['user_id']}<br>
                    Plan: {inv['plan']}<br>
                    Status: <span class="status {inv['status']}">{inv['status'].upper()}</span>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th>Description</th>
                            <th>Quantity</th>
                            <th>Unit Price</th>
                            <th>Total</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for item in items:
                html += f"""
                        <tr>
                            <td>{item['description']}</td>
                            <td>{item['quantity']}</td>
                            <td>₹{item['unit_price']:.2f}</td>
                            <td>₹{item['total']:.2f}</td>
                        </tr>
                """
            
            html += f"""
                    </tbody>
                </table>
                
                <div style="text-align: right; margin-top: 20px;">
                    <div class="total">Total: ₹{total_amount:.2f}</div>
                </div>
            </body>
            </html>
            """
            
            return html
        
        except Exception as e:
            return f"<h1>Error generating invoice: {e}</h1>"


    def get_user_payments(self, user_id: str) -> List[Dict]:
        """
        Day 22 Feature: Get all payments for a user (alias for invoices)
        
        Args:
            user_id: User ID
        
        Returns:
            List of user payments/invoices
        """
        return self.get_user_invoices(user_id)


# Global instance
invoice_service = InvoiceService()
invoice_service.init_db()
