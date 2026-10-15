import os

PLANS = {
    "starter": {
        "gumroad_id": os.getenv("GUMROAD_STARTER_ID"),
        "docs_per_month": 100,
        "features": {"extract", "deadlines"},
    },
    "practice": {
        "gumroad_id": os.getenv("GUMROAD_PRACTICE_ID"),
        "docs_per_month": 1000,
        "features": {"extract", "deadlines", "export", "multi_client"},
    },
    "enterprise": {
        "gumroad_id": os.getenv("GUMROAD_ENTERPRISE_ID"),
        "docs_per_month": 10000,  # Or flag as a custom high limit
        "features": {"extract", "deadlines", "export", "multi_client", "api_access", "priority_support"},
    },
}
