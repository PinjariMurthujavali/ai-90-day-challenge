# ============================================
# Day 22: Razorpay Payment Integration
# Advanced payment processing with Razorpay
# ============================================

import os
import json
import hashlib
import hmac
import requests
from datetime import datetime
from typing import Dict, Optional, List
import sqlite3

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_API_URL = "https://api.razorpay.com/v1"

# Payment Plans for Day 22
PAYMENT_PLANS = {
    "free": {"name": "Free", "price": 0, "features": ["10 chats/day", "Basic support"]},
    "pro": {"name": "Pro", "price": 500, "features": ["Unlimited chats", "Priority support", "Advanced analytics"]},
    "premium": {"name": "Premium", "price": 1500, "features": ["Unlimited everything", "API access", "Dedicated support"]},
}

class RazorpayService:
    """Day 22: Razorpay payment processing"""
    
    def __init__(self):
        self.key_id = RAZORPAY_KEY_ID
        self.key_secret = RAZORPAY_KEY_SECRET
        self.api_url = RAZORPAY_API_URL
        self.auth = (self.key_id, self.key_secret)
    
    def is_configured(self) -> bool:
        """Check if Razorpay is properly configured"""
        return bool(self.key_id and self.key_secret)
    
    def create_order(self, user_id: str, plan: str, email: str, phone: str) -> Dict:
        """
        Day 22 Feature: Create a Razorpay payment order
        
        Args:
            user_id: User identifier
            plan: Payment plan (free, pro, premium)
            email: User email
            phone: User phone number
        
        Returns:
            Order details with order_id
        """
        if not self.is_configured():
            return {"error": "Razorpay not configured"}
        
        if plan not in PAYMENT_PLANS:
            return {"error": f"Invalid plan: {plan}"}
        
        plan_info = PAYMENT_PLANS[plan]
        amount = int(plan_info["price"] * 100)  # Convert to paise
        
        if amount == 0:  # Free plan
            return {
                "order_id": f"free_{user_id}_{datetime.now().timestamp()}",
                "amount": 0,
                "currency": "INR",
                "plan": plan,
                "status": "approved",
                "created_at": datetime.now().isoformat()
            }
        
        try:
            payload = {
                "amount": amount,
                "currency": "INR",
                "receipt": f"receipt_{user_id}_{datetime.now().timestamp()}",
                "notes": {
                    "user_id": user_id,
                    "plan": plan,
                    "email": email,
                    "phone": phone
                }
            }
            
            response = requests.post(
                f"{self.api_url}/orders",
                auth=self.auth,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "order_id": data["id"],
                    "amount": data["amount"],
                    "currency": data["currency"],
                    "receipt": data["receipt"],
                    "status": "created",
                    "created_at": datetime.now().isoformat()
                }
            else:
                return {"error": f"Failed to create order: {response.text}"}
        
        except Exception as e:
            return {"error": str(e)}
    
    def verify_payment(self, order_id: str, payment_id: str, signature: str) -> bool:
        """
        Day 22 Feature: Verify Razorpay payment signature
        
        Args:
            order_id: Razorpay order ID
            payment_id: Razorpay payment ID
            signature: Razorpay signature from webhook
        
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.is_configured():
            return False
        
        try:
            message = f"{order_id}|{payment_id}"
            generated_signature = hmac.new(
                self.key_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return generated_signature == signature
        except Exception as e:
            print(f"Signature verification error: {e}")
            return False
    
    def capture_payment(self, payment_id: str, amount: int) -> Dict:
        """
        Day 22 Feature: Capture authorized payment
        
        Args:
            payment_id: Razorpay payment ID
            amount: Amount in paise
        
        Returns:
            Capture status
        """
        if not self.is_configured():
            return {"error": "Razorpay not configured"}
        
        try:
            response = requests.post(
                f"{self.api_url}/payments/{payment_id}/capture",
                auth=self.auth,
                json={"amount": amount},
                timeout=10
            )
            
            if response.status_code == 200:
                return {"status": "captured", "data": response.json()}
            else:
                return {"error": f"Capture failed: {response.text}"}
        
        except Exception as e:
            return {"error": str(e)}
    
    def refund_payment(self, payment_id: str, amount: Optional[int] = None) -> Dict:
        """
        Day 22 Feature: Refund a payment
        
        Args:
            payment_id: Razorpay payment ID
            amount: Amount to refund in paise (None for full refund)
        
        Returns:
            Refund status
        """
        if not self.is_configured():
            return {"error": "Razorpay not configured"}
        
        try:
            payload = {}
            if amount:
                payload["amount"] = amount
            
            response = requests.post(
                f"{self.api_url}/payments/{payment_id}/refund",
                auth=self.auth,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return {"status": "refunded", "data": response.json()}
            else:
                return {"error": f"Refund failed: {response.text}"}
        
        except Exception as e:
            return {"error": str(e)}
    
    def get_payment_details(self, payment_id: str) -> Dict:
        """
        Day 22 Feature: Get payment details
        
        Args:
            payment_id: Razorpay payment ID
        
        Returns:
            Payment details
        """
        if not self.is_configured():
            return {"error": "Razorpay not configured"}
        
        try:
            response = requests.get(
                f"{self.api_url}/payments/{payment_id}",
                auth=self.auth,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Failed to fetch payment: {response.text}"}
        
        except Exception as e:
            return {"error": str(e)}
    
    def get_order_details(self, order_id: str) -> Dict:
        """
        Day 22 Feature: Get order details
        
        Args:
            order_id: Razorpay order ID
        
        Returns:
            Order details
        """
        if not self.is_configured():
            return {"error": "Razorpay not configured"}
        
        try:
            response = requests.get(
                f"{self.api_url}/orders/{order_id}",
                auth=self.auth,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Failed to fetch order: {response.text}"}
        
        except Exception as e:
            return {"error": str(e)}
    
    def list_payments(self, count: int = 10, skip: int = 0) -> Dict:
        """
        Day 22 Feature: List all payments
        
        Args:
            count: Number of payments to fetch
            skip: Number of payments to skip
        
        Returns:
            List of payments
        """
        if not self.is_configured():
            return {"error": "Razorpay not configured"}
        
        try:
            response = requests.get(
                f"{self.api_url}/payments",
                auth=self.auth,
                params={"count": count, "skip": skip},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Failed to fetch payments: {response.text}"}
        
        except Exception as e:
            return {"error": str(e)}


# Global instance
razorpay = RazorpayService()


# ============================================
# Helper Functions for Day 22
# ============================================

def get_payment_plans() -> Dict:
    """Get all available payment plans"""
    return PAYMENT_PLANS

def format_amount(amount_paise: int) -> str:
    """Format paise amount to INR"""
    return f"₹{amount_paise / 100:.2f}"

def get_razorpay_keys() -> Dict:
    """Get Razorpay configuration keys"""
    return {
        "key_id": RAZORPAY_KEY_ID,
        "app_url": os.getenv("APP_URL", "http://localhost:8501")
    }

def verify_and_finalize(user_id: str, plan: str, order_id: str, payment_id: str, signature: str) -> tuple:
    """
    Day 22 Feature: Verify payment and upgrade user plan
    
    Args:
        user_id: User ID
        plan: Plan to upgrade to
        order_id: Razorpay order ID
        payment_id: Razorpay payment ID
        signature: Razorpay signature
    
    Returns:
        Tuple of (success: bool, message: str, payment_data: dict)
    """
    # Verify signature
    if not razorpay.verify_payment(order_id, payment_id, signature):
        return False, "Invalid payment signature", None
    
    try:
        # Get payment details
        payment_data = razorpay.get_payment_details(payment_id)
        
        if "error" in payment_data:
            return False, "Could not verify payment", None
        
        # Update user plan in database
        try:
            import database
            database.update_user_plan(user_id, plan)
            
            # Create invoice
            from invoice_service import invoice_service
            amount = payment_data.get("amount", 0) / 100
            inv_result = invoice_service.create_invoice(user_id, order_id, amount, plan, payment_id)
            
            if inv_result.get("success"):
                return True, f"Successfully upgraded to {plan} plan", payment_data
            else:
                return True, f"Plan upgraded but invoice creation failed: {inv_result.get('error')}", payment_data
        
        except Exception as e:
            return False, f"Database update failed: {str(e)}", payment_data
    
    except Exception as e:
        return False, f"Payment verification failed: {str(e)}", None
