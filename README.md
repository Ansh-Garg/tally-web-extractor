# Universal Tally Web Extractor v3.4
### Enterprise Accounting & Consolidated Multi-Company Audit Suite (Web Edition)
**Engineered & Developed By : Ansh Garg**

---

## 🌟 Overview & Architecture

Because **Tally's HTTP Server is bound strictly to `localhost:8080`** on the local Windows machine, browsers block public websites from querying `localhost` due to CORS and Same-Origin security policies.

To overcome this without compromising security or requiring accounting data to leave the user's private computer, this project implements a **Hybrid Web-Local Bridge Architecture**:

```
┌─────────────────────────────────┐           ┌─────────────────────────────────┐
│     Commercial Cloud Website    │           │      Browser Web Dashboard      │
│      (Landing & Downloader)     │           │      (Modern Responsive UI)     │
│   Hosted on public domain/Vercel│           │     Runs at: localhost:5000     │
└───────────────┬─────────────────┘           └────────────────┬────────────────┘
                │ Downloads Agent Bundle                       │ REST API (JSON)
                ▼                                              ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                           LOCAL WINDOWS COMPUTER                              │
│                                                                               │
│  ┌─────────────────────────────┐           ┌─────────────────────────────┐    │
│  │      Local Bridge Agent     │  XML/TDL  │      TallyPrime / ERP 9     │    │
│  │   (Flask Service on :5000)  ├──────────►│      (HTTP Server :8080)    │    │
│  └──────────────┬──────────────┘           └─────────────────────────────┘    │
│                 │                                                             │
│                 ▼ Generates                                                   │
│  ┌─────────────────────────────────────────────────────────┐                  │
│  │         Strictly 1 Master Excel Workbook (.xlsx)        │                  │
│  │  - Sheet 1: Trial Balance Extract (Active Ledgers Only) │                  │
│  │  - Sheet 2: Transaction Register (Signed Net Amounts)   │                  │
│  │  - Sheet 3: Reconciliation & Audit Summary             │                  │
│  └─────────────────────────────────────────────────────────┘                  │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 How to Run

### 1. Launch the Local Web Agent
Navigate to the `agent/` folder and double-click:
```cmd
run_web_agent.bat
```
- Automatically checks Python and installs dependencies (`Flask`).
- Starts the local REST service on `http://localhost:5000`.
- Automatically opens your default web browser to the Web Dashboard.

### 2. View the Commercial Landing & Download Website
Open `website/index.html` in any browser or serve it with any static web server (Vercel, Netlify, GitHub Pages, Apache, Nginx):
```cmd
python -m http.server 8000 --directory website
```
- Live heartbeat probes `http://localhost:5000/api/status`.
- Automatically detects if the user's agent is active and provides a 1-click **Launch Dashboard** button.
- Provides a direct 1-click download of `downloads/tally-web-agent.zip`.

### 3. Build a Zero-Python Standalone EXE Agent
Inside `agent/`, double-click:
```cmd
Build_Standalone_Agent_EXE.bat
```
- Uses PyInstaller to compile `tally_agent.py`, all HTML templates, CSS, and JS into a standalone Windows executable `dist\TallyWebAgent\TallyWebAgent.exe`.
- End users do not even need Python installed!

---

## 📡 REST API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | `GET` | Serves the interactive Single Page Web Dashboard |
| `/api/status` | `GET` | Returns Tally connection status (`tally_online`, `version`, `tally_url`) |
| `/api/companies` | `GET` | Scans and returns all loaded companies in Tally with FY start/end dates |
| `/api/inspect` | `POST` | Inspects statement heads (P&L vs Balance Sheet) and counts for a company |
| `/api/extract` | `POST` | Triggers background extraction and returns `{ "task_id": "..." }` |
| `/api/extract/<task_id>` | `GET` | Returns task status, percent progress, and streaming live execution logs |
| `/api/download/<filename>` | `GET` | Downloads the generated `.xlsx` workbook directly |
| `/api/outputs` | `GET` | Lists previously generated workbooks with timestamps and file sizes |
| `/api/license` | `GET` | Returns Machine ID, tier, status, expiry, and extraction quotas |
| `/api/license/activate` | `POST` | Activates an offline cryptographic license key |

---

## 📂 Directory Layout

```
TallyWebExtractor/
├── package_agent.py             # Script to bundle agent into website zip
├── README.md                    # Complete project documentation
├── agent/                       # Local Agent service & Web UI
│   ├── tally_agent.py           # Flask REST API server & task runner
│   ├── tally_engine.py          # Core extraction engine & OpenXML builder
│   ├── license_client.py        # Machine ID & cloud/offline license manager
│   ├── config.json              # Cloud API & Tally URLs configuration
│   ├── requirements.txt         # Flask dependencies
│   ├── run_web_agent.bat        # 1-Click agent runner batch script
│   ├── Build_Standalone_Agent_EXE.bat # PyInstaller standalone EXE compiler
│   ├── templates/
│   │   └── dashboard.html       # Web dashboard Jinja2 template
│   ├── static/
│   │   ├── css/style.css        # Enterprise dashboard stylesheet
│   │   └── js/app.js            # Client-side state, polling & UI logic
│   └── output/                  # Output directory for generated workbooks
└── website/                     # Public Commercial Landing & Downloader
    ├── index.html               # Modern marketing & bridge detection page
    ├── css/style.css            # Landing page stylesheet
    ├── js/app.js                # Live agent heartbeat detection
    └── downloads/
        └── tally-web-agent.zip  # Pre-packaged 1-click downloadable agent
```

---
*Developed By : Ansh Garg*  
*Enterprise Accounting Systems Automation*
