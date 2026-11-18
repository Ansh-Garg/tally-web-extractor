#!/usr/bin/env python3
"""
Tally Web Extractor — Flask REST API Agent
===========================================
Main entry point for the local web agent. Serves the dashboard UI
and provides REST API endpoints for Tally data extraction.
Developed By : Ansh Garg
"""

import sys
import os
import json
import uuid
import threading
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, render_template, send_file

import tally_engine
from license_client import LicenseManager

# --------------- App Setup ---------------
app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)

# --------------- Configuration ---------------
CONFIG_PATH = Path(__file__).parent / "config.json"

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}

def get_tally_url():
    cfg = load_config()
    return cfg.get("tally_url", tally_engine.DEFAULT_TALLY_URL)

# --------------- License Manager ---------------
license_mgr = LicenseManager()

# --------------- Active Extraction Tasks ---------------
active_tasks = {}

# --------------- CORS & Private Network Access ---------------
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        res = app.make_default_options_response()
        res.headers["Access-Control-Allow-Origin"] = "*"
        res.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, *"
        res.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        res.headers["Access-Control-Allow-Private-Network"] = "true"
        return res

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, *"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response

# --------------- Log Capture ---------------
class LogCapture:
    """Redirect stdout to capture extraction logs into the task dict."""
    def __init__(self, task):
        self.task = task
        self.real = sys.stdout

    def write(self, s):
        c = s.strip()
        if c:
            self.task["logs"].append(c)
            self.real.write(s)

    def flush(self):
        self.real.flush()

# --------------- Background Extraction Thread ---------------
def run_extraction(task_id, params):
    task = active_tasks[task_id]
    old_stdout = sys.stdout
    sys.stdout = LogCapture(task)
    try:
        output_root = Path(__file__).parent / "output"
        folders = tally_engine.execute_all(
            params["companies"],
            params["mode"],
            params["label"],
            params["heads"],
            params["start_date"],
            params["end_date"],
            get_tally_url(),
            output_root,
            fast_mode=params.get("fast_mode", False),
        )
        # Find the generated Excel file
        if folders:
            for f in folders[0].glob("*.xlsx"):
                task["file_name"] = f.name
                break
        task["status"] = "completed"
        task["progress"] = 100
        # Log usage telemetry
        try:
            lm = LicenseManager()
            comp_display = (
                params["companies"][0]
                if len(params["companies"]) == 1
                else f"Consolidated ({len(params['companies'])} Companies)"
            )
            lm.log_usage_telemetry(comp_display, params["label"], 0)
        except Exception:
            pass
    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
    finally:
        sys.stdout = old_stdout

# ===================== ROUTES =====================

# --------------- Dashboard ---------------
@app.route("/")
def index():
    return render_template("dashboard.html")

# --------------- Status ---------------
@app.route("/api/status")
def api_status():
    tally_url = get_tally_url()
    online, _ = tally_engine.test_connection(tally_url)
    return jsonify({
        "tally_online": online,
        "version": tally_engine.APP_VERSION,
        "tally_url": tally_url,
    })

# --------------- Companies ---------------
@app.route("/api/companies")
def api_companies():
    tally_url = get_tally_url()
    comps = tally_engine.fetch_loaded_companies(tally_url)
    return jsonify({"companies": comps})

# --------------- Inspect Company Structure ---------------
@app.route("/api/inspect", methods=["POST"])
def api_inspect():
    data = request.get_json(force=True)
    company = data.get("company", "")
    tally_url = get_tally_url()

    _, _, pl_heads, bs_heads, _, bs_count, pl_count = (
        tally_engine.inspect_company_structure(company, tally_url)
    )
    return jsonify({
        "pl_heads": pl_heads,
        "bs_heads": bs_heads,
        "pl_count": pl_count,
        "bs_count": bs_count,
        "total_count": pl_count + bs_count,
    })

# --------------- Start Extraction ---------------
@app.route("/api/extract", methods=["POST"])
def api_extract():
    # License gate
    lic = license_mgr.check_license()
    if not lic.get("allowed"):
        return jsonify({"error": lic.get("message", "License not active")}), 403

    data = request.get_json(force=True)
    task_id = uuid.uuid4().hex[:8]
    params = {
        "companies": data.get("companies", []),
        "mode": data.get("mode", "all"),
        "label": data.get("label", "All Ledgers"),
        "heads": data.get("heads", []),
        "start_date": data.get("start_date", "20250401"),
        "end_date": data.get("end_date", "20260331"),
        "fast_mode": data.get("fast_mode", False),
    }

    active_tasks[task_id] = {
        "status": "running",
        "logs": [],
        "progress": 0,
        "file_name": None,
        "error": None,
        "thread": None,
    }

    t = threading.Thread(target=run_extraction, args=(task_id, params), daemon=True)
    active_tasks[task_id]["thread"] = t
    t.start()

    return jsonify({"task_id": task_id})

# --------------- Extraction Progress ---------------
@app.route("/api/extract/<task_id>")
def api_extract_status(task_id):
    task = active_tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({
        "status": task["status"],
        "progress": task["progress"],
        "logs": task["logs"],
        "file_name": task["file_name"],
        "error": task["error"],
    })

# --------------- Download Output File ---------------
@app.route("/api/download/<filename>")
def api_download(filename):
    output_root = Path(__file__).parent / "output"
    # Search recursively for the file
    for f in output_root.rglob(filename):
        if f.is_file():
            return send_file(str(f), as_attachment=True)
    return jsonify({"error": "File not found"}), 404

# --------------- List Previous Outputs ---------------
@app.route("/api/outputs")
def api_outputs():
    output_root = Path(__file__).parent / "output"
    files = []
    if output_root.exists():
        for f in output_root.rglob("*.xlsx"):
            stat = f.stat()
            files.append({
                "name": f.name,
                "size": stat.st_size,
                "timestamp": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
    # Most recent first
    files.sort(key=lambda x: x["timestamp"], reverse=True)
    return jsonify({"files": files})

# --------------- License Info ---------------
@app.route("/api/license")
def api_license():
    lic = license_mgr.check_license()
    return jsonify({
        "allowed": lic.get("allowed", False),
        "status": lic.get("status", "UNKNOWN"),
        "tier": lic.get("tier", "NONE"),
        "client_name": lic.get("client_name", ""),
        "expiry": lic.get("expiry", "-"),
        "machine_id": license_mgr.machine_id,
        "extractions_left": lic.get("extractions_left", 0),
        "message": lic.get("message", ""),
    })

# --------------- Activate License ---------------
@app.route("/api/license/activate", methods=["POST"])
def api_license_activate():
    data = request.get_json(force=True)
    key = data.get("key", "").strip()
    if not key:
        return jsonify({"success": False, "message": "No license key provided."})

    success, message = license_mgr.verify_offline_key(key)
    return jsonify({"success": success, "message": message})

# ===================== STARTUP =====================
if __name__ == "__main__":
    import webbrowser

    print("=" * 60)
    print(f"  {tally_engine.APP_TITLE} - Web Agent {tally_engine.APP_VERSION}")
    print(f"  Developed By : {tally_engine.APP_DEVELOPER}")
    print(f"  Dashboard: http://localhost:5000")
    print("=" * 60)
    webbrowser.open("http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
