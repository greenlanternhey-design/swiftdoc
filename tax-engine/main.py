"""
SMB Ledger & Tax Scheduler Engine  +  DocuFiscal billing sub-application.

Deploy target: Vercel (@vercel/python). The ASGI app is the top-level `app`.

Environment variables
---------------------
ADMIN_API_KEY              Required. Clients send header  X-API-Key: <value>
CRON_SECRET                Required for Vercel cron (Vercel sends Authorization: Bearer <value>)
SENDGRID_API_KEY           Optional. Needed to really send reminder emails.
SENDER_EMAIL               Optional. Verified sender address in SendGrid.
GUMROAD_ACCESS_TOKEN       Optional. Needed for /api/gumroad/sync.
UPSTASH_REDIS_REST_URL     Optional but recommended on Vercel (persistent storage).
UPSTASH_REDIS_REST_TOKEN   (KV_REST_API_URL / KV_REST_API_TOKEN are also accepted.)
SUPABASE_URL               Optional. Keep-alive ping so the project is not paused.
SUPABASE_KEY               Optional. Anon or service key.
SUPABASE_KEEPALIVE_TABLE   Optional. Any small table name (more reliable ping).
"""

import hmac
import html
import json
import logging
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Pricing module: use the project's own fiscal_pricing.py if it can be imported,
# otherwise fall back to a small built-in implementation so the app still boots.
# ---------------------------------------------------------------------------
try:
    import fiscal_pricing as _pricing
except Exception:
    _pricing = None

logger = logging.getLogger("smb_engine")
logging.basicConfig(level=logging.INFO)

REMINDER_INTERVALS_DAYS = (30, 7, 1)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class _FallbackPricing:
    """Minimal stand-in used only when fiscal_pricing.py cannot be imported."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.CURRENT_PRICING_STATE: Dict[str, Any] = {
            "product": "DocuFiscal",
            "price": 49.0,
            "currency": "USD",
            "trial_enabled": True,
            "trial_days": 14,
        }

    def calculate_user_access_window(self) -> Dict[str, Any]:
        start = datetime.now(timezone.utc)
        days = self.CURRENT_PRICING_STATE["trial_days"] if self.CURRENT_PRICING_STATE["trial_enabled"] else 0
        return {
            "access_starts_at": start.isoformat(),
            "access_ends_at": (start + timedelta(days=days)).isoformat(),
            "trial_enabled": self.CURRENT_PRICING_STATE["trial_enabled"],
            "price": self.CURRENT_PRICING_STATE["price"],
            "currency": self.CURRENT_PRICING_STATE["currency"],
        }

    def update_product_price(self, new_price: float) -> Dict[str, Any]:
        with self._lock:
            self.CURRENT_PRICING_STATE["price"] = new_price
            return dict(self.CURRENT_PRICING_STATE)

    def toggle_trial(self, enabled: Optional[bool] = None) -> Dict[str, Any]:
        with self._lock:
            current = self.CURRENT_PRICING_STATE["trial_enabled"]
            self.CURRENT_PRICING_STATE["trial_enabled"] = (not current) if enabled is None else enabled
            return dict(self.CURRENT_PRICING_STATE)


pricing = _pricing if _pricing is not None else _FallbackPricing()

# ---------------------------------------------------------------------------
# 1. Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SMB Ledger & Tax Scheduler Engine",
    version="2.1.0",
    description="Serverless backend: businesses, documents, tax deadlines, email reminders, Gumroad sync.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


# ---------------------------------------------------------------------------
# 2. Sub-base routing bypass: strips proxy prefixes and neutralizes root_path
#    so rewritten Vercel/proxy paths never cause 404s.
# ---------------------------------------------------------------------------
@app.middleware("http")
async def bypass_subbase_routing(request: Request, call_next):
    scope = request.scope
    prefix = request.headers.get("x-forwarded-prefix", "").rstrip("/")
    if prefix and scope["path"].startswith(prefix + "/"):
        scope["path"] = scope["path"][len(prefix):]
        raw = scope.get("raw_path")
        if raw and raw.startswith(prefix.encode() + b"/"):
            scope["raw_path"] = raw[len(prefix):]
    scope["root_path"] = ""
    return await call_next(request)


# ---------------------------------------------------------------------------
# 3. Security dependencies (fail closed when secrets are not configured)
# ---------------------------------------------------------------------------
def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = os.environ.get("ADMIN_API_KEY")
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ADMIN_API_KEY is not configured on the server.")
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing X-API-Key header.")


def require_cron_or_api_key(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> None:
    """Accepts Vercel cron (Bearer CRON_SECRET) or a manual call with the admin key."""
    cron_secret = os.environ.get("CRON_SECRET")
    admin_key = os.environ.get("ADMIN_API_KEY")
    if not cron_secret and not admin_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Neither CRON_SECRET nor ADMIN_API_KEY is configured.")
    if cron_secret and authorization and hmac.compare_digest(authorization, f"Bearer {cron_secret}"):
        return
    if admin_key and x_api_key and hmac.compare_digest(x_api_key, admin_key):
        return
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unauthorized trigger.")


# ---------------------------------------------------------------------------
# 4. Persistence layer: Upstash/Vercel KV (REST) when configured, /tmp otherwise.
#    NOTE: /tmp is per-instance and ephemeral on Vercel; use Upstash for real data.
# ---------------------------------------------------------------------------
STATE_KEY = "smb_ledger_state"
DATA_FILE = os.environ.get("LOCAL_STATE_FILE", "/tmp/smb_ledger_store.json")
_state_lock = threading.RLock()


def _redis_config():
    url = os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN")
    return (url, token) if url and token else (None, None)


def _redis(command: list) -> Any:
    url, token = _redis_config()
    req = urllib.request.Request(
        url,
        data=json.dumps(command).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if "error" in payload:
        raise RuntimeError(f"Redis error: {payload['error']}")
    return payload.get("result")


def _default_state() -> Dict[str, Any]:
    deadline_id = str(uuid.uuid4())
    return {
        "businesses": {},
        "documents": {},
        "metadata": {},
        "usage": {},
        "reminders": {},
        "deadlines": {
            deadline_id: {
                "id": deadline_id,
                "jurisdiction": "US-Federal",
                "tax_type": "Quarterly Estimated Tax",
                "due_date": "2026-11-15",
                "fiscal_year": 2026,
            }
        },
    }


def _normalize(state: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("businesses", "documents", "metadata", "usage", "reminders", "deadlines"):
        state.setdefault(key, {})
    return state


def load_system_state() -> Dict[str, Any]:
    with _state_lock:
        if _redis_config()[0]:
            raw = _redis(["GET", STATE_KEY])
            if raw:
                return _normalize(json.loads(raw))
            state = _default_state()
            _redis(["SET", STATE_KEY, json.dumps(state)])
            return state
        if not os.path.exists(DATA_FILE):
            state = _default_state()
            save_system_state(state)
            return state
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return _normalize(json.load(f))


def save_system_state(state: Dict[str, Any]) -> None:
    with _state_lock:
        if _redis_config()[0]:
            _redis(["SET", STATE_KEY, json.dumps(state)])
            return
        tmp_path = f"{DATA_FILE}.{uuid.uuid4().hex}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp_path, DATA_FILE)


@contextmanager
def state_txn():
    """Load -> mutate -> save, serialized within one instance."""
    with _state_lock:
        try:
            state = load_system_state()
        except Exception as exc:
            logger.exception("State load failed")
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Storage backend unavailable.") from exc
        yield state
        try:
            save_system_state(state)
        except Exception as exc:
            logger.exception("State save failed")
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Storage backend unavailable.") from exc


# ---------------------------------------------------------------------------
# 5. Email layer (SendGrid)
# ---------------------------------------------------------------------------
def send_live_email_alert(recipient_email: str, subject: str, html_content: str) -> bool:
    api_key = os.environ.get("SENDGRID_API_KEY")
    sender_email = os.environ.get("SENDER_EMAIL")
    if not api_key or not sender_email:
        logger.warning("SendGrid not configured; reminder to %s left queued.", recipient_email)
        return False

    payload = {
        "personalizations": [{"to": [{"email": recipient_email}]}],
        "from": {"email": sender_email, "name": "SMB Ledger Compliance Platform"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_content}],
    }
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Vercel-Python-Agent",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 202)
    except Exception as exc:
        logger.error("SendGrid delivery failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# 6. Supabase keep-alive (prevents free-tier project pausing)
# ---------------------------------------------------------------------------
def supabase_keepalive() -> Dict[str, Any]:
    """Real request against Supabase so the project counts as active. Never raises."""
    base = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not base or not key:
        return {"supabase": "not_configured"}
    table = os.environ.get("SUPABASE_KEEPALIVE_TABLE", "")
    path = f"/rest/v1/{table}?select=*&limit=1" if table else "/rest/v1/"
    req = urllib.request.Request(
        base.rstrip("/") + path,
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return {"supabase": "pinged", "http_status": resp.status}
    except urllib.error.HTTPError as exc:
        return {"supabase": "responded", "http_status": exc.code}
    except Exception as exc:
        logger.error("Supabase keep-alive failed: %s", type(exc).__name__)
        return {"supabase": "unreachable"}


# ---------------------------------------------------------------------------
# 7. Schemas
# ---------------------------------------------------------------------------
class BusinessCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    owner_email: str

    @field_validator("company_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("company_name cannot be blank")
        return v

    @field_validator("owner_email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip()
        if not EMAIL_RE.match(v):
            raise ValueError("owner_email is not a valid email address")
        return v


class DocumentUpload(BaseModel):
    business_id: str
    file_name: str = Field(..., min_length=1, max_length=255)
    storage_url: str
    document_type: Literal["invoice", "receipt", "tax_form"] = Field(
        ..., description="must be: invoice, receipt, or tax_form"
    )

    @field_validator("storage_url")
    @classmethod
    def _valid_url(cls, v: str) -> str:
        if not v.lower().startswith(("http://", "https://")):
            raise ValueError("storage_url must start with http:// or https://")
        return v


class TaxDeadlineCreate(BaseModel):
    jurisdiction: str = Field(..., min_length=1, max_length=100)
    tax_type: str = Field(..., min_length=1, max_length=100)
    due_date: date
    fiscal_year: int = Field(..., ge=2000, le=2100)


# ---------------------------------------------------------------------------
# 8. Helpers
# ---------------------------------------------------------------------------
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def queue_reminders(state: Dict[str, Any], biz_id: str, deadline: Dict[str, Any]) -> int:
    """Create 30/7/1-day reminders for one business + deadline. Skips past dates and duplicates."""
    biz = state["businesses"][biz_id]
    due = date.fromisoformat(deadline["due_date"])
    today = utc_now().date()
    created = 0
    for days in REMINDER_INTERVALS_DAYS:
        alert_date = due - timedelta(days=days)
        if alert_date < today:
            continue
        rem_id = f"{biz_id}:{deadline['id']}:{days}"
        if rem_id in state["reminders"]:
            continue
        state["reminders"][rem_id] = {
            "id": rem_id,
            "business_id": biz_id,
            "deadline_id": deadline["id"],
            "recipient_email": biz["owner_email"],
            "message": (
                f"CRITICAL TAX REMINDER: Your {deadline['tax_type']} deadline for "
                f"{deadline['jurisdiction']} is due in {days} days ({deadline['due_date']})."
            ),
            "scheduled_date": alert_date.isoformat(),
            "is_dispatched": False,
        }
        created += 1
    return created


def dispatch_due_reminders(state: Dict[str, Any]) -> Dict[str, int]:
    today = utc_now().date().isoformat()
    sent = failed = 0
    for data in state["reminders"].values():
        if data["is_dispatched"] or data["scheduled_date"] > today:
            continue
        ok = send_live_email_alert(
            recipient_email=data["recipient_email"],
            subject="Automated Business Compliance Tax Alert",
            html_content=f"<h3>Business Alert Engine</h3><p>{html.escape(data['message'])}</p>",
        )
        if ok:
            data["is_dispatched"] = True
            data["dispatched_at"] = utc_now().isoformat()
            sent += 1
        else:
            failed += 1
    return {"dispatched": sent, "failed_or_skipped": failed}


# ---------------------------------------------------------------------------
# 9. Routes
# ---------------------------------------------------------------------------
@app.get("/")
def read_root():
    return {
        "status": "online",
        "system": "SMB Compliance Engine Master Build",
        "interactive_documentation": "/api/docs",
        "docufiscal_docs": "/docufiscal/docs",
    }


@app.get("/api/health", tags=["System Maintenance"])
def health():
    backend = "redis" if _redis_config()[0] else "local-tmp (ephemeral)"
    return {
        "status": "ok",
        "storage_backend": backend,
        "pricing_module": "fiscal_pricing" if _pricing else "built-in fallback",
    }


# --- Cron handlers (Vercel cron issues GET requests) ---
@app.get("/api/cron", tags=["System Maintenance"], dependencies=[Depends(require_cron_or_api_key)])
def vercel_daily_cron_ping():
    """Daily cron: keep-alive stamp + Supabase ping + dispatch any reminders that are due."""
    ping = supabase_keepalive()
    with state_txn() as state:
        state["metadata"]["last_cron_ping"] = utc_now().isoformat()
        result = dispatch_due_reminders(state)
    return {"status": "success", "message": "Daily cron ping executed successfully.", **result, **ping}


@app.get("/api/billing/reset-monthly-counters", tags=["System Maintenance"], dependencies=[Depends(require_cron_or_api_key)])
def reset_monthly_counters():
    """Monthly cron: reset usage counters and keep the Supabase project active."""
    ping = supabase_keepalive()
    with state_txn() as state:
        state["usage"] = {}
        state["metadata"]["last_monthly_reset"] = utc_now().isoformat()
    return {"status": "success", "message": "Monthly counters reset successfully.", **ping}


# --- Businesses ---
@app.post("/api/businesses", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_business(payload: BusinessCreate):
    biz_id = str(uuid.uuid4())
    with state_txn() as state:
        state["businesses"][biz_id] = {
            "id": biz_id,
            "company_name": payload.company_name,
            "owner_email": payload.owner_email,
            "created_at": utc_now().isoformat(),
        }
        queued = sum(queue_reminders(state, biz_id, d) for d in state["deadlines"].values())
    return {"status": "success", "business_id": biz_id, "company_name": payload.company_name, "reminders_queued": queued}


@app.get("/api/businesses", dependencies=[Depends(require_api_key)])
def list_businesses():
    state = load_system_state()
    return {"count": len(state["businesses"]), "businesses": list(state["businesses"].values())}


# --- Documents ---
@app.post("/api/documents/upload", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def upload_document(payload: DocumentUpload):
    doc_id = str(uuid.uuid4())
    with state_txn() as state:
        if payload.business_id not in state["businesses"]:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Target Business entity folder missing.")
        state["documents"][doc_id] = {
            "id": doc_id,
            "business_id": payload.business_id,
            "file_name": payload.file_name,
            "storage_url": payload.storage_url,
            "document_type": payload.document_type,
            "uploaded_at": utc_now().isoformat(),
        }
        # PLACEHOLDER extraction: replace with a real OCR / parsing step.
        extracted_meta = {
            "document_id": doc_id,
            "vendor_name": "Global Compliance Corp" if payload.document_type == "tax_form" else "ACME Supplier Ltd",
            "issue_date": utc_now().date().isoformat(),
            "total_amount": 1250.75,
            "currency": "USD",
            "extraction_mode": "placeholder",
        }
        state["metadata"][doc_id] = extracted_meta
        usage = state["usage"].setdefault(payload.business_id, {"documents_uploaded": 0})
        usage["documents_uploaded"] += 1
    return extracted_meta


# --- Tax deadlines & reminders ---
@app.post("/api/tax/deadlines", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_global_deadline(payload: TaxDeadlineCreate):
    deadline_id = str(uuid.uuid4())
    with state_txn() as state:
        deadline = {
            "id": deadline_id,
            "jurisdiction": payload.jurisdiction,
            "tax_type": payload.tax_type,
            "due_date": payload.due_date.isoformat(),
            "fiscal_year": payload.fiscal_year,
        }
        state["deadlines"][deadline_id] = deadline
        queued = sum(queue_reminders(state, biz_id, deadline) for biz_id in state["businesses"])
    return {
        "status": "deadline_created",
        "deadline_id": deadline_id,
        "reminders_queued": queued,
        "active_reminders_queued": queued > 0,
    }


@app.get("/api/tax/deadlines", dependencies=[Depends(require_api_key)])
def list_deadlines():
    state = load_system_state()
    return {
        "count": len(state["deadlines"]),
        "deadlines": sorted(state["deadlines"].values(), key=lambda d: d["due_date"]),
    }


@app.api_route("/api/tax/cron-dispatch", methods=["GET", "POST"], dependencies=[Depends(require_cron_or_api_key)])
def run_cron_notification_dispatcher():
    with state_txn() as state:
        result = dispatch_due_reminders(state)
    return {
        "status": "cron_job_finished",
        "dispatched_notifications_count": result["dispatched"],
        "failed_or_skipped": result["failed_or_skipped"],
    }


# --- Gumroad ---
@app.get("/api/gumroad/sync", dependencies=[Depends(require_api_key)])
def sync_gumroad_folder():
    token = os.environ.get("GUMROAD_ACCESS_TOKEN")
    if not token:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "GUMROAD_ACCESS_TOKEN is missing in Vercel settings.")
    url = "https://api.gumroad.com/v2/products?" + urllib.parse.urlencode({"access_token": token})
    req = urllib.request.Request(url, headers={"User-Agent": "Vercel-SMB-Engine-Agent"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            parsed = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Gumroad responded with HTTP {exc.code}.") from exc
    except Exception as exc:
        logger.error("Gumroad sync failed: %s", type(exc).__name__)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Failed to communicate with Gumroad.") from exc
    products = parsed.get("products", [])
    return {
        "sync_status": "Successful",
        "platform": "Gumroad API v2 Connected",
        "total_items_found": len(products),
        "items": products,
    }


# ---------------------------------------------------------------------------
# 10. DocuFiscal billing sub-application (mounted at /docufiscal)
# ---------------------------------------------------------------------------
sub_app = FastAPI(title="DocuFiscal Core Engine")


@sub_app.get("/status")
def get_current_pricing_details():
    return pricing.CURRENT_PRICING_STATE


@sub_app.post("/access-check")
def generate_user_licensing_profile():
    profile = pricing.calculate_user_access_window()
    return {"status": "profile_generated", "details": profile}


@sub_app.post("/update-price", dependencies=[Depends(require_api_key)])
def admin_modify_price(new_price: float):
    if new_price < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "new_price must be >= 0.")
    return pricing.update_product_price(new_price=new_price)


@sub_app.post("/toggle-trial", dependencies=[Depends(require_api_key)])
def admin_modify_trial(enabled: Optional[bool] = None):
    fn = getattr(pricing, "toggle_trial", None)
    if not callable(fn):
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "fiscal_pricing.toggle_trial is not defined.")
    return fn(enabled=enabled)


app.mount("/docufiscal", sub_app)
