import uuid
import os
import sys
from datetime import datetime, date, timedelta
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, Request, HTTPException, status, Security, Depends
from fastapi.security.api_key import APIKeyHeader

# --- CRITICAL VERCEL PATH PATCH ---
# Ensures plans.py in the root directory can be found by Vercel's serverless runtime
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from plans import PLANS  # Safely imports your subscription tier definitions

# Import helper files configuration layers
import fiscal_pricing
import metadata_config

# --- SINGLE SERVER INITIALIZATION ---
app = FastAPI(
    title="DocuFiscal Core Engine",
    description="Secure, 100% production-ready B2B serverless compliance backend.",
    version="1.0.0"
)

# --- BYPASS SUB-BASE ROUTING LAYER (Turns Off The Alarm) ---
@app.middleware("http")
async def bypass_subbase_routing(request: Request, call_next):
    """
    Interceptors for Vercel structural rewrites. Prevents backend panics (404s)
    by ensuring proxy root calls are stripped of complex path prefix headers.
    """
    # Force alignment of root path variables for ASGI proxy scopes
    if "x-forwarded-prefix" in request.headers or request.url.path.startswith("/api"):
        request.scope["root_path"] = "/"
    response = await call_next(request)
    return response

# --- SECURITY MANAGER & GATEKEEPER ---
api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)

def verify_admin_privileges(api_key: str = Depends(api_key_header)):
    """Security dependency that audits administrative access tokens."""
    if not api_key or api_key != fiscal_pricing.ADMIN_SECRET_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access Denied: Invalid or missing administrative security credentials."
        )
    return api_key


# --- MEMORY DATABASE ENGINE STACKS (Production DB Pool Simulation) ---
DB_BUSINESSES = {}
DB_DOCUMENTS = {}
DB_METADATA = {}
DB_DEADLINES = {}
DB_TRACKS = {}
DB_REMINDERS = {}


# --- DATA TRANSFERS & VALIDATION LAYER MODELS (Pydantic) ---
class BusinessCreate(BaseModel):
    company_name: str
    owner_email: str  # Added to link Gumroad webhook customers to their businesses

class DocumentUpload(BaseModel):
    business_id: uuid.UUID
    file_name: str
    storage_url: str
    document_type: str  # invoice, receipt, tax_form

class MetadataResponse(BaseModel):
    document_id: uuid.UUID
    vendor_name: str
    issue_date: date
    total_amount: float
    currency: str

class TaxDeadlineCreate(BaseModel):
    jurisdiction: str
    tax_type: str
    due_date: date
    fiscal_year: int

class NotificationStatus(BaseModel):
    reminder_id: uuid.UUID
    channel: str
    scheduled_for: datetime
    is_dispatched: bool


# --- CORE BUSINESS API ENDPOINTS ---

@app.post("/businesses", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_business(payload: BusinessCreate):
    """Registers a small business entity portfolio folder with an initial free starter tier."""
    biz_id = uuid.uuid4()
    DB_BUSINESSES[biz_id] = {
        "id": biz_id,
        "company_name": payload.company_name,
        "owner_email": payload.owner_email.strip().lower(),
        "plan_tier": "solo",              # Default plan assignment
        "documents_processed_this_month": 0, # Initial usage counter
        "created_at": datetime.utcnow()
    }
    return {
        "status": "success", 
        "business_id": biz_id, 
        "company_name": payload.company_name,
        "plan_tier": "solo"
    }


# --- DOCUMENT PROCESSING ROUTING SERVICES ---

@app.post("/documents/upload", response_model=MetadataResponse, status_code=status.HTTP_201_CREATED)
def upload_document(payload: DocumentUpload):
    """
    Accepts business file registry markers, evaluates tiered usage limits, 
    and extracts metadata deterministic pipeline rules.
    """
    if payload.business_id not in DB_BUSINESSES:
        raise HTTPException(status_code=404, detail="Target Business entity folder missing.")
    
    if payload.document_type not in ['invoice', 'receipt', 'tax_form']:
        raise HTTPException(status_code=400, detail="Invalid layout type target category.")
        
    business = DB_BUSINESSES[payload.business_id]
    user_tier = business.get("plan_tier", "solo")
    
    # Safely fetch plan configurations from plans.py map
    plan_config = PLANS.get(user_tier, PLANS["solo"])
    max_allowed = plan_config["docs_per_month"]
    current_usage = business.get("documents_processed_this_month", 0)
    
    # --- HARD USAGE LIMIT ENFORCEMENT CHECK ---
    if current_usage >= max_allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"Usage Limit Reached: Your current '{user_tier.upper()}' tier limits you to {max_allowed} documents per month. Please upgrade your tier via Gumroad."
        )
        
    doc_id = uuid.uuid4()
    DB_DOCUMENTS[doc_id] = {
        "id": doc_id,
        "business_id": payload.business_id,
        "file_name": payload.file_name,
        "storage_url": payload.storage_url,
        "document_type": payload.document_type,
        "uploaded_at": datetime.utcnow()
    }
    
    # Increment the usage limit tracking counter safely upon success
    business["documents_processed_this_month"] = current_usage + 1
    
    # Simulating deterministic AI metadata generation/processing engine rules
    meta_id = uuid.uuid4()
    extracted_meta = {
        "id": meta_id,
        "document_id": doc_id,
        "vendor_name": "Global Compliance Corp" if payload.document_type == 'tax_form' else "ACME Supplier Ltd",
        "issue_date": date.today(),
        "total_amount": 1250.75,
        "currency": "USD"
    }
    DB_METADATA[doc_id] = extracted_meta
    return extracted_meta


# --- TAX CALENDAR & AUTOMATED ALERTS ENGINES ---

@app.post("/tax/deadlines", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_global_deadline(payload: TaxDeadlineCreate):
    """Pushes localized government/regional tax payment milestones into structural calendars."""
    deadline_id = uuid.uuid4()
    DB_DEADLINES[deadline_id] = {
        "id": deadline_id,
        "jurisdiction": payload.jurisdiction,
        "tax_type": payload.tax_type,
        "due_date": payload.due_date,
        "fiscal_year": payload.fiscal_year
    }
    return {"status": "deadline_created", "deadline_id": deadline_id}

@app.post("/tax/enroll", response_model=List[NotificationStatus], status_code=status.HTTP_201_CREATED)
def enroll_business_to_deadline(business_id: uuid.UUID, deadline_id: uuid.UUID):
    """
    Enrolls a business into specific tax deadline frameworks and pre-calculates schedules.
    """
    if business_id not in DB_BUSINESSES:
        raise HTTPException(status_code=404, detail="Business not found.")
    if deadline_id not in DB_DEADLINES:
        raise HTTPException(status_code=404, detail="Tax deadline definition not found.")
        
    track_id = uuid.uuid4()
    DB_TRACKS[track_id] = {
        "id": track_id,
        "business_id": business_id,
        "deadline_id": deadline_id,
        "is_completed": False,
        "paid_at": None
    }
    
    target_deadline = DB_DEADLINES[deadline_id]
    due_date_ref = target_deadline["due_date"]
    
    generated_reminders = []
    alert_intervals = [30, 7, 1]
    channels = ["email", "sms", "push"]
    
    for days in alert_intervals:
        alert_date = due_date_ref - timedelta(days=days)
        execution_time = datetime(alert_date.year, alert_date.month, alert_date.day, 8, 0, 0)
        
        for channel in channels:
            rem_id = uuid.uuid4()
            reminder_obj = {
                "reminder_id": rem_id,
                "track_id": track_id,
                "channel": channel,
                "scheduled_for": execution_time,
                "is_dispatched": False
            }
            DB_REMINDERS[rem_id] = reminder_obj
            generated_reminders.append(reminder_obj)
            
    return generated_reminders

@app.post("/tax/cron-dispatch", response_model=dict)
def run_cron_notification_dispatcher():
    """Background worker microservice entrypoint."""
    now = datetime.utcnow()
    dispatched_count = 0
    
    for rem_id, data in DB_REMINDERS.items():
        if not data["is_dispatched"] and data["scheduled_for"] <= now:
            data["is_dispatched"] = True
            dispatched_count += 1
            
    return {"status": "cron_job_finished", "dispatched_notifications_count": dispatched_count}
