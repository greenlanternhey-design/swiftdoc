import os
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field

# --- SECURITY MANAGER ---
# Replace this string with a highly secure random password of your choice
ADMIN_SECRET_API_KEY = "DocuFiscal_Admin_Secret_Pass_99x"

class PricingTier(BaseModel):
    tier_name: str = "Enterprise Edition"
    base_price_usd: float = 200.00
    currency: str = "USD"
    is_free_trial_active: bool = False
    free_trial_days: int = Field(default=0, ge=0)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

CURRENT_PRICING_STATE = {
    "annual_license": PricingTier(
        tier_name="DocuFiscal Enterprise Tier",
        base_price_usd=200.00,
        is_free_trial_active=False,
        free_trial_days=0
    )
}

def update_product_price(new_price: float, key: str = "annual_license") -> dict:
    if key in CURRENT_PRICING_STATE:
        state = CURRENT_PRICING_STATE[key]
        state.base_price_usd = new_price
        state.last_updated = datetime.utcnow()
        return {"status": "price_updated", "current_tier": state}
    return {"status": "error", "message": "Target billing tier not found."}

def configure_free_trial(active: bool, duration_days: int = 7, key: str = "annual_license") -> dict:
    if key in CURRENT_PRICING_STATE:
        state = CURRENT_PRICING_STATE[key]
        state.is_free_trial_active = active
        state.free_trial_days = duration_days if active else 0
        state.last_updated = datetime.utcnow()
        return {"status": "trial_state_changed", "current_tier": state}
    return {"status": "error", "message": "Target billing tier not found."}

def calculate_user_access_window(key: str = "annual_license") -> dict:
    state = CURRENT_PRICING_STATE[key]
    start_date = datetime.utcnow()
    
    if state.is_free_trial_active:
        expiration_date = start_date + timedelta(days=state.free_trial_days)
        access_type = "free_trial"
    else:
        expiration_date = start_date + timedelta(days=365)
        access_type = "paid_annual_license"
        
    return {
        "access_type": access_type,
        "activated_at": start_date,
        "expires_at": expiration_date,
        "cost_processed": 0.00 if state.is_free_trial_active else state.base_price_usd
    }
    
import os
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field

# --- CONFIGURATION DATA STRUCTURES ---

class PricingTier(BaseModel):
    """Blueprint layout representing a dynamic billing gateway structure."""
    tier_name: str = "Enterprise Edition"
    base_price_usd: float = 200.00
    currency: str = "USD"
    is_free_trial_active: bool = False
    free_trial_days: int = Field(default=0, ge=0)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

# --- IN-MEMORY STATE ENGINE ---
# This dictionary acts as an isolated pricing cache that routes can hit instantly.
CURRENT_PRICING_STATE = {
    "annual_license": PricingTier(
        tier_name="DocuFiscal Enterprise Tier",
        base_price_usd=200.00,
        is_free_trial_active=False,
        free_trial_days=0
    )
}

# --- ADMINISTRATIVE CONTROL CONTROLLERS ---

def update_product_price(new_price: float, key: str = "annual_license") -> dict:
    """Updates the target price gate value inside the operational cache."""
    if key in CURRENT_PRICING_STATE:
        state = CURRENT_PRICING_STATE[key]
        state.base_price_usd = new_price
        state.last_updated = datetime.utcnow()
        return {"status": "price_updated", "current_tier": state}
    return {"status": "error", "message": "Target billing tier not found."}

def configure_free_trial(active: bool, duration_days: int = 7, key: str = "annual_license") -> dict:
    """Toggles free trial configurations dynamically time after time."""
    if key in CURRENT_PRICING_STATE:
        state = CURRENT_PRICING_STATE[key]
        state.is_free_trial_active = active
        state.free_trial_days = duration_days if active else 0
        state.last_updated = datetime.utcnow()
        return {"status": "trial_state_changed", "current_tier": state}
    return {"status": "error", "message": "Target billing tier not found."}

def calculate_user_access_window(key: str = "annual_license") -> dict:
    """Evaluates active variables to generate access start and expiration dates."""
    state = CURRENT_PRICING_STATE[key]
    start_date = datetime.utcnow()
    
    if state.is_free_trial_active:
        # User is placed into a temporary access window based on your current configurations
        expiration_date = start_date + timedelta(days=state.free_trial_days)
        access_type = "free_trial"
    else:
        # Standard full license access window configuration
        expiration_date = start_date + timedelta(days=365)
        access_type = "paid_annual_license"
        
    return {
        "access_type": access_type,
        "activated_at": start_date,
        "expires_at": expiration_date,
        "cost_processed": 0.00 if state.is_free_trial_active else state.base_price_usd
    }
