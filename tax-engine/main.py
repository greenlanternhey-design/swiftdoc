from fastapi import FastAPI, HTTPException, status
# Import the pricing configuration file you just built
import fiscal_pricing

app = FastAPI(title="DocuFiscal Core Engine")

@app.get("/billing/status")
def get_current_pricing_details():
    """Public endpoint to fetch current active prices and trial configurations."""
    return fiscal_pricing.CURRENT_PRICING_STATE

@app.post("/billing/access-check")
def generate_user_licensing_profile():
    """Processes dynamic access windows based on active trial configurations."""
    profile = fiscal_pricing.calculate_user_access_window()
    return {"status": "profile_generated", "details": profile}

# --- SYSTEM ADMIN ROUTE GATES (Keep these protected behind your auth layer) ---

@app.post("/admin/update-price")
def admin_modify_price(new_price: float):
    """Allows you to change the price dynamically at any time."""
    result = fiscal_pricing.update_product_price(new_price=new_price)
    return result

@app.post("/admin/toggle-trial")
def admin_modify_trial(active: bool, days: int = 7):
    """Allows you to turn free trials on and off time after time."""
    result = fiscal_pricing.configure_free_trial(active=active, duration_days=days)
    return result
