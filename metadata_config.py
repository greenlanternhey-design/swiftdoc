import os
from pathlib import Path

# ====================================================================
# PROD TEXT ASSET BACKUP (Guards your text copy from accidental loss)
# ====================================================================
PRODUCT_NAME = "TaxPulse™ Engine — Serverless SMB Compliance Backend"

DELIVERY_TEXT_BACKUP = """
Thank you for your purchase! Your enterprise production-grade backend architecture is ready for deployment. Below you will find your full code suite and blueprint assets.

📦 ARCHITECTURAL PACKAGE CONTENTS
1. system_blueprint.md (File Attached Above)
   Complete technical schematics and a comprehensive setup walk-through. It contains your production PostgreSQL schemas with optimized multi-tenant database indexing.

2. /tax-engine/ Core Microservices (Inside Blueprint)
   High-efficiency Python FastAPI production service script (index.py). Includes a clean routing framework with serverless operational manifests (vercel.json) and automated Metadata/OCR processing pipelines for seamless document extraction.

3. Proactive Calendar & Alerting Subsystem
   A native background cron-scheduler that calculates time offsets. It manages a pre-calibrated multi-channel warning engine (30-day, 7-day, and 24-hour alert windows) alongside a dynamic Gumroad API bridge gateway for live folder synchronization.

🛠️ QUICK-START ARCHITECTURE DEPLOYMENT
First, download the system_blueprint.md file attached above. Next, follow the initialization guide inside to link the FastAPI modules directly to your GitHub repository. Finally, deploy seamlessly onto Vercel with a single push to your main branch.

SUPPORT & LICENSING PROTOCOL
Your annual access license includes 12 months of core schema optimizations, system patches, and microservice framework updates. Reference your transaction receipt if you require priority engineering support.

DISCLAIMER: This application provides automated structural data-processing architecture. It does not constitute formal accounting or legal counsel.
"""

# ====================================================================
# RUNTIME INTEGRITY GUARD (Protects your folders from disappearing)
# ====================================================================
def enforce_application_structure():
    """
    Ensures that essential storage directories exist on the server environment.
    This prevents Vercel serverless containers from failing due to missing paths.
    """
    required_directories = [
        Path("tax-engine/uploads"),
        Path("tax-engine/blueprints"),
        Path("tax-engine/cache")
    ]
    
    for directory in required_directories:
        directory.mkdir(parents=True, exist_ok=True)
        # Create a hidden anchor file inside so the runtime recognizes the directory structure
        anchor_file = directory / ".runtime_anchor"
        if not anchor_file.exists():
            anchor_file.touch()

# Automatically execute folder protection when this module is imported by your app
enforce_application_structure()
