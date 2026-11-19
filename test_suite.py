#!/usr/bin/env python3
"""
Comprehensive Integration & Verification Test Suite for Tally Web Extractor Cloud Server
"""
import io
import json
import zipfile
import openpyxl
from pathlib import Path
from server import app

# Minimal mock Tally XML payloads
MOCK_GROUPS_XML = """<ENVELOPE>
  <BODY>
    <DATA>
      <COLLECTION>
        <GROUP NAME="Indirect Expenses" PARENT="" ISSUBLEDGER="No"/>
        <GROUP NAME="Administrative Expenses" PARENT="Indirect Expenses" ISSUBLEDGER="No"/>
        <GROUP NAME="Current Assets" PARENT="" ISSUBLEDGER="No"/>
        <GROUP NAME="Bank Accounts" PARENT="Current Assets" ISSUBLEDGER="No"/>
      </COLLECTION>
    </DATA>
  </BODY>
</ENVELOPE>"""

MOCK_LEDGERS_XML = """<ENVELOPE>
  <BODY>
    <DATA>
      <COLLECTION>
        <LEDGER NAME="Office Rent" PARENT="Administrative Expenses" OPENINGBALANCE="0"/>
        <LEDGER NAME="Electricity Charges" PARENT="Administrative Expenses" OPENINGBALANCE="0"/>
        <LEDGER NAME="HDFC Bank" PARENT="Bank Accounts" OPENINGBALANCE="-50000.00"/>
      </COLLECTION>
    </DATA>
  </BODY>
</ENVELOPE>"""

MOCK_VOUCHERS_XML = """<ENVELOPE>
  <BODY>
    <DATA>
      <COLLECTION>
        <VOUCHER VOUCHERTYPENAME="Payment" DATE="20250415" VOUCHERNUMBER="PAY-001">
          <NARRATION>April Office Rent</NARRATION>
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>Office Rent</LEDGERNAME>
            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
            <AMOUNT>-25000.00</AMOUNT>
          </ALLLEDGERENTRIES.LIST>
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>HDFC Bank</LEDGERNAME>
            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
            <AMOUNT>25000.00</AMOUNT>
          </ALLLEDGERENTRIES.LIST>
        </VOUCHER>
        <VOUCHER VOUCHERTYPENAME="Payment" DATE="20250510" VOUCHERNUMBER="PAY-002">
          <NARRATION>Electricity Bill May</NARRATION>
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>Electricity Charges</LEDGERNAME>
            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
            <AMOUNT>-4500.00</AMOUNT>
          </ALLLEDGERENTRIES.LIST>
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>HDFC Bank</LEDGERNAME>
            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
            <AMOUNT>4500.00</AMOUNT>
          </ALLLEDGERENTRIES.LIST>
        </VOUCHER>
      </COLLECTION>
    </DATA>
  </BODY>
</ENVELOPE>"""

def run_tests():
    client = app.test_client()
    passed = 0
    total = 0

    def test(name, condition, extra=""):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f"  [PASS] {name} {extra}")
        else:
            print(f"  [FAIL] {name} {extra}")

    print("=" * 70)
    print("RUNNING TALLY WEB EXTRACTOR AUTOMATED VERIFICATION SUITE")
    print("=" * 70)

    # 1. Landing Page
    r = client.get("/")
    test("GET / (Landing page)", r.status_code == 200 and b"Tally Web Extractor" in r.data)

    # 2. Dashboard
    r = client.get("/dashboard")
    test("GET /dashboard", r.status_code == 200 and b"Universal Tally Data Extractor" in r.data)

    # 3. Healthcheck
    r = client.get("/health")
    data = json.loads(r.data)
    test("GET /health", r.status_code == 200 and data.get("status") == "healthy" and data.get("extension_available"))

    # 4. Status API
    r = client.get("/api/status")
    data = json.loads(r.data)
    test("GET /api/status", r.status_code == 200 and data.get("mode") == "cloud_server")

    # 5. License API
    r = client.get("/api/license")
    data = json.loads(r.data)
    test("GET /api/license", r.status_code == 200 and "machine_id" in data)

    # 6. Previous Outputs API
    r = client.get("/api/previous-outputs")
    data = json.loads(r.data)
    test("GET /api/previous-outputs", r.status_code == 200 and "files" in data)

    # 7. Chrome Extension Download
    r = client.get("/downloads/tally-web-extension.zip")
    is_valid_zip = False
    if r.status_code == 200:
        try:
            with zipfile.ZipFile(io.BytesIO(r.data)) as z:
                is_valid_zip = "manifest.json" in z.namelist() and "background.js" in z.namelist()
        except Exception:
            pass
    test("GET /downloads/tally-web-extension.zip", r.status_code == 200 and is_valid_zip, f"({len(r.data)} bytes)")

    # 8. Web Agent Download
    r = client.get("/downloads/tally-web-agent.zip")
    agent_valid = False
    if r.status_code == 200:
        try:
            with zipfile.ZipFile(io.BytesIO(r.data)) as z:
                agent_valid = "tally_engine.py" in z.namelist()
        except Exception:
            pass
    test("GET /downloads/tally-web-agent.zip", r.status_code == 200 and agent_valid, f"({len(r.data)} bytes)")

    # 9. TDL Templates API
    r = client.get("/api/tally-templates?company=TestCompany&start=20250401&end=20260331&fast=true")
    data = json.loads(r.data)
    test("GET /api/tally-templates", r.status_code == 200 and "<ENVELOPE>" in data.get("vouchers", ""))

    # 10. Cloud Inspect API
    r = client.post("/api/cloud-inspect", json={
        "groups_xml": MOCK_GROUPS_XML,
        "ledgers_xml": MOCK_LEDGERS_XML,
        "company": "Test Enterprise"
    })
    data = json.loads(r.data)
    test("POST /api/cloud-inspect", r.status_code == 200 and "pl_heads" in data and "Indirect Expenses" in data.get("pl_heads", {}))

    # 11. Cloud Extract API (Full OpenXML Generation Test)
    r = client.post("/api/cloud-extract", json={
        "companies_data": [
            {
                "company": "Enterprise Branch 1",
                "groups_xml": MOCK_GROUPS_XML,
                "ledgers_xml": MOCK_LEDGERS_XML,
                "vouchers_xml": MOCK_VOUCHERS_XML
            }
        ],
        "mode": "pl",
        "label": "Income & Expenditure",
        "target_heads": ["Administrative Expenses"],
        "start_date": "20250401",
        "end_date": "20260331",
        "fast_mode": False
    })
    data = json.loads(r.data)
    extract_ok = r.status_code == 200 and data.get("success") and "download_url" in data
    filename = data.get("filename", "")
    test("POST /api/cloud-extract", extract_ok, f"-> {filename}")

    # 12. Download Generated Excel Workbook & Validate OpenXML Structure
    if filename:
        r = client.get(f"/api/download/{filename}")
        excel_valid = False
        sheet_names = []
        if r.status_code == 200:
            try:
                wb = openpyxl.load_workbook(io.BytesIO(r.data), data_only=True)
                sheet_names = wb.sheetnames
                # Check for active TB extract and register sheets
                excel_valid = "Trial Balance Extract" in sheet_names or "Transaction Register" in sheet_names
            except Exception as e:
                print("Excel parse error:", e)
        test(f"GET /api/download/{filename}", excel_valid, f"Sheets: {sheet_names}")

    print("=" * 70)
    print(f"TEST RESULTS: {passed}/{total} Passed (100% Success Rate: {passed == total})")
    print("=" * 70)
    return passed == total

if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
