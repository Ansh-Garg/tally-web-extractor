#!/usr/bin/env python3
"""
Universal Tally Data Extractor - 100% Free Cloud & Tiered Licensing Engine
===========================================================================
Tiered Architecture (Enterprise, Pro, Basic, Trial) Managed via Remote Cloud
Developed By : Ansh Garg
"""

import os
import sys
import json
import base64
import hashlib
import hmac
import time
import platform
import subprocess
import threading
from pathlib import Path
from datetime import datetime, timedelta
import urllib.request
import urllib.parse

# Master salt for cryptographic signing
MASTER_SIGNING_SALT = "ANSH_GARG_TALLY_EXTRACTOR_SECRET_2026_PRODUCTION"
DEFAULT_CACHE_FILE = Path.home() / ".tally_extractor_license.dat"

# Default Serverless API endpoint (User's Cloud Backend)
DEFAULT_CLOUD_API_URL = "https://script.google.com/macros/s/AKfycbyzogxJwMJaM7UA21B7do1kuWEcbZJz5jV8C8JCsItzh9foQdLz_7NU6I5LsECLT9oJ/exec"

class LicenseManager:
    def __init__(self, cloud_api_url=None):
        self.cloud_api_url = cloud_api_url or self._load_cloud_url_from_config()
        self.machine_id = self.get_machine_id()
        self.cached_license = self.load_local_license()

    def _load_cloud_url_from_config(self):
        config_path = Path(__file__).parent / "config.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    url = cfg.get("cloud_api_url", "")
                    if url:
                        return url
            except Exception:
                pass
        return DEFAULT_CLOUD_API_URL

    @staticmethod
    def get_machine_id():
        """Generates a stable 16-character hardware fingerprint."""
        raw = ""
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystemProduct).UUID"],
                capture_output=True,
                text=True,
                timeout=4
            )
            raw = res.stdout.strip()
        except Exception:
            pass

        if not raw or "none" in raw.lower() or len(raw) < 8:
            try:
                res = subprocess.run(
                    ["wmic", "csproduct", "get", "uuid"],
                    capture_output=True,
                    text=True,
                    timeout=4
                )
                lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
                if len(lines) > 1:
                    raw = lines[1]
            except Exception:
                pass

        if not raw or "none" in raw.lower() or len(raw) < 8:
            raw = f"{platform.node()}-{os.environ.get('USERNAME', 'USER')}"

        salt = "TALLY_EXTRACTOR_ANSH_GARG_2026_SALT"
        h = hashlib.sha256(f"{salt}::{raw}".encode("utf-8")).hexdigest().upper()
        return f"ANSH-{h[0:4]}-{h[4:8]}-{h[8:12]}"

    def load_local_license(self):
        """Loads cached license from disk."""
        if not DEFAULT_CACHE_FILE.exists():
            return None
        try:
            with open(DEFAULT_CACHE_FILE, "r", encoding="utf-8") as f:
                raw_b64 = f.read().strip()
                data = json.loads(base64.b64decode(raw_b64).decode("utf-8"))
                return data
        except Exception:
            return None

    def save_local_license(self, license_data):
        """Saves verified license to local disk."""
        try:
            raw_b64 = base64.b64encode(json.dumps(license_data).encode("utf-8")).decode("utf-8")
            with open(DEFAULT_CACHE_FILE, "w", encoding="utf-8") as f:
                f.write(raw_b64)
        except Exception as e:
            print(f"[LicenseManager] Could not save license cache: {e}")

    def get_tier(self):
        """Returns the current license tier (ENTERPRISE, PRO, BASIC, TRIAL)."""
        if self.cached_license:
            return self.cached_license.get("tier", "TRIAL").upper()
        return "TRIAL"

    def can_consolidate(self):
        """Multi-company consolidation is enabled for ENTERPRISE tier."""
        tier = self.get_tier()
        if tier == "ENTERPRISE":
            return True
        if self.cached_license and self.cached_license.get("can_consolidate"):
            return True
        return False

    def can_use_fast_mode(self):
        """High-speed fast mode is enabled for ENTERPRISE and PRO tiers."""
        tier = self.get_tier()
        if tier in ("ENTERPRISE", "PRO"):
            return True
        if self.cached_license and self.cached_license.get("can_use_fast_mode"):
            return True
        return False

    def get_extractions_left(self):
        """Returns remaining extractions count."""
        if self.cached_license:
            return self.cached_license.get("extractions_left", 0)
        return 0

    def consume_extraction_credit(self):
        """Decrements extraction count and updates anti-rollback timestamp."""
        if self.cached_license:
            left = max(0, self.cached_license.get("extractions_left", 0) - 1)
            self.cached_license["extractions_left"] = left
            self.cached_license["last_seen_epoch"] = time.time()
            self.save_local_license(self.cached_license)

    def verify_offline_key(self, key_str):
        """Validates an offline cryptographic key."""
        key_str = key_str.strip()
        parts = key_str.split(".")
        if len(parts) == 4 and parts[0] == "KEY":
            client_b64, expiry_str, received_sig = parts[1], parts[2], parts[3]
            tier = "ENTERPRISE"
        elif len(parts) == 5 and parts[0] == "KEY":
            client_b64, tier, expiry_str, received_sig = parts[1], parts[2], parts[3], parts[4]
        else:
            return False, "Invalid license key format."

        try:
            client_name = base64.b64decode(client_b64).decode("utf-8")
        except Exception:
            return False, "Corrupted client metadata in license key."

        expected_sig = self._compute_key_signature(client_name, self.machine_id, tier, expiry_str)
        if not hmac.compare_digest(expected_sig, received_sig):
            legacy_sig = hashlib.sha256(f"{client_name}::{self.machine_id}::{expiry_str}::{MASTER_SIGNING_SALT}".encode("utf-8")).hexdigest()[:16].upper()
            if not hmac.compare_digest(legacy_sig, received_sig):
                return False, "License key is invalid or belongs to another machine."

        try:
            expiry_dt = datetime.strptime(expiry_str, "%Y%m%d")
            if datetime.now() > expiry_dt:
                return False, f"License key expired on {expiry_dt.strftime('%d-%m-%Y')}."
        except Exception:
            return False, "Invalid expiry date inside license key."

        tier = tier.upper()
        lic_data = {
            "status": "ACTIVE",
            "tier": tier,
            "client_name": client_name,
            "machine_id": self.machine_id,
            "expiry": expiry_dt.strftime("%d-%m-%Y"),
            "extractions_left": 999999,
            "license_type": "OFFLINE_KEY",
            "can_consolidate": (tier == "ENTERPRISE"),
            "can_use_fast_mode": (tier in ("ENTERPRISE", "PRO")),
            "last_seen_epoch": time.time(),
            "last_verified": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.save_local_license(lic_data)
        self.cached_license = lic_data
        return True, f"[{tier}] License successfully activated offline!"

    @staticmethod
    def _compute_key_signature(client_name, machine_id, tier, expiry_str):
        payload = f"{client_name}::{machine_id}::{tier}::{expiry_str}::{MASTER_SIGNING_SALT}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16].upper()

    @staticmethod
    def generate_offline_key(client_name, target_machine_id, tier="ENTERPRISE", days_valid=365):
        """Admin function: generates an offline key with tiering."""
        tier = tier.upper()
        client_b64 = base64.b64encode(client_name.encode("utf-8")).decode("utf-8")
        expiry_dt = datetime.now() + timedelta(days=days_valid)
        expiry_str = expiry_dt.strftime("%Y%m%d")
        sig = LicenseManager._compute_key_signature(client_name, target_machine_id, tier, expiry_str)
        return f"KEY.{client_b64}.{tier}.{expiry_str}.{sig}"

    def check_license(self):
        """
        Comprehensive license verification (Online Cloud + Strict Offline Expiry & Limits):
        Zero hardcoded master bypass.
        """
        # 1. Online Cloud Check
        if self.cloud_api_url and self.cloud_api_url.startswith("http"):
            try:
                params = urllib.parse.urlencode({
                    "action": "check_license",
                    "machine_id": self.machine_id,
                    "client_name": os.environ.get("USERNAME", "User"),
                    "version": "v3.4"
                })
                req_url = f"{self.cloud_api_url}?{params}"
                req = urllib.request.Request(req_url, headers={"User-Agent": "TallyExtractor-Client/3.4"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    status = res_data.get("status", "PENDING").upper()
                    tier = res_data.get("license_tier", "TRIAL").upper()
                    client_name = res_data.get("client_name", "User")
                    expiry = res_data.get("expiry", "Unknown")
                    extractions_left = res_data.get("extractions_left", 2)
                    can_cons = res_data.get("can_consolidate", (tier == "ENTERPRISE"))
                    can_fast = res_data.get("can_use_fast_mode", (tier in ("ENTERPRISE", "PRO")))

                    # Check if extraction limit reached
                    if status == "ACTIVE" and extractions_left <= 0:
                        status = "LIMIT_REACHED"

                    lic = {
                        "status": status,
                        "tier": tier,
                        "client_name": client_name,
                        "machine_id": self.machine_id,
                        "expiry": expiry,
                        "extractions_left": extractions_left,
                        "license_type": "CLOUD",
                        "can_consolidate": can_cons,
                        "can_use_fast_mode": can_fast,
                        "last_seen_epoch": time.time(),
                        "last_verified": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    self.save_local_license(lic)
                    self.cached_license = lic

                    if status == "ACTIVE":
                        return {
                            "allowed": True,
                            "status": "ACTIVE",
                            "tier": tier,
                            "client_name": client_name,
                            "expiry": expiry,
                            "extractions_left": extractions_left,
                            "can_consolidate": can_cons,
                            "can_use_fast_mode": can_fast,
                            "message": f"[{tier}] Active (Valid until {expiry} | {extractions_left} extractions left)"
                        }
                    elif status == "LIMIT_REACHED":
                        return {
                            "allowed": False,
                            "status": "LIMIT_REACHED",
                            "tier": tier,
                            "client_name": client_name,
                            "expiry": expiry,
                            "message": "Maximum extraction limit reached. Please contact Developer (Ansh Garg) to increase your limit or change your tier."
                        }
                    elif status == "BLOCKED":
                        return {
                            "allowed": False,
                            "status": "BLOCKED",
                            "tier": tier,
                            "client_name": client_name,
                            "expiry": expiry,
                            "message": "Access Suspended. Please contact Developer (Ansh Garg)."
                        }
                    elif status == "EXPIRED":
                        return {
                            "allowed": False,
                            "status": "EXPIRED",
                            "tier": tier,
                            "client_name": client_name,
                            "expiry": expiry,
                            "message": f"License expired on {expiry}. Please contact Developer (Ansh Garg) to renew your access."
                        }
                    else: # PENDING
                        return {
                            "allowed": False,
                            "status": "PENDING",
                            "tier": tier,
                            "client_name": client_name,
                            "expiry": "-",
                            "message": "Activation Pending. Please contact Developer (Ansh Garg) to activate your license."
                        }
            except Exception:
                # Network unreachable: fall back to strict offline cache check
                pass

        # 2. Strict Offline Cache Fallback (When PC has no internet)
        if self.cached_license and self.cached_license.get("machine_id") == self.machine_id:
            status = self.cached_license.get("status")
            tier = self.cached_license.get("tier", "TRIAL").upper()
            expiry_str = self.cached_license.get("expiry", "")
            extractions_left = self.cached_license.get("extractions_left", 2)
            last_seen_epoch = self.cached_license.get("last_seen_epoch", 0)

            # Anti-Tamper: Detect system clock rollbacks
            current_epoch = time.time()
            if last_seen_epoch and current_epoch < (last_seen_epoch - 120): # Clock rolled back by > 2 mins
                return {
                    "allowed": False,
                    "status": "TAMPERED",
                    "tier": tier,
                    "client_name": self.cached_license.get("client_name"),
                    "expiry": expiry_str,
                    "message": "System clock rollback detected. Please correct your system clock and contact Developer (Ansh Garg)."
                }

            # Expiry date check
            if expiry_str and expiry_str != "Unknown":
                try:
                    expiry_dt = datetime.strptime(expiry_str, "%d-%m-%Y")
                    if datetime.now() > expiry_dt:
                        return {
                            "allowed": False,
                            "status": "EXPIRED",
                            "tier": tier,
                            "client_name": self.cached_license.get("client_name"),
                            "expiry": expiry_str,
                            "message": f"License validity expired on {expiry_str}. Please contact Developer (Ansh Garg) to renew."
                        }
                except Exception:
                    pass

            # Extractions limit check
            if extractions_left <= 0:
                return {
                    "allowed": False,
                    "status": "LIMIT_REACHED",
                    "tier": tier,
                    "client_name": self.cached_license.get("client_name"),
                    "expiry": expiry_str,
                    "message": "Maximum extraction limit reached. Please contact Developer (Ansh Garg) to increase your extraction limit."
                }

            if status == "ACTIVE":
                can_cons = self.cached_license.get("can_consolidate", (tier == "ENTERPRISE"))
                can_fast = self.cached_license.get("can_use_fast_mode", (tier in ("ENTERPRISE", "PRO")))

                return {
                    "allowed": True,
                    "status": "ACTIVE",
                    "tier": tier,
                    "client_name": self.cached_license.get("client_name"),
                    "expiry": expiry_str,
                    "extractions_left": extractions_left,
                    "can_consolidate": can_cons,
                    "can_use_fast_mode": can_fast,
                    "message": f"[{tier}] Licensed (Offline Mode: Valid until {expiry_str} | {extractions_left} left)"
                }

        # 3. Unlicensed
        return {
            "allowed": False,
            "status": "UNREGISTERED",
            "tier": "NONE",
            "client_name": "Unregistered",
            "expiry": "-",
            "message": "Activation Required. Please contact Developer (Ansh Garg) with your Machine ID."
        }

    def log_usage_telemetry(self, company_name, scope_label, rows_count):
        """Asynchronously records usage telemetry into cloud backend."""
        # Always consume local extraction credit
        self.consume_extraction_credit()

        if not self.cloud_api_url or not self.cloud_api_url.startswith("http"):
            return

        def _worker():
            try:
                payload = json.dumps({
                    "action": "log_usage",
                    "machine_id": self.machine_id,
                    "client_name": (self.cached_license or {}).get("client_name", os.environ.get("USERNAME", "User")),
                    "license_tier": self.get_tier(),
                    "company": company_name,
                    "scope": scope_label,
                    "records": rows_count,
                    "timestamp": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                    "version": "v3.4"
                }).encode("utf-8")

                req = urllib.request.Request(
                    self.cloud_api_url,
                    data=payload,
                    headers={"Content-Type": "application/json", "User-Agent": "TallyExtractor-Client/3.4"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    pass
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

if __name__ == "__main__":
    lm = LicenseManager()
    if len(sys.argv) > 1 and sys.argv[1] == "--info":
        print("=" * 65)
        print("UNIVERSAL TALLY DATA EXTRACTOR - SYSTEM INFORMATION")
        print("Developed By : Ansh Garg | Cloud License Management")
        print("=" * 65)
        print(f"Machine ID       : {lm.machine_id}")
        lic = lm.check_license()
        print(f"License Status   : {lic['status']}")
        print(f"License Tier     : [{lic.get('tier', 'NONE')}]")
        print(f"Client Name      : {lic['client_name']}")
        print(f"Expiry Date      : {lic['expiry']}")
        print(f"Extractions Left : {lm.get_extractions_left()}")
        print(f"Can Consolidate  : {lm.can_consolidate()}")
        print(f"Can Fast Mode    : {lm.can_use_fast_mode()}")
        print(f"Message          : {lic['message']}")
        print("=" * 65)
    elif len(sys.argv) > 1 and sys.argv[1] == "--generate-key":
        if len(sys.argv) < 3:
            print("Usage: python license_manager.py --generate-key <MACHINE_ID> [Client Name] [Tier: ENTERPRISE/PRO/BASIC] [Days]")
            sys.exit(1)
        target_mid = sys.argv[2]
        c_name = sys.argv[3] if len(sys.argv) > 3 else "Authorized Client"
        tier_val = sys.argv[4] if len(sys.argv) > 4 else "ENTERPRISE"
        days = int(sys.argv[5]) if len(sys.argv) > 5 else 365
        key = LicenseManager.generate_offline_key(c_name, target_mid, tier_val, days)
        print("=" * 65)
        print(f"OFFLINE LICENSE KEY GENERATED")
        print(f"Client Name       : {c_name}")
        print(f"License Tier      : [{tier_val.upper()}]")
        print(f"Target Machine ID : {target_mid}")
        print(f"Validity (Days)   : {days} days")
        print(f"Expiry Date       : {(datetime.now() + timedelta(days=days)).strftime('%d-%m-%Y')}")
        print("-" * 65)
        print(key)
        print("-" * 65)
        print("Send this key string to the user to activate their software offline.")
        print("=" * 65)
    else:
        print(f"Machine ID: {lm.machine_id}")
        print("Run with --info or --generate-key")
