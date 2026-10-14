# 🚀 SMB Document & Tax Compliance Engine Backend

A unified serverless backend architecture running seamlessly on **Vercel** and connected directly to **GitHub**. This app is custom-engineered to help small businesses dynamically organize business documentation, process receipts, track localized geographical tax calendar milestones, and automate reminders so payment gates are never missed.

---

## 📁 Active Workspace Repositories (Verified by Vercel)
* `/tax-engine/index.py` — High-efficiency Python FastAPI production service script managing core computing and data routing.
* `/tax-engine/requirements.txt` — Core framework software dependency manifests mapping your live Python packages.
* `/vercel.json` — Root configuration map instructing Vercel to bypass Node.js and route 100% of network traffic straight to the Python engine.

---

## 🛠️ Deep Dive: Integrated Core Micro-Engines

### 📂 1. Document Processing Engine
An integrated metadata processing node built to securely log incoming receipt snapshots, PDFs, and vendor invoice data fields into dynamic schemas. 
* **OCR Field Extraction:** Automatically evaluates uploaded assets and structures key fields—identifying Vendor Identities, Billing Issue Dates, Total Financial Amounts, and Tax Fractions.
* **Storage Pointers:** Links transactional file nodes securely to unique resource locations (`storage_url`) without overloading native computational layers.

### 📅 2. Calendar & Notification Subsystem
An operational, proactive compliance engine built to map statutory timelines across distinct regional jurisdictions and handle notification alerts automatically.
* **Auto-Offset Scheduler:** When a target tax deadline calendar boundary is registered, the system crawls active user profiles, evaluates delivery windows, and pre-queues alert parameters.
* **Multi-Channel Alert Dispatches:** Implements automated cron-worker checks that calculate temporal offsets and trigger live **Email warnings** exactly **30 days, 7 days, and 24 hours** before a business's tax liability window closes.

---

## 🛰️ Third-Party API Sync Gateways
* **Live Gumroad API Bridge:** Connects seamlessly to remote storefront data points via cryptographic personal security keys, enabling real-time background file and folder synchronization straight through Vercel's edge network layers.
