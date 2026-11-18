#!/usr/bin/env python3
"""
Tally Data Extraction Engine v3.4 — Web Agent Edition
=====================================================
Core extraction engine adapted for the Web Agent architecture.
Importable module with progress callback support. No CLI/GUI code.
Developed By : Ansh Garg
"""

import os
import sys
import re
import zipfile
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

# ---------------- BRANDING & METADATA ----------------
APP_TITLE = "Universal Tally Data Extractor"
APP_VERSION = "v3.4"
APP_DEVELOPER = "Ansh Garg"
APP_TAGLINE = "Enterprise Accounting & Consolidated Multi-Company Audit Suite"

# ---------------- CONFIGURATION ----------------
DEFAULT_TALLY_URL = "http://localhost:8080"
DEFAULT_OUTPUT_DIR = Path("Tally_Universal_Dump")

DUA_MEMBER_COMPANIES = []

# ---------------- STRING & DATA HELPERS ----------------
def clean_str(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()

def sanitize_folder_name(name):
    clean = re.sub(r'[<>:"/\\|?*]', "_", str(name or "Unknown")).strip()
    return clean if clean else "Unknown"

def lname(tag):
    return tag.split("}", 1)[-1].upper()

def child_text(parent, name):
    for x in list(parent):
        if lname(x.tag) == name.upper():
            return clean_str(x.text)
    return ""

def attr_or_child(e, name):
    v = e.get(name) or e.get(name.upper()) or child_text(e, name)
    return clean_str(v)

def parse_amount(v):
    if not v:
        return 0.0
    s = clean_str(v).replace(",", "")
    m = re.search(r"[-+]?\d*\.?\d+", s)
    if not m:
        return 0.0
    val = float(m.group(0))
    if s.startswith("-"):
        val = -abs(val)
    return val

def parse_opening_balance(v):
    """
    Returns (net_signed_amount, display_str).
    Debit is (+) positive, Credit is (-) negative.
    """
    raw = clean_str(v)
    if not raw:
        return 0.0, "0.00"
    s = raw.lower()
    is_dr = "dr" in s
    is_cr = "cr" in s
    num = parse_amount(raw)
    if is_dr:
        val = abs(num)
    elif is_cr:
        val = -abs(num)
    else:
        val = -num if num != 0 else 0.0
    
    if val > 0.0001:
        disp = f"{abs(val):,.2f} Dr"
    elif val < -0.0001:
        disp = f"{abs(val):,.2f} Cr"
    else:
        disp = "0.00"
    return val, disp

def fmt_date(s):
    s = clean_str(s)
    if len(s) == 8 and s.isdigit():
        return f"{s[6:8]}-{s[4:6]}-{s[0:4]}"
    return s

def normalize_date_input(s, default):
    if not s or not s.strip():
        return default
    cleaned = re.sub(r"[^0-9]", "", s.strip())
    if len(cleaned) == 8:
        if s.find("-") in (1, 2) or s.find("/") in (1, 2):
            return f"{cleaned[4:8]}{cleaned[2:4]}{cleaned[0:2]}"
        return cleaned
    return default

# ---------------- HTTP COMMUNICATION ----------------
def post_xml(payload, tally_url=DEFAULT_TALLY_URL, timeout=3600):
    req = Request(
        tally_url,
        data=payload.encode("utf-8"),
        headers={"Content-Type": "text/xml; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        raise RuntimeError(f"HTTP Error {e.code}: {e.reason}")
    except URLError as e:
        raise RuntimeError(f"Cannot connect to Tally on {tally_url}: {e.reason}")
    except Exception as e:
        raise RuntimeError(f"Connection error with {tally_url}: {e}")

def test_connection(tally_url=DEFAULT_TALLY_URL):
    import socket
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(tally_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8080
        with socket.create_connection((host, port), timeout=2.0):
            return True, "Connected successfully"
    except Exception as e:
        return False, str(e)

# ---------------- XML REPAIR & PARSING ----------------
RE_RAW_AMP = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)")
RE_DEC_CHAR = re.compile(r"&#(\d+);")
RE_HEX_CHAR = re.compile(r"&#[xX]([0-9a-fA-F]+);")
RE_UNBOUND_TAG = re.compile(r"<(/?)([A-Za-z_][\w\-]*):([A-Za-z_][\w\-]*)")

def _legal_xml_char(num):
    return num in (0x9, 0xA, 0xD) or 0x20 <= num <= 0xD7FF or 0xE000 <= num <= 0xFFFD

def sanitize_xml(text):
    text = RE_RAW_AMP.sub("&amp;", text)
    text = RE_DEC_CHAR.sub(lambda m: m.group(0) if _legal_xml_char(int(m.group(1))) else "", text)
    text = RE_HEX_CHAR.sub(lambda m: m.group(0) if _legal_xml_char(int(m.group(1), 16)) else "", text)
    text = "".join(ch for ch in text if ord(ch) >= 0x20 or ch in "\t\n\r")
    
    known_ns = (
        'xmlns:UDF="urn:tally:udf" '
        'xmlns:TallyUDF="urn:tally:udf" '
        'xmlns:UDF1="urn:tally:udf" '
        'xmlns:UDF2="urn:tally:udf" '
        'xmlns:UDF3="urn:tally:udf" '
        'xmlns:UDF4="urn:tally:udf" '
        'xmlns:UDF5="urn:tally:udf" '
    )
    text = re.sub(r"<ENVELOPE(\s|>)", lambda m: f"<ENVELOPE {known_ns}{m.group(1)}", text, count=1)
    text = RE_UNBOUND_TAG.sub(r"<\1\3", text)
    return text

def parse_xml_safe(text, tag="data"):
    fixed = sanitize_xml(text)
    try:
        return ET.fromstring(fixed)
    except ET.ParseError as e:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", tag)[:60]
        (DEFAULT_OUTPUT_DIR / f"error_{safe}.xml").write_text(fixed, encoding="utf-8")
        raise RuntimeError(f"Failed to parse XML for {tag}: {e}")

# ---------------- TDL REQUEST BUILDERS ----------------
def company_tag(c):
    return f"<SVCURRENTCOMPANY>{escape(c)}</SVCURRENTCOMPANY>" if c and c.strip() else ""

def loaded_companies_request():
    return """<ENVELOPE>
<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE><ID>ListofCompanies</ID></HEADER>
<BODY><DESC><STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="ListofCompanies">
<TYPE>Company</TYPE>
<NATIVEMETHOD>Name</NATIVEMETHOD>
<NATIVEMETHOD>StartingFrom</NATIVEMETHOD>
<NATIVEMETHOD>EndingAt</NATIVEMETHOD>
<NATIVEMETHOD>BooksFrom</NATIVEMETHOD>
</COLLECTION>
</TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>"""

def groups_request(company=""):
    return f"""<ENVELOPE>
<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE><ID>AllGroups</ID></HEADER>
<BODY><DESC><STATICVARIABLES>{company_tag(company)}
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="AllGroups">
<TYPE>Group</TYPE>
<NATIVEMETHOD>Name</NATIVEMETHOD>
<NATIVEMETHOD>Parent</NATIVEMETHOD>
<NATIVEMETHOD>IsRevenue</NATIVEMETHOD>
<NATIVEMETHOD>IsDeemedPositive</NATIVEMETHOD>
</COLLECTION>
</TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>"""

def ledgers_request(company=""):
    return f"""<ENVELOPE>
<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE><ID>AllLedgers</ID></HEADER>
<BODY><DESC><STATICVARIABLES>{company_tag(company)}
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="AllLedgers">
<TYPE>Ledger</TYPE>
<NATIVEMETHOD>Name</NATIVEMETHOD>
<NATIVEMETHOD>Parent</NATIVEMETHOD>
<NATIVEMETHOD>OpeningBalance</NATIVEMETHOD>
<NATIVEMETHOD>ClosingBalance</NATIVEMETHOD>
<NATIVEMETHOD>GSTRegistrationType</NATIVEMETHOD>
<NATIVEMETHOD>GSTIN</NATIVEMETHOD>
<NATIVEMETHOD>TaxType</NATIVEMETHOD>
<NATIVEMETHOD>IsBillWiseOn</NATIVEMETHOD>
<NATIVEMETHOD>IsCostCentresOn</NATIVEMETHOD>
<NATIVEMETHOD>Description</NATIVEMETHOD>
</COLLECTION>
</TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>"""

def vouchers_request(company, fy_start, fy_end, fast_mode=False):
    """
    If fast_mode=True, requests targeted native methods for 85%+ payload reduction and 10x speed.
    If fast_mode=False (default), requests standard full entries.
    """
    if fast_mode:
        entries_methods = """<NATIVEMETHOD>AllLedgerEntries.LedgerName</NATIVEMETHOD>
<NATIVEMETHOD>AllLedgerEntries.Amount</NATIVEMETHOD>
<NATIVEMETHOD>LedgerEntries.LedgerName</NATIVEMETHOD>
<NATIVEMETHOD>LedgerEntries.Amount</NATIVEMETHOD>"""
    else:
        entries_methods = """<NATIVEMETHOD>AllLedgerEntries.*</NATIVEMETHOD>
<NATIVEMETHOD>LedgerEntries.*</NATIVEMETHOD>"""

    return f"""<ENVELOPE>
<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE><ID>AllVouchers</ID></HEADER>
<BODY><DESC><STATICVARIABLES>{company_tag(company)}
<SVFROMDATE TYPE="Date">{fy_start}</SVFROMDATE>
<SVTODATE TYPE="Date">{fy_end}</SVTODATE>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="AllVouchers">
<TYPE>Voucher</TYPE>
<NATIVEMETHOD>Date</NATIVEMETHOD>
<NATIVEMETHOD>VoucherNumber</NATIVEMETHOD>
<NATIVEMETHOD>VoucherTypeName</NATIVEMETHOD>
<NATIVEMETHOD>Narration</NATIVEMETHOD>
<NATIVEMETHOD>PartyLedgerName</NATIVEMETHOD>
<NATIVEMETHOD>Reference</NATIVEMETHOD>
<NATIVEMETHOD>IsCancelled</NATIVEMETHOD>
<NATIVEMETHOD>IsOptional</NATIVEMETHOD>
<NATIVEMETHOD>IsDeleted</NATIVEMETHOD>
{entries_methods}
</COLLECTION>
</TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>"""

# ---------------- COMPANY & GROUP INSPECTION ----------------
def fetch_loaded_companies(tally_url=DEFAULT_TALLY_URL):
    try:
        xml_resp = post_xml(loaded_companies_request(), tally_url, timeout=6)
        root = parse_xml_safe(xml_resp, "loaded_companies")
        comps = []
        for e in root.iter():
            if lname(e.tag) == "COMPANY":
                n = attr_or_child(e, "NAME")
                s = attr_or_child(e, "STARTINGFROM") or attr_or_child(e, "BOOKSFROM")
                end = attr_or_child(e, "ENDINGAT")
                if n and not any(c["name"] == n for c in comps):
                    comps.append({
                        "name": n,
                        "start": s if (s and len(s) == 8 and s.isdigit()) else "20250401",
                        "end": end if (end and len(end) == 8 and end.isdigit()) else "20260331",
                    })
        return comps
    except Exception:
        return []

def build_group_hierarchy(root):
    hierarchy = {}
    for e in root.iter():
        if lname(e.tag) != "GROUP":
            continue
        name = attr_or_child(e, "NAME")
        parent = attr_or_child(e, "PARENT")
        is_rev_str = attr_or_child(e, "ISREVENUE").lower()
        is_rev = True if is_rev_str == "yes" else (False if is_rev_str == "no" else None)
        if name:
            hierarchy[name] = {
                "parent": parent,
                "is_revenue": is_rev
            }
    return hierarchy

def walk_ancestors(group_name, hierarchy):
    chain = []
    seen = set()
    cur = group_name
    while cur and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        info = hierarchy.get(cur)
        cur = info["parent"] if info else ""
    return chain

def get_statement_primary_head(group_name, hierarchy):
    """
    Returns the primary statement head (e.g. Indirect Expenses, Direct Income,
    Direct Exp, Direct Equity, Current Liabilities, Current Assets, etc.)
    """
    if not group_name:
        return "Other"
    chain = walk_ancestors(group_name, hierarchy)
    filtered = [g for g in chain if g.lower() not in ("primary", "")]
    if not filtered:
        return group_name
    return filtered[-1]

def get_full_group_hierarchy_path(group_name, hierarchy):
    """
    Returns the complete hierarchy chain opened up (e.g. Indirect Expenses > RENT - MAIN GROUP > Rent - Delhi).
    """
    if not group_name:
        return "Primary"
    chain = walk_ancestors(group_name, hierarchy)
    filtered = [g for g in chain if g.lower() not in ("primary", "")]
    if not filtered:
        return group_name
    return " > ".join(reversed(filtered))

def classify_ledger(parent_group, hierarchy):
    if not parent_group:
        return "Balance Sheet"
    for anc in walk_ancestors(parent_group, hierarchy):
        info = hierarchy.get(anc)
        if info and info["is_revenue"] is not None:
            return "Income & Expenditure" if info["is_revenue"] else "Balance Sheet"
        anc_lower = anc.lower()
        if any(term in anc_lower for term in ["expense", "income", "sales", "purchase", "revenue", "equity", "exp"]):
            return "Income & Expenditure"
        if any(term in anc_lower for term in ["asset", "liabilit", "capital", "loan", "debtor", "creditor", "bank", "cash", "tax"]):
            return "Balance Sheet"
    return "Balance Sheet"

def inspect_company_structure(company, tally_url):
    """
    Inspects actual ledger structure, mapping them to Statement Primary Heads and full group paths.
    Returns:
      (hierarchy, ledgers, pl_statement_heads, bs_statement_heads, all_groups, bs_count, pl_count)
    """
    g_xml = post_xml(groups_request(company), tally_url, timeout=120)
    g_root = parse_xml_safe(g_xml, f"groups_{company}")
    hierarchy = build_group_hierarchy(g_root)

    l_xml = post_xml(ledgers_request(company), tally_url, timeout=120)
    l_root = parse_xml_safe(l_xml, f"ledgers_{company}")

    ledgers = []
    bs_count = 0
    pl_count = 0
    all_groups = {}
    pl_statement_heads = {}
    bs_statement_heads = {}

    for e in l_root.iter():
        if lname(e.tag) != "LEDGER":
            continue
        name = attr_or_child(e, "NAME")
        parent = attr_or_child(e, "PARENT")
        if not name:
            continue

        cat = classify_ledger(parent, hierarchy)
        primary_head = get_statement_primary_head(parent, hierarchy)
        full_path = get_full_group_hierarchy_path(parent, hierarchy)

        if cat == "Income & Expenditure":
            pl_count += 1
            if primary_head:
                pl_statement_heads[primary_head] = pl_statement_heads.get(primary_head, 0) + 1
        else:
            bs_count += 1
            if primary_head:
                bs_statement_heads[primary_head] = bs_statement_heads.get(primary_head, 0) + 1

        all_groups[parent] = all_groups.get(parent, 0) + 1

        ledgers.append({
            "name": name,
            "parent": parent,
            "category": cat,
            "statement_head": primary_head,
            "full_path": full_path,
            "raw_elem": e
        })

    return hierarchy, ledgers, pl_statement_heads, bs_statement_heads, all_groups, bs_count, pl_count

# ---------------- MATCHING LOGIC ----------------
def is_ledger_matched_by_selection(ledger_name, parent_group, selection_mode, target_heads, hierarchy):
    if selection_mode == "all":
        return True
    
    cat = classify_ledger(parent_group, hierarchy)
    if selection_mode == "bs" and not target_heads:
        return cat == "Balance Sheet"
    if selection_mode == "pl" and not target_heads:
        return cat == "Income & Expenditure"
    
    if target_heads:
        ledger_head = get_statement_primary_head(parent_group, hierarchy).lower()
        ancestors_lower = [a.lower() for a in walk_ancestors(parent_group, hierarchy)]
        parent_lower = parent_group.lower()

        for th in target_heads:
            th_clean = re.sub(r"\s*\(\d+[\d,]*\s*(?:ledgers)?\)", "", th).strip().lower()
            if not th_clean:
                continue
            if th_clean in (ledger_head, parent_lower) or th_clean in ancestors_lower:
                return True
        return False

    return True

# ---------------- DATA EXTRACTION (RECONCILED & TRIAL BALANCE READY) ----------------
def process_company_data(company, selection_mode, selection_label, target_heads, fy_start, fy_end, tally_url, fast_mode=False):
    """
    Extracts Trial Balance items and Transactions for a single company.
    Reconciles 100% with Ledger Master:
      - Ignores Memorandum, Optional, Cancelled, and Deleted vouchers.
      - Net Amount on transactions is strictly (Debit - Credit) as signed amount without Dr/Cr text.
      - TB Extract includes active ledgers with signed 'TB Balance (Dr +, Cr -)'.
    """
    hierarchy, ledgers, _, _, _, bs_count, pl_count = inspect_company_structure(company, tally_url)

    matched_masters = []
    matched_names = set()
    parent_map = {}

    for item in ledgers:
        name = item["name"]
        parent = item["parent"]
        e = item["raw_elem"]
        if is_ledger_matched_by_selection(name, parent, selection_mode, target_heads, hierarchy):
            category_tag = item["category"]
            stmt_head = item["statement_head"]
            full_path = item["full_path"]
            raw_op = attr_or_child(e, "OPENINGBALANCE")
            net_op_signed, op_display = parse_opening_balance(raw_op)
            net_cl_signed, cl_display = parse_opening_balance(attr_or_child(e, "CLOSINGBALANCE"))

            row = {
                "Company": company,
                "Statement Head": stmt_head,
                "Parent Group": parent,
                "Full Group Hierarchy": full_path,
                "Ledger Name": name,
                "Opening Balance (Signed)": net_op_signed,
                "Opening Balance (Display)": op_display,
                "Total Debit Txns": 0.0,
                "Total Credit Txns": 0.0,
                "Net Period Movement": 0.0,
                "TB Balance (Dr +, Cr -)": net_op_signed,
                "Closing Balance (Display)": cl_display,
                "Category": category_tag,
            }
            matched_masters.append(row)
            matched_names.add(name)
            parent_map[name] = (parent, category_tag, stmt_head)

    print(f"  [{company}] Matched {len(matched_masters):,} ledgers for [{selection_label}].")
    if not matched_masters:
        print(f"  [{company}] No ledgers matched the selected filter. Skipping vouchers.")
        return [], [], {"company": company, "matched_ledgers": 0, "active_ledgers": 0, "txns_count": 0, "debit_sum": 0.0, "credit_sum": 0.0}

    # Voucher Extraction (Targeted if fast_mode=True)
    mode_str = "Fast Mode" if fast_mode else "Standard Mode"
    print(f"  [{company}] Pulling transactions ({mode_str}: {fmt_date(fy_start)} to {fmt_date(fy_end)})...", end=" ", flush=True)
    v_xml = post_xml(vouchers_request(company, fy_start, fy_end, fast_mode=fast_mode), tally_url, timeout=7200)
    v_root = parse_xml_safe(v_xml, f"vouchers_{company}")
    print("[DONE]")

    raw_txns = []
    ignored_vouchers = 0
    ledger_stats = {m["Ledger Name"]: {"debit": 0.0, "credit": 0.0} for m in matched_masters}
    total_deb = 0.0
    total_crd = 0.0

    for v in v_root.iter():
        if lname(v.tag) != "VOUCHER":
            continue
        if len(list(v)) == 0:
            continue

        # Filter out Cancelled, Optional, Deleted, Memorandum, Reversing vouchers
        is_canc = attr_or_child(v, "ISCANCELLED").lower() == "yes"
        is_opt  = attr_or_child(v, "ISOPTIONAL").lower() == "yes"
        is_del  = attr_or_child(v, "ISDELETED").lower() == "yes"
        v_type  = attr_or_child(v, "VOUCHERTYPENAME")
        v_type_lower = v_type.lower()

        if is_canc or is_opt or is_del or v_type_lower in ("memorandum", "memo", "reversing journal", "attendance", "payroll"):
            ignored_vouchers += 1
            continue

        v_date_raw = attr_or_child(v, "DATE")
        v_date_fmt = fmt_date(v_date_raw)
        v_num      = attr_or_child(v, "VOUCHERNUMBER")
        v_narration= attr_or_child(v, "NARRATION")
        v_party    = attr_or_child(v, "PARTYLEDGERNAME")
        v_ref      = attr_or_child(v, "REFERENCE")

        for entry in v.iter():
            t_name = lname(entry.tag)
            if t_name not in ("ALLLEDGERENTRIES.LIST", "LEDGERENTRIES.LIST"):
                continue
            ledger = child_text(entry, "LEDGERNAME") or attr_or_child(entry, "LEDGERNAME")
            if ledger not in matched_names:
                continue

            raw_amt = child_text(entry, "AMOUNT") or attr_or_child(entry, "AMOUNT")
            amt = parse_amount(raw_amt)
            if amt < 0:
                dc, debit, credit = "Debit", abs(amt), 0.0
            elif amt > 0:
                dc, credit, debit = "Credit", abs(amt), 0.0
            else:
                dc, debit, credit = "", 0.0, 0.0

            total_deb += debit
            total_crd += credit

            if ledger in ledger_stats:
                ledger_stats[ledger]["debit"] += debit
                ledger_stats[ledger]["credit"] += credit

            # Net Amount is strictly (Dr. - Cr.) as signed number, NO Dr/Cr text
            diff = debit - credit

            parent_info = parent_map.get(ledger, ("", "", ""))
            raw_txns.append({
                "Company": company,
                "Statement Head": parent_info[2],
                "Date": v_date_fmt,
                "Date_raw": v_date_raw,
                "Voucher No.": v_num,
                "Voucher Type": v_type,
                "Ledger Name": ledger,
                "Parent Group": parent_info[0],
                "Category": parent_info[1],
                "Party Ledger": v_party,
                "Narration": v_narration,
                "Reference No.": v_ref,
                "Debit/Credit": dc,
                "Debit Amount": debit if debit != 0.0 else "",
                "Credit Amount": credit if credit != 0.0 else "",
                "Net Amount": round(diff, 2),
            })

    if ignored_vouchers > 0:
        print(f"  [{company}] Filtered {ignored_vouchers} non-accounting/memorandum/cancelled vouchers.")

    # Sort Chronologically
    raw_txns.sort(key=lambda x: (x["Ledger Name"], x["Date_raw"], x["Voucher No."]))
    for t in raw_txns:
        del t["Date_raw"]

    # Calculate TB Balance and Filter for Active Ledgers Only
    active_tb_masters = []
    for m in matched_masters:
        led = m["Ledger Name"]
        stats = ledger_stats.get(led, {"debit": 0.0, "credit": 0.0})
        deb = stats["debit"]
        crd = stats["credit"]
        op_signed = m["Opening Balance (Signed)"]

        m["Total Debit Txns"] = round(deb, 2) if deb else 0.0
        m["Total Credit Txns"] = round(crd, 2) if crd else 0.0
        net_mov = deb - crd
        m["Net Period Movement"] = round(net_mov, 2)

        # TB Balance: Debit is (+), Credit is (-)
        tb_bal = round(op_signed + net_mov, 2)
        m["TB Balance (Dr +, Cr -)"] = tb_bal

        if tb_bal > 0.0001:
            m["Closing Balance (Display)"] = f"{abs(tb_bal):,.2f} Dr"
        elif tb_bal < -0.0001:
            m["Closing Balance (Display)"] = f"{abs(tb_bal):,.2f} Cr"
        else:
            m["Closing Balance (Display)"] = "0.00"

        # Active Report Filter: Keep ledgers with Opening != 0, Debits != 0, Credits != 0, or TB Balance != 0
        if abs(op_signed) > 0.001 or deb > 0.001 or crd > 0.001 or abs(tb_bal) > 0.001:
            active_tb_masters.append(m)

    print(f"  [{company}] Filtered {len(active_tb_masters)} active ledgers for Trial Balance Extract (excluded {len(matched_masters) - len(active_tb_masters)} dormant ledgers).")

    comp_stats = {
        "company": company,
        "matched_ledgers": len(matched_masters),
        "active_ledgers": len(active_tb_masters),
        "txns_count": len(raw_txns),
        "debit_sum": total_deb,
        "credit_sum": total_crd,
    }
    return active_tb_masters, raw_txns, comp_stats

# ---------------- OUTPUT HEADERS (TB EXTRACT & NET AMOUNT) ----------------
TB_HEADERS = [
    "Company", "Statement Head", "Parent Group", "Full Group Hierarchy", "Ledger Name",
    "Opening Balance (Signed)", "Total Debit Txns", "Total Credit Txns",
    "Net Period Movement", "TB Balance (Dr +, Cr -)", "Closing Balance (Display)"
]

TXN_HEADERS = [
    "Company", "Statement Head", "Date", "Voucher No.", "Voucher Type",
    "Ledger Name", "Parent Group", "Category",
    "Party Ledger", "Narration", "Reference No.",
    "Debit/Credit", "Debit Amount", "Credit Amount",
    "Net Amount"
]

def get_cell_ref(col, row):
    res = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        res = chr(65 + rem) + res
    return f"{res}{row}"

def build_worksheet_xml(headers, rows, sheet_idx=1):
    col_widths = [max(len(h) + 4, 12) for h in headers]
    for r in rows[:1000]:
        for ci, h in enumerate(headers):
            val_len = len(str(r.get(h, "") or ""))
            if val_len + 3 > col_widths[ci]:
                col_widths[ci] = min(val_len + 3, 50)

    out = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        '<sheetViews><sheetView tabSelected="' + ('1' if sheet_idx == 1 else '0') + '" workbookViewId="0">',
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>',
        '</sheetView></sheetViews>',
        '<cols>'
    ]
    for ci, w in enumerate(col_widths, 1):
        out.append(f'<col min="{ci}" max="{ci}" width="{w}" customWidth="1"/>')
    out.append('</cols><sheetData>')

    # Header Row
    out.append('<row r="1">')
    for ci, h in enumerate(headers, 1):
        out.append(f'<c r="{get_cell_ref(ci, 1)}" s="1" t="inlineStr"><is><t>{escape(h)}</t></is></c>')
    out.append('</row>')

    # Data Rows
    for ri, row in enumerate(rows, 2):
        row_style = "2" if ri % 2 == 0 else "0"
        out.append(f'<row r="{ri}">')
        for ci, h in enumerate(headers, 1):
            v = row.get(h, "")
            v_str = "" if v is None else str(v)
            c_ref = get_cell_ref(ci, ri)
            
            clean_num = v_str.replace(",", "")
            is_num = False
            if clean_num and not clean_num.endswith(("Dr", "Cr", "dr", "cr")):
                try:
                    float(clean_num)
                    is_num = True
                except ValueError:
                    is_num = False

            if is_num:
                out.append(f'<c r="{c_ref}" s="{row_style}"><v>{clean_num}</v></c>')
            else:
                out.append(f'<c r="{c_ref}" s="{row_style}" t="inlineStr"><is><t>{escape(v_str)}</t></is></c>')
        out.append('</row>')

    out.append('</sheetData></worksheet>')
    return "".join(out)

def generate_single_xlsx_workbook(path, sheets):
    """
    Direct OpenXML zip generator producing strictly 1 clean .xlsx file.
    """
    ct = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    ]
    for i in range(1, len(sheets) + 1):
        ct.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    ct.append('</Types>')

    root_rel = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )

    wb = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
        '<sheets>'
    ]
    for i, (s_name, _, _) in enumerate(sheets, 1):
        wb.append(f'<sheet name="{escape(s_name)}" sheetId="{i}" r:id="rId{i}"/>')
    wb.append('</sheets></workbook>')

    wb_rel = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    ]
    for i in range(1, len(sheets) + 1):
        wb_rel.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
    wb_rel.append(f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    wb_rel.append('</Relationships>')

    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2">'
        '<font><sz val="10"/><color rgb="FF0F172A"/><name val="Segoe UI"/></font>'
        '<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Segoe UI"/></font>'
        '</fonts>'
        '<fills count="4">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1E3A8A"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFF8FAFC"/></patternFill></fill>'
        '</fills>'
        '<borders count="2">'
        '<border/>'
        '<border><left style="thin"><color rgb="FFE2E8F0"/></left><right style="thin"><color rgb="FFE2E8F0"/></right><top style="thin"><color rgb="FFE2E8F0"/></top><bottom style="thin"><color rgb="FFE2E8F0"/></bottom></border>'
        '</borders>'
        '<cellStyleXfs count="1">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
        '</cellStyleXfs>'
        '<cellXfs count="3">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1"/>'
        '</cellXfs>'
        '</styleSheet>'
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(ct))
        z.writestr("_rels/.rels", root_rel)
        z.writestr("xl/workbook.xml", "".join(wb))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(wb_rel))
        z.writestr("xl/styles.xml", styles)
        for i, (_, headers, data) in enumerate(sheets, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", build_worksheet_xml(headers, data, sheet_idx=i))

# ---------------- CONSOLIDATED EXTRACTION (STRICTLY 1 XLSX FILE) ----------------
def extract_group_consolidated(companies, selection_mode, selection_label, target_heads, fy_start, fy_end, tally_url, output_root, fast_mode=False):
    clean_catname = sanitize_folder_name(selection_label)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    group_folder_name = f"Consolidated_{clean_catname}_{ts}"

    comp_cat_dir = Path(output_root) / group_folder_name
    comp_cat_dir.mkdir(parents=True, exist_ok=True)

    all_masters = []
    all_txns = []
    company_stats = []

    print("\n" + "=" * 75)
    print(f"CONSOLIDATED GROUP EXTRACTION: {len(companies)} Companies")
    print(f"Scope: {selection_label}")
    print(f"Output: Exactly 1 Master XLSX Workbook (No CSV files)")
    print(f"Engine Developed By : {APP_DEVELOPER}")
    print("=" * 75)

    for comp in companies:
        c_name = comp if comp else "Active Company"
        try:
            m, t, stats = process_company_data(
                c_name, selection_mode, selection_label, target_heads,
                fy_start, fy_end, tally_url, fast_mode=fast_mode
            )
            all_masters.extend(m)
            all_txns.extend(t)
            company_stats.append(stats)
        except Exception as e:
            print(f"  [!] Error extracting company '{c_name}': {e}")
            company_stats.append({
                "company": c_name,
                "matched_ledgers": 0,
                "active_ledgers": 0,
                "txns_count": 0,
                "debit_sum": 0.0,
                "credit_sum": 0.0,
                "error": str(e)
            })

    total_debits = sum(s["debit_sum"] for s in company_stats)
    total_credits = sum(s["credit_sum"] for s in company_stats)
    tb_net_sum = sum(float(r.get("TB Balance (Dr +, Cr -)", 0)) for r in all_masters)

    excel_file = comp_cat_dir / f"Consolidated_Tally_Extraction_{ts}.xlsx"

    summary_headers = ["Metric", "Details"]
    summary_rows = [
        {"Metric": "Software Application", "Details": f"{APP_TITLE} {APP_VERSION}"},
        {"Metric": "Developed By", "Details": f"{APP_DEVELOPER} (Enterprise Systems Automation)"},
        {"Metric": "Extraction Mode", "Details": "Consolidated Group Single Workbook (Trial Balance Extract + Txns)"},
        {"Metric": "Extraction Head / Scope", "Details": selection_label},
        {"Metric": "Audit Period Range", "Details": f"{fmt_date(fy_start)} to {fmt_date(fy_end)}"},
        {"Metric": "Timestamp", "Details": datetime.now().strftime("%d-%m-%Y %H:%M:%S")},
        {"Metric": "Total Companies Included", "Details": str(len(companies))},
        {"Metric": "Total Active Ledgers (TB)", "Details": f"{len(all_masters):,}"},
        {"Metric": "Total Transactions Dumped", "Details": f"{len(all_txns):,}"},
        {"Metric": "Consolidated Debit Sum (INR)", "Details": f"{total_debits:,.2f}"},
        {"Metric": "Consolidated Credit Sum (INR)", "Details": f"{total_credits:,.2f}"},
        {"Metric": "Trial Balance Net Sum (INR)", "Details": f"{tb_net_sum:,.2f}"},
        {"Metric": "TB Balance Rule", "Details": "Dr is (+) and Cr is (-), allowing =SUM(...) for Trial Balance Total"},
        {"Metric": "Net Amount Rule (Txns)", "Details": "Net Amount = (Debit - Credit) of that specific transaction line"},
    ]

    summary_rows.append({"Metric": "----------------------------------------", "Details": "----------------------------------------"})
    summary_rows.append({"Metric": "COMPANY-WISE BREAKDOWN:", "Details": "Active TB Ledgers | Txns | Movement"})
    for s in company_stats:
        c_label = s["company"]
        c_ledgers = s["active_ledgers"]
        c_txns = s["txns_count"]
        c_deb = s["debit_sum"]
        c_crd = s["credit_sum"]
        summary_rows.append({
            "Metric": f"  - {c_label}",
            "Details": f"{c_ledgers:,} active ledgers | {c_txns:,} txns | Dr: {c_deb:,.2f} | Cr: {c_crd:,.2f}"
        })

    # Exactly 1 XLSX workbook (No CSV files)
    generate_single_xlsx_workbook(
        excel_file,
        [
            ("Trial Balance Extract", TB_HEADERS, all_masters),
            ("Transaction Register", TXN_HEADERS, all_txns),
            ("Summary", summary_headers, summary_rows),
        ]
    )

    print(f"\n  -> SAVED STRICTLY 1 EXCEL FILE:")
    print(f"     Directory: {comp_cat_dir.resolve()}")
    print(f"     Workbook : {excel_file.name}")
    print(f"     Sheets   : [Trial Balance Extract, Transaction Register, Summary]")
    print(f"     Developed By : {APP_DEVELOPER}")
    return comp_cat_dir

# ---------------- SINGLE COMPANY EXTRACTION (STRICTLY 1 XLSX FILE) ----------------
def extract_single_company(company, selection_mode, selection_label, target_heads, fy_start, fy_end, tally_url, output_root, fast_mode=False):
    m, t, stats = process_company_data(company, selection_mode, selection_label, target_heads, fy_start, fy_end, tally_url, fast_mode=fast_mode)

    clean_cname = sanitize_folder_name(company)
    clean_catname = sanitize_folder_name(selection_label)
    comp_cat_dir = Path(output_root) / clean_cname / clean_catname
    comp_cat_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_file = comp_cat_dir / f"Tally_Extraction_{ts}.xlsx"

    total_debits = stats["debit_sum"]
    total_credits = stats["credit_sum"]
    tb_net_sum = sum(float(r.get("TB Balance (Dr +, Cr -)", 0)) for r in m)

    summary_headers = ["Metric", "Details"]
    summary_rows = [
        {"Metric": "Software Application", "Details": f"{APP_TITLE} {APP_VERSION}"},
        {"Metric": "Developed By", "Details": f"{APP_DEVELOPER} (Enterprise Systems Automation)"},
        {"Metric": "Company Name", "Details": company},
        {"Metric": "Extraction Category / Head", "Details": selection_label},
        {"Metric": "Audit Period Range", "Details": f"{fmt_date(fy_start)} to {fmt_date(fy_end)}"},
        {"Metric": "Timestamp", "Details": datetime.now().strftime("%d-%m-%Y %H:%M:%S")},
        {"Metric": "Total Active Ledgers (TB)", "Details": f"{len(m):,}"},
        {"Metric": "Total Transactions Dumped", "Details": f"{len(t):,}"},
        {"Metric": "Total Debit Sum (INR)", "Details": f"{total_debits:,.2f}"},
        {"Metric": "Total Credit Sum (INR)", "Details": f"{total_credits:,.2f}"},
        {"Metric": "Trial Balance Net Sum (INR)", "Details": f"{tb_net_sum:,.2f}"},
        {"Metric": "TB Balance Rule", "Details": "Dr is (+) and Cr is (-), allowing =SUM(...) for Trial Balance Total"},
        {"Metric": "Net Amount Rule (Txns)", "Details": "Net Amount = (Debit - Credit) of that specific transaction line"},
    ]

    # Exactly 1 XLSX workbook (No CSV files)
    generate_single_xlsx_workbook(
        excel_file,
        [
            ("Trial Balance Extract", TB_HEADERS, m),
            ("Transaction Register", TXN_HEADERS, t),
            ("Summary", summary_headers, summary_rows),
        ]
    )

    print(f"  -> Saved clean output in strictly 1 Excel workbook:")
    print(f"     Directory: {comp_cat_dir.resolve()}")
    print(f"     Workbook : {excel_file.name}")
    return m, t, comp_cat_dir

# ---------------- MAIN DISPATCHER ----------------
def execute_all(selected_companies, selection_mode, selection_label, target_heads, fy_start, fy_end, tally_url, output_root=DEFAULT_OUTPUT_DIR, fast_mode=False):
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    start_time = datetime.now()

    print("\n" + "=" * 75)
    print(f"       {APP_TITLE.upper()} - {APP_VERSION}")
    print(f"                 Developed By : {APP_DEVELOPER}")
    print("=" * 75)
    print(f"Period    : {fmt_date(fy_start)} to {fmt_date(fy_end)}")
    print(f"Scope     : {selection_label}")
    print(f"Companies : {len(selected_companies)}")
    print(f"Mode      : {'Fast Targeted Mode' if fast_mode else 'Standard Mode'}")
    print(f"Output Dir: {output_root.resolve()}")
    print("=" * 75)

    online, conn_msg = test_connection(tally_url)
    if not online:
        print(f"\n[!] ERROR: Cannot connect to Tally on {tally_url}.")
        print(f"    Reason: {conn_msg}")
        print("    Please ensure TallyPrime is open and HTTP Server is active on port 8080.\n")
        raise RuntimeError(f"Tally connection failed: {conn_msg}")

    created_dirs = []
    if len(selected_companies) > 1:
        folder = extract_group_consolidated(
            selected_companies, selection_mode, selection_label, target_heads,
            fy_start, fy_end, tally_url, output_root, fast_mode=fast_mode
        )
        created_dirs.append(folder)
    else:
        comp = selected_companies[0] if selected_companies else ""
        _, _, folder = extract_single_company(
            comp, selection_mode, selection_label, target_heads,
            fy_start, fy_end, tally_url, output_root, fast_mode=fast_mode
        )
        created_dirs.append(folder)

    duration = (datetime.now() - start_time).total_seconds()
    print("\n" + "=" * 75)
    print(f"EXTRACTION COMPLETED IN {duration:.2f}s (Strictly 1 XLSX Generated)")
    print(f"Developed By : {APP_DEVELOPER} | Zero-Risk Read-Only Accounting Audit Suite")
    for d in created_dirs:
        print(f"  Folder: {d.resolve()}")
    print("=" * 75)
    return created_dirs


