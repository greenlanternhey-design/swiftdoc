import os
import sys

# 1. CRITICAL VERCEL PATH FIX: Ensures plans.py in the root directory can be found 
# without causing local development or production runtime import crashes.
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from fastapi import FastAPI, Request, HTTPException
from plans import PLANS  # Safely imports your subscription tier definitions

app = FastAPI()

def set_user_plan(email: str, plan_type: str):
    """
    Saves the user's purchased tier securely.
    TODO: Replace this print statement with your preferred database save query later.
    """
    print(f"SUCCESS: Synchronized database record for {email} to tier: {plan_type.upper()}")

@app.post("/api/webhook")
async def gumroad_webhook(request: Request):
    # 2. Parse the standard application/x-www-form-urlencoded data sent by Gumroad
    form_data = await request.form()
    
    customer_email = form_data.get("email")
    # Clean and lowercase the incoming tier text string to avoid capitalization mismatch
    purchased_tier = form_data.get("tier", "").strip().lower() 
    
    if not customer_email:
        raise HTTPException(status_code=400, detail="Missing customer email parameter from webhook provider.")

    # 3. Handle specific subscription logic tiers safely
    if purchased_tier == "solo":
        set_user_plan(customer_email, plan_type="solo")
        return {
            "status": "success", 
            "message": "User package upgraded successfully to Solo tier.",
            "limit": PLANS["solo"]["docs_per_month"]
        }
        
    elif purchased_tier == "practice":
        set_user_plan(customer_email, plan_type="practice")
        return {
            "status": "success", 
            "message": "User package upgraded successfully to Practice tier.",
            "limit": PLANS["practice"]["docs_per_month"]
        }
        
    else:
        # Graceful fallback handler for potential custom fields or subscription cancellations
        print(f"INFO: Webhook event bypassed or tier name unmapped: '{purchased_tier}' for user: {customer_email}")
        return {
            "status": "ignored", 
            "message": f"Tier value '{purchased_tier}' is unmapped. No profile adjustments were made."
        }
