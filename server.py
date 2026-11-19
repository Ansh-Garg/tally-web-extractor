#!/usr/bin/env python3
"""
Tally Web Extractor — Production Cloud Web Server (Render / Cloud Deployment)
=============================================================================
Serves the commercial landing site, marketing assets, extension download bundle,
and the Cloud Extraction API (converts raw Tally XML into strictly 1 Master XLSX).
Developed By : Ansh Garg
"""

import os
import sys
import json
import uuid
from pathlib import Path
from datetime import datetime
from flask import Flask, send_from_directory, jsonify, make_response, request, render_template

import tally_engine
from license_client import LicenseManager

BASE_DIR = Path(__file__).parent.resolve()
WEBSITE_DIR = BASE_DIR / "website"
DOWNLOADS_DIR = WEBSITE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "cloud_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "agent" / "templates"),
    static_folder=str(WEBSITE_DIR),
    static_url_path=""
)

license_mgr = LicenseManager()

# ---------------- Security & CORS Headers ----------------
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
def add_security_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, *"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

# ---------------- Landing Page ----------------
@app.route("/")
def index():
    return send_from_directory(str(WEBSITE_DIR), "index.html")

# ---------------- Online Web Extractor Dashboard ----------------
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

# ---------------- Extension Install Guide ----------------
@app.route("/install")
def install_guide():
    return send_from_directory(str(WEBSITE_DIR), "install.html")

# ---------------- Static Assets ----------------
@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory(str(WEBSITE_DIR / "css"), filename)

@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory(str(WEBSITE_DIR / "js"), filename)

@app.route("/static/<path:filename>")
def serve_agent_static(filename):
    return send_from_directory(str(BASE_DIR / "agent" / "static"), filename)

# ---------------- Direct Downloads (Agent & Chrome Extension) ----------------
@app.route("/downloads/<path:filename>")
def serve_downloads(filename):
    response = make_response(send_from_directory(str(DOWNLOADS_DIR), filename, as_attachment=True))
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

# ---------------- TDL Request XML Templates ----------------
@app.route("/api/tally-templates")
def get_templates():
    company = request.args.get("company", "")
    start = request.args.get("start", "20250401")
    end = request.args.get("end", "20260331")
    fast = request.args.get("fast", "false").lower() == "true"

    return jsonify({
        "loaded_companies": tally_engine.loaded_companies_request(),
        "groups": tally_engine.groups_request(company),
        "ledgers": tally_engine.ledgers_request(company),
        "vouchers": tally_engine.vouchers_request(company, start, end, fast_mode=fast)
    })

# ---------------- Cloud Structure Inspection ----------------
@app.route("/api/cloud-inspect", methods=["POST"])
def cloud_inspect():
    data = request.get_json(force=True)
    g_xml = data.get("groups_xml", "")
    l_xml = data.get("ledgers_xml", "")
    company = data.get("company", "")

    try:
        _, _, pl_heads, bs_heads, _, bs_count, pl_count = (
            tally_engine.inspect_company_structure_from_xml(g_xml, l_xml, company)
        )
        return jsonify({
            "pl_heads": pl_heads,
            "bs_heads": bs_heads,
            "pl_count": pl_count,
            "bs_count": bs_count,
            "total_count": pl_count + bs_count
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ---------------- Cloud Extraction & Excel Generation ----------------
@app.route("/api/cloud-extract", methods=["POST"])
def cloud_extract():
    data = request.get_json(force=True)
    companies_data = data.get("companies_data", [])
    mode = data.get("mode", "pl")
    label = data.get("label", "Income & Expenditure")
    target_heads = data.get("target_heads", [])
    fy_start = data.get("start_date", "20250401")
    fy_end = data.get("end_date", "20260331")

    if not companies_data:
        return jsonify({"error": "No company XML data provided."}), 400

    try:
        excel_path, stats, tb_sum = tally_engine.execute_cloud_extraction(
            companies_data, mode, label, target_heads, fy_start, fy_end, OUTPUT_DIR
        )

        filename = excel_path.name
        download_url = f"/api/download/{filename}"

        # Asynchronously log usage telemetry if license allows
        try:
            comp_display = companies_data[0].get("company", "") if len(companies_data) == 1 else f"Consolidated ({len(companies_data)} Companies)"
            license_mgr.log_usage_telemetry(comp_display, label, 0)
        except Exception:
            pass

        return jsonify({
            "success": True,
            "filename": filename,
            "download_url": download_url,
            "stats": stats,
            "tb_total_sum": tb_sum
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- Download Generated Workbook ----------------
@app.route("/api/download/<filename>")
def download_workbook(filename):
    for f in OUTPUT_DIR.rglob(filename):
        if f.is_file():
            return send_from_directory(str(f.parent), f.name, as_attachment=True)
    return jsonify({"error": "File not found"}), 404

# ---------------- Health Check (Render) ----------------
@app.route("/health")
@app.route("/api/health")
def health_check():
    agent_zip = DOWNLOADS_DIR / "tally-web-agent.zip"
    ext_zip = DOWNLOADS_DIR / "tally-web-extension.zip"
    return jsonify({
        "status": "healthy",
        "service": "Tally Web Extractor",
        "version": "v3.4",
        "agent_bundle_available": agent_zip.exists(),
        "extension_available": ext_zip.exists(),
        "cloud_engine_ready": True
    })

# ---------------- Local Runner ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 65)
    print("  TALLY WEB EXTRACTOR — CLOUD SERVER")
    print("  Developed By : Ansh Garg")
    print(f"  Listening on http://0.0.0.0:{port}")
    print("=" * 65)
    app.run(host="0.0.0.0", port=port, debug=False)
