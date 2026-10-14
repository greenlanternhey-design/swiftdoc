from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

app = FastAPI(
    title="SMB Document & Tax Compliance Engine",
    description="Vercel serverless production build.",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json"
)

# --- IN-MEMORY DATABASE SCHEMAS ---
class Business(BaseModel):
    id: int
    name: str
    tax_region: str

class DocumentMetadata(BaseModel):
    vendor_name: Optional[str] = None
    total_amount: Optional[float] = None
    issue_date: Optional[str] = None
    detected_tax_amount: Optional[float] = None

class Document(BaseModel):
    id: int
    business_id: int
    doc_type: str = Field(..., description="bill, receipt, or invoice")
    storage_url: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[DocumentMetadata] = None

class TaxDeadline(BaseModel):
    id: int
    region: str
    tax_type: str
    due_date: str

class NotificationLog(BaseModel):
    id: int
    business_id: int
    message: str
    channel: str
    sent_at: datetime

# Mock Storage Engines
db_businesses = []
db_documents = []
db_deadlines = [
    {"id": 1, "region": "US-CA", "tax_type": "Sales Tax", "due_date": "2026-11-15"},
    {"id": 2, "region": "US-NY", "tax_type": "Corporate Tax", "due_date": "2026-12-01"}
]

# --- API ROUTE ENDPOINTS ---
@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "SMB Ledger Cloud Engine",
        "documentation": "/api/docs"
    }

@app.post("/api/businesses", response_model=Business)
def create_business(business: Business):
    if any(b['id'] == business.id for b in db_businesses):
        raise HTTPException(status_code=400, detail="Business ID already registered.")
    db_businesses.append(business.dict())
    return business

@app.post("/api/documents/upload", response_model=Document)
def upload_document(doc_id: int, business_id: int, type_of_doc: str, file_mock_url: str):
    # Simulated OCR extraction matching our core processing design rules
    simulated_metadata = DocumentMetadata(
        vendor_name="Global Vendor Enterprise",
        total_amount=1250.75,
        issue_date="2026-10-14",
        detected_tax_amount=100.06
    )
    
    new_doc = Document(
        id=doc_id,
        business_id=business_id,
        doc_type=type_of_doc,
        storage_url=file_mock_url,
        metadata=simulated_metadata
    )
    db_documents.append(new_doc.dict())
    return new_doc

@app.get("/api/tax/deadlines", response_model=List[TaxDeadline])
def get_tax_deadlines(region: Optional[str] = None):
    if region:
        return [d for d in db_deadlines if d['region'] == region]
    return db_deadlines

@app.post("/api/tax/cron-dispatch")
def trigger_notification_dispatcher():
    dispatched_alerts = []
    for deadline in db_deadlines:
        alert_msg = f"REMINDER: Your local {deadline['tax_type']} submission boundary expires on {deadline['due_date']}."
        dispatched_alerts.append({
            "target_region": deadline['region'],
            "dispatched_channels": ["Email", "SMS Gateway", "Push Notification Hub"],
            "payload_message": alert_msg,
            "status": "Dispatched Successfully"
        })
    return {"cron_status": "Batch complete", "alerts_sent": dispatched_alerts}
