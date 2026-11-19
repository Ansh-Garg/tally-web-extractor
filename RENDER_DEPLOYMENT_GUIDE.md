# How to Deploy Tally Web Extractor on Render via GitHub

Follow this 3-minute guide to take your **Tally Web Extractor** online using GitHub and Render.

---

## ⚡ Prerequisites
1. A **GitHub account** ([github.com](https://github.com/))
2. A free **Render account** ([render.com](https://render.com/))
3. **Git installed** on your computer ([git-scm.com](https://git-scm.com/))

---

## 🚀 Step 1: Create a GitHub Repository
1. Log in to [GitHub](https://github.com/).
2. In the top right corner, click **`+`** -> **New repository**.
3. Set the repository name: `tally-web-extractor`.
4. Choose **Public** or **Private** (Render supports both).
5. **Do NOT** check "Add a README file" (we already have all files ready).
6. Click **Create repository**.
7. Copy your repository URL (e.g., `https://github.com/YOUR_USERNAME/tally-web-extractor.git`).

---

## 🚀 Step 2: Push Your Code to GitHub

Open a terminal or command prompt inside `TallyWebExtractor`:

```cmd
cd "c:\Users\Ansh\Desktop\Download\0._TALLY_DATA_Extractor\TallyWebExtractor"
```

Then run:

```cmd
git init
git branch -M main
git add .
git commit -m "Deploy Universal Tally Web Extractor v3.4"
git remote add origin https://github.com/YOUR_USERNAME/tally-web-extractor.git
git push -u origin main
```

*(Alternatively, you can simply double-click `prepare_git_repo.bat`)*

---

## 🚀 Step 3: Deploy on Render

### Method A: Automatic Deployment using Render Blueprint (Recommended)
Because the repository includes `render.yaml`, Render can set up everything automatically!

1. Open your [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** (top right) -> **Blueprint**.
3. Select your connected GitHub account and choose the `tally-web-extractor` repository.
4. Render will detect `render.yaml` with all settings pre-configured:
   - **Service Name**: `tally-web-extractor`
   - **Environment**: `Python`
   - **Build Command**: `python package_agent.py && pip install -r requirements.txt`
   - **Start Command**: `gunicorn server:app`
   - **Health Check Path**: `/health`
5. Click **Apply**. Render will build and deploy your site in ~60 seconds!

---

### Method B: Manual Web Service Setup
If you prefer setting it up manually:

1. In Render Dashboard, click **New +** -> **Web Service**.
2. Select your `tally-web-extractor` GitHub repository.
3. Configure the following fields:
   - **Name**: `tally-web-extractor`
   - **Region**: Any (e.g., *Oregon (US West)* or *Frankfurt (EU)*)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `python package_agent.py && pip install -r requirements.txt`
   - **Start Command**: `gunicorn server:app`
   - **Instance Type**: `Free`
4. Expand **Advanced**:
   - **Health Check Path**: `/health`
5. Click **Create Web Service**.

---

## 🎯 Step 4: Access Your Live Website

Once deployment succeeds, Render gives you a free live URL:
```
https://tally-web-extractor.onrender.com
```

### What happens when users visit your live Render URL?
1. **The Commercial Landing Page** loads instantly with branding, architecture explanations, and feature breakdowns.
2. **Zero EXE Mode (Chrome Extension - Recommended)**:
   - Users click **Add Chrome Extension (6 KB)** to download `tally-web-extension.zip`.
   - In Chrome, they open `chrome://extensions`, enable Developer Mode, and click *Load unpacked*.
   - They click **Launch Web Extractor** (`/dashboard`). The dashboard instantly communicates with their local Tally on `localhost:8080` without running any local Python server or desktop EXE!
3. **Local Agent Mode (Optional Fallback)**:
   - Users can alternatively download `tally-web-agent.zip` (35 KB) and double-click `run_web_agent.bat` if they prefer a local background server.

---

## 📁 Repository Structure for Render

| File | Purpose for Render |
|---|---|
| `server.py` | Production Flask WSGI entrypoint serving landing page, dashboard, and Cloud Extraction API |
| `tally_engine.py` | Enterprise core parsing TDL XML, reconstructing hierarchies, Dr/Cr signed values, and generating Master XLSX |
| `requirements.txt` | Lists dependencies (`flask`, `gunicorn`, `openpyxl`, `werkzeug`) for Render |
| `render.yaml` | Render Blueprint configuration (auto-configures the service) |
| `Procfile` | Specifies `web: gunicorn server:app` process type |
| `extension/` | Lightweight Manifest V3 Chrome Extension source code |
| `website/` | The frontend landing page, CSS, JS, and downloadable assets |
| `agent/` | The optional fallback local bridge agent source code |
| `package_agent.py` | Automatically bundles both `tally-web-extension.zip` and `tally-web-agent.zip` during build |

---

*Engineered & Developed By : Ansh Garg*  
*Enterprise Accounting Systems Automation*
