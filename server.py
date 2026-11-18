#!/usr/bin/env python3
"""
Tally Web Extractor — Production Cloud Web Server (Render / Cloud Deployment)
=============================================================================
Serves the commercial landing site, marketing assets, and agent download bundle.
Designed for deployment on Render, Railway, Fly.io, or any cloud container.
Developed By : Ansh Garg
"""

import os
from pathlib import Path
from flask import Flask, send_from_directory, jsonify, make_response

BASE_DIR = Path(__file__).parent.resolve()
WEBSITE_DIR = BASE_DIR / "website"
DOWNLOADS_DIR = WEBSITE_DIR / "downloads"

app = Flask(
    __name__,
    static_folder=str(WEBSITE_DIR),
    static_url_path=""
)

# ---------------- Security & CORS Headers ----------------
@app.after_request
def add_security_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    # Allow communication with local private network agent
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response

# ---------------- Landing Page ----------------
@app.route("/")
def index():
    return send_from_directory(str(WEBSITE_DIR), "index.html")

# ---------------- Static Assets ----------------
@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory(str(WEBSITE_DIR / "css"), filename)

@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory(str(WEBSITE_DIR / "js"), filename)

# ---------------- Direct Agent Download ----------------
@app.route("/downloads/<path:filename>")
def serve_downloads(filename):
    response = make_response(send_from_directory(str(DOWNLOADS_DIR), filename, as_attachment=True))
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

# ---------------- Health Check (For Render Zero-Downtime Deploys) ----------------
@app.route("/health")
@app.route("/api/health")
def health_check():
    agent_zip = DOWNLOADS_DIR / "tally-web-agent.zip"
    return jsonify({
        "status": "healthy",
        "service": "Tally Web Extractor",
        "version": "v3.4",
        "agent_bundle_available": agent_zip.exists(),
        "agent_bundle_size_bytes": agent_zip.stat().st_size if agent_zip.exists() else 0
    })

# ---------------- Entrypoint for Local Testing ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 65)
    print("  TALLY WEB EXTRACTOR — CLOUD SERVER")
    print("  Developed By : Ansh Garg")
    print(f"  Listening on http://0.0.0.0:{port}")
    print("=" * 65)
    app.run(host="0.0.0.0", port=port, debug=False)
