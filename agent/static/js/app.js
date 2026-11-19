/**
 * Universal Tally Data Extractor v3.4 — Web & Extension Client App
 * Developed By : Ansh Garg
 */

// Application State
const state = {
  tallyOnline: false,
  isExtensionMode: false,
  companies: [],
  selectedCompany: "",
  consolidateAll: false,
  statementType: "pl", // pl, bs, all
  scopeMode: "all_stmt", // all_stmt, custom
  plHeads: {},
  bsHeads: {},
  plCount: 0,
  bsCount: 0,
  totalCount: 0,
  headCheckboxes: {}, // headName -> boolean
  activeTaskId: null,
  isExtracting: false,
  lastLogIndex: 0,
  pollInterval: null,
  currentDownloadFile: null,
  licenseInfo: null
};

// ================= EXTENSION BRIDGE PROMISE HELPER =================
function callTallyBridge(action, payload = null, timeout = 60000) {
  return new Promise((resolve) => {
    if (!window.__TALLY_EXTENSION_INSTALLED__) {
      return resolve({ success: false, notInstalled: true, error: "Chrome extension not detected" });
    }

    const requestId = "req_" + Math.random().toString(36).substring(2, 9);
    function onMsg(e) {
      if (e.source === window && e.data && e.data.source === "TALLY_EXTENSION" && e.data.requestId === requestId) {
        window.removeEventListener("message", onMsg);
        resolve(e.data.data);
      }
    }
    window.addEventListener("message", onMsg);
    window.postMessage({ source: "TALLY_WEB_PAGE", action, requestId, payload, timeout }, "*");

    setTimeout(() => {
      window.removeEventListener("message", onMsg);
      resolve({ success: false, error: "Tally Bridge request timeout" });
    }, timeout + 5000);
  });
}

function parseCompaniesFromXML(xmlText) {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlText, "text/xml");
    const comps = [];
    const compElements = doc.querySelectorAll("COMPANY");
    compElements.forEach((el) => {
      const nameEl = el.querySelector("NAME");
      const startEl = el.querySelector("STARTINGFROM") || el.querySelector("BOOKSFROM");
      const endEl = el.querySelector("ENDINGAT");
      if (nameEl) {
        const name = nameEl.textContent.trim();
        const start = startEl ? startEl.textContent.trim() : "20250401";
        const end = endEl ? endEl.textContent.trim() : "20260331";
        if (name && !comps.some(c => c.name === name)) {
          comps.push({ name, start, end });
        }
      }
    });
    return comps;
  } catch (e) {
    return [];
  }
}

// ================= DOM CONTENT LOADED =================
document.addEventListener("DOMContentLoaded", () => {
  initApp();
  // Listen for extension injection event if it loads after DOM
  window.addEventListener("TallyExtensionReady", () => {
    state.isExtensionMode = true;
    refreshTallyStatus();
  });
});

async function initApp() {
  await refreshTallyStatus();
  await refreshCompanies();
  await loadLicenseInfo();
  await loadPreviousOutputs();
}

// ================= TALLY STATUS =================
async function refreshTallyStatus() {
  const badge = document.getElementById("tally-status-badge");
  const banner = document.getElementById("tally-offline-banner");

  badge.className = "status-pill status-checking";
  badge.querySelector(".status-text").textContent = "Checking Tally...";

  // 1. Try Chrome Extension Bridge first
  if (window.__TALLY_EXTENSION_INSTALLED__) {
    state.isExtensionMode = true;
    const extRes = await callTallyBridge("CHECK_TALLY");
    if (extRes && extRes.online) {
      state.tallyOnline = true;
      badge.className = "status-pill status-online";
      badge.querySelector(".status-text").textContent = "Tally: ONLINE (Extension)";
      banner.style.display = "none";
      appendTerminalLog("Chrome Extension Bridge connected to Tally (localhost:8080).", "text-success");
      return;
    }
  }

  // 2. Try Local Agent Server API
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    state.tallyOnline = data.tally_online;

    if (state.tallyOnline) {
      badge.className = "status-pill status-online";
      badge.querySelector(".status-text").textContent = "Tally: ONLINE";
      banner.style.display = "none";
      appendTerminalLog("Connected to TallyPrime / Tally.ERP 9 on port 8080.", "text-success");
    } else {
      badge.className = "status-pill status-offline";
      badge.querySelector(".status-text").textContent = "Tally: OFFLINE";
      banner.style.display = "flex";
      appendTerminalLog("Tally is currently offline or unreachable on localhost:8080.", "text-danger");
    }
  } catch (err) {
    state.tallyOnline = false;
    badge.className = "status-pill status-offline";
    badge.querySelector(".status-text").textContent = "Tally: Disconnected";
    banner.style.display = "flex";
  }
}

// ================= COMPANIES =================
async function refreshCompanies() {
  const select = document.getElementById("company-select");
  select.innerHTML = '<option value="">[Scanning Tally companies...]</option>';

  // 1. If Extension Mode: fetch loaded companies XML directly from Tally
  if (state.isExtensionMode) {
    try {
      const tplRes = await fetch("/api/tally-templates");
      const tplData = await tplRes.json();
      const tRes = await callTallyBridge("POST_TALLY", tplData.loaded_companies);

      if (tRes && tRes.success && tRes.xml) {
        state.companies = parseCompaniesFromXML(tRes.xml);
        populateCompanyDropdown();
        return;
      }
    } catch (err) {
      // Fallback
    }
  }

  // 2. Local Agent Mode
  try {
    const res = await fetch("/api/companies");
    const data = await res.json();
    state.companies = data.companies || [];
    populateCompanyDropdown();
  } catch (err) {
    select.innerHTML = '<option value="">[Could not load companies]</option>';
  }
}

function populateCompanyDropdown() {
  const select = document.getElementById("company-select");
  select.innerHTML = "";

  if (state.companies.length > 0) {
    state.companies.forEach((comp) => {
      const opt = document.createElement("option");
      opt.value = comp.name;
      opt.textContent = `${comp.name} (FY: ${formatTallyDate(comp.start)} to ${formatTallyDate(comp.end)})`;
      select.appendChild(opt);
    });

    if (state.companies.length > 1) {
      const optAll = document.createElement("option");
      optAll.value = "__ALL__";
      optAll.textContent = "★ ALL Loaded Companies in Tally (Consolidated)";
      select.appendChild(optAll);
    }

    state.selectedCompany = state.companies[0].name;
    select.value = state.selectedCompany;
    onCompanyChanged();
  } else {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "[Active Company in Tally]";
    select.appendChild(opt);
    state.selectedCompany = "";
    onCompanyChanged();
  }
}

function onCompanyChanged() {
  const select = document.getElementById("company-select");
  const pill = document.getElementById("company-info-pill");
  const chosen = select.value;
  state.selectedCompany = chosen;

  if (chosen === "__ALL__" || state.consolidateAll) {
    pill.style.display = "block";
    pill.innerHTML = `<strong>Consolidated Mode Active:</strong> All ${state.companies.length} loaded member companies will be merged into strictly ONE Master Workbook with 'Company' column.`;
    inspectCompanyStructure(state.companies.length > 0 ? state.companies[0].name : "");
  } else {
    const matched = state.companies.find((c) => c.name === chosen);
    if (matched) {
      pill.style.display = "block";
      pill.innerHTML = `Selected Entity: <strong>${matched.name}</strong> &bull; Period: ${formatTallyDate(matched.start)} to ${formatTallyDate(matched.end)}`;
      document.getElementById("from-date").value = formatTallyDate(matched.start);
      document.getElementById("to-date").value = formatTallyDate(matched.end);
      inspectCompanyStructure(matched.name);
    } else {
      pill.style.display = "none";
      inspectCompanyStructure("");
    }
  }
}

function onConsolidateToggled() {
  const chk = document.getElementById("chk-consolidate");
  state.consolidateAll = chk.checked;

  if (state.consolidateAll) {
    if (state.licenseInfo && !state.licenseInfo.can_consolidate && state.licenseInfo.tier !== "ENTERPRISE") {
      alert(`Multi-Company Consolidation requires an ENTERPRISE license tier.\n\nYour current tier: [${state.licenseInfo.tier || 'TRIAL'}]\n\nPlease contact Developer (Ansh Garg) to upgrade.`);
      chk.checked = false;
      state.consolidateAll = false;
      return;
    }
  }

  onCompanyChanged();
}

// ================= INSPECT STRUCTURE & HEADS =================
async function inspectCompanyStructure(compName) {
  const grid = document.getElementById("heads-checkbox-grid");
  grid.innerHTML = '<div class="heads-loading">Inspecting statement structure in Tally...</div>';

  // 1. If Extension Mode: fetch groups & ledgers XML via bridge and inspect on cloud
  if (state.isExtensionMode) {
    try {
      const tplRes = await fetch(`/api/tally-templates?company=${encodeURIComponent(compName)}`);
      const tpl = await tplRes.json();

      const gRes = await callTallyBridge("POST_TALLY", tpl.groups);
      const lRes = await callTallyBridge("POST_TALLY", tpl.ledgers);

      if (gRes.success && lRes.success) {
        const inspectRes = await fetch("/api/cloud-inspect", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            groups_xml: gRes.xml,
            ledgers_xml: lRes.xml,
            company: compName
          })
        });
        const data = await inspectRes.json();
        updateInspectedHeads(data);
        return;
      }
    } catch (err) {
      // Fallback to local inspect
    }
  }

  // 2. Local Agent Mode
  try {
    const res = await fetch("/api/inspect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company: compName })
    });
    const data = await res.json();
    updateInspectedHeads(data);
  } catch (err) {
    grid.innerHTML = '<div class="heads-loading">Could not inspect Tally structure. Verify Tally connection.</div>';
  }
}

function updateInspectedHeads(data) {
  state.plHeads = data.pl_heads || {};
  state.bsHeads = data.bs_heads || {};
  state.plCount = data.pl_count || 0;
  state.bsCount = data.bs_count || 0;
  state.totalCount = data.total_count || 0;

  document.getElementById("pl-count-badge").textContent = `${state.plCount.toLocaleString()} ledgers`;
  document.getElementById("bs-count-badge").textContent = `${state.bsCount.toLocaleString()} ledgers`;
  document.getElementById("all-count-badge").textContent = `${state.totalCount.toLocaleString()} total`;

  renderHeadCheckboxes();
}

function onStatementTypeChanged() {
  const radios = document.getElementsByName("statement-type");
  for (const r of radios) {
    if (r.checked) {
      state.statementType = r.value;
      break;
    }
  }

  const scopeAllRadio = document.querySelector('input[name="scope-mode"][value="all_stmt"]');
  if (scopeAllRadio) scopeAllRadio.checked = true;
  state.scopeMode = "all_stmt";

  renderHeadCheckboxes();
}

function onScopeModeChanged() {
  const radios = document.getElementsByName("scope-mode");
  for (const r of radios) {
    if (r.checked) {
      state.scopeMode = r.value;
      break;
    }
  }
  updateSelectionSummary();
}

function renderHeadCheckboxes() {
  const grid = document.getElementById("heads-checkbox-grid");
  const scopeBox = document.getElementById("scope-selection-box");
  grid.innerHTML = "";
  state.headCheckboxes = {};

  if (state.statementType === "all") {
    scopeBox.style.display = "none";
    return;
  }
  scopeBox.style.display = "block";

  const headsMap = state.statementType === "pl" ? state.plHeads : state.bsHeads;
  const headsList = Object.entries(headsMap).sort((a, b) => b[1] - a[1]);

  if (headsList.length === 0) {
    grid.innerHTML = '<div class="heads-loading">No primary heads detected in this statement.</div>';
    return;
  }

  headsList.forEach(([headName, count], idx) => {
    state.headCheckboxes[headName] = true;

    const item = document.createElement("div");
    item.className = "head-item";

    const chk = document.createElement("input");
    chk.type = "checkbox";
    chk.id = `head-chk-${idx}`;
    chk.checked = true;
    chk.onchange = () => {
      state.headCheckboxes[headName] = chk.checked;
      document.querySelector('input[name="scope-mode"][value="custom"]').checked = true;
      state.scopeMode = "custom";
      updateSelectionSummary();
    };

    const label = document.createElement("label");
    label.htmlFor = `head-chk-${idx}`;
    label.innerHTML = `<strong>${headName}</strong> <span class="head-count">(${count.toLocaleString()})</span>`;

    item.appendChild(chk);
    item.appendChild(label);
    grid.appendChild(item);
  });

  updateSelectionSummary();
}

function selectAllHeads() {
  for (const k in state.headCheckboxes) {
    state.headCheckboxes[k] = true;
  }
  document.querySelectorAll("#heads-checkbox-grid input[type='checkbox']").forEach((cb) => (cb.checked = true));
  document.querySelector('input[name="scope-mode"][value="all_stmt"]').checked = true;
  state.scopeMode = "all_stmt";
  updateSelectionSummary();
}

function deselectAllHeads() {
  for (const k in state.headCheckboxes) {
    state.headCheckboxes[k] = false;
  }
  document.querySelectorAll("#heads-checkbox-grid input[type='checkbox']").forEach((cb) => (cb.checked = false));
  document.querySelector('input[name="scope-mode"][value="custom"]').checked = true;
  state.scopeMode = "custom";
  updateSelectionSummary();
}

function updateSelectionSummary() {
  const badge = document.getElementById("heads-summary-badge");
  const total = Object.keys(state.headCheckboxes).length;
  const active = Object.values(state.headCheckboxes).filter(Boolean).length;

  if (state.statementType === "all") {
    badge.textContent = `Complete Dump (${state.totalCount.toLocaleString()} total ledgers)`;
    badge.style.color = "var(--primary)";
    return;
  }

  if (state.scopeMode === "all_stmt" || active === total) {
    badge.textContent = `All ${total} Heads Selected (${state.statementType === "pl" ? "P&L" : "Balance Sheet"})`;
    badge.style.color = "var(--success)";
  } else if (active === 0) {
    badge.textContent = "No head selected (Will extract all heads)";
    badge.style.color = "var(--warning)";
  } else {
    badge.textContent = `${active} of ${total} Heads Selected`;
    badge.style.color = "var(--primary)";
  }
}

// ================= EXTRACTION EXECUTION =================
async function startExtraction() {
  if (state.isExtracting) return;

  // Verify license first if local agent
  if (state.licenseInfo && !state.licenseInfo.allowed) {
    alert(`License Activation Required:\n\n${state.licenseInfo.message}\n\nPlease click 'License / Key' to activate.`);
    openLicenseModal();
    return;
  }

  // Determine target companies
  let targetCompanies = [];
  const chosen = state.selectedCompany;
  if (state.consolidateAll || chosen === "__ALL__") {
    targetCompanies = state.companies
      .filter((c) => !c.name.toLowerCase().includes("group companies"))
      .map((c) => c.name);
    if (targetCompanies.length === 0) {
      targetCompanies = state.companies.map((c) => c.name);
    }
  } else if (!chosen) {
    targetCompanies = [""];
  } else {
    targetCompanies = [chosen];
  }

  // Determine active heads
  const activeHeads = Object.keys(state.headCheckboxes).filter((k) => state.headCheckboxes[k]);
  const totalHeadsCount = Object.keys(state.headCheckboxes).length;

  let mode = state.statementType;
  let label = state.statementType === "pl" ? "Income & Expenditure" : state.statementType === "bs" ? "Balance Sheet" : "All Ledgers";
  let targetHeadsList = [];

  if (state.statementType !== "all" && state.scopeMode === "custom" && activeHeads.length > 0 && activeHeads.length < totalHeadsCount) {
    mode = "groups";
    targetHeadsList = activeHeads;
    label = activeHeads.slice(0, 3).join(", ") + (activeHeads.length > 3 ? ` + ${activeHeads.length - 3} more` : "");
  }

  const fromDateRaw = document.getElementById("from-date").value.trim();
  const toDateRaw = document.getElementById("to-date").value.trim();
  const startDate = normalizeDateToYMD(fromDateRaw, "20250401");
  const endDate = normalizeDateToYMD(toDateRaw, "20260331");
  const fastMode = document.getElementById("chk-fast-mode").checked;

  setExtractionRunning(true);
  appendTerminalLog(`======================================================================`, "text-info");
  appendTerminalLog(`EXTRACTION STARTED: Scope = [${label}]`, "text-info");
  appendTerminalLog(`Companies: ${targetCompanies.length} | Mode: ${state.isExtensionMode ? "Chrome Extension Online" : "Local Agent"}`);

  // 1. EXTENSION MODE (100% Online, Zero EXE, Zero Python on Client)
  if (state.isExtensionMode) {
    try {
      appendTerminalLog("Fetching data from Tally via Chrome Extension Bridge...", "text-info");
      document.getElementById("progress-bar-fill").style.width = "25%";
      document.getElementById("progress-pct").textContent = "25%";

      const companiesData = [];
      for (const comp of targetCompanies) {
        appendTerminalLog(`[${comp || "Active Company"}] Fetching groups and ledgers...`);
        const tpl = await fetch(`/api/tally-templates?company=${encodeURIComponent(comp)}&start=${startDate}&end=${endDate}&fast=${fastMode}`).then(r => r.json());

        const gRes = await callTallyBridge("POST_TALLY", tpl.groups);
        const lRes = await callTallyBridge("POST_TALLY", tpl.ledgers);

        document.getElementById("progress-bar-fill").style.width = "50%";
        document.getElementById("progress-pct").textContent = "50%";
        appendTerminalLog(`[${comp || "Active Company"}] Fetching transactions from Tally...`);

        const vRes = await callTallyBridge("POST_TALLY", tpl.vouchers, 180000);

        companiesData.push({
          company: comp || "Active Company",
          groups_xml: gRes.xml,
          ledgers_xml: lRes.xml,
          vouchers_xml: vRes.xml
        });
      }

      document.getElementById("progress-bar-fill").style.width = "75%";
      document.getElementById("progress-pct").textContent = "75%";
      appendTerminalLog("Processing hierarchy and generating Master Excel Workbook on Cloud Server...", "text-info");

      const cloudRes = await fetch("/api/cloud-extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          companies_data: companiesData,
          mode: mode,
          label: label,
          target_heads: targetHeadsList,
          start_date: startDate,
          end_date: endDate,
          fast_mode: fastMode
        })
      });

      const cloudData = await cloudRes.json();
      if (!cloudData.success) {
        throw new Error(cloudData.error || "Cloud generation failed");
      }

      document.getElementById("progress-bar-fill").style.width = "100%";
      document.getElementById("progress-pct").textContent = "100%";
      setExtractionRunning(false);

      appendTerminalLog("EXTRACTION COMPLETED SUCCESSFULLY (100% ONLINE VIA CHROME EXTENSION)!", "text-success");
      appendTerminalLog(`Master Workbook: ${cloudData.filename}`, "text-success");

      state.currentDownloadFile = cloudData.filename;
      document.getElementById("download-filename").textContent = cloudData.filename;
      document.getElementById("download-success-banner").style.display = "flex";

      // Trigger automatic download
      window.location.href = cloudData.download_url;
      return;
    } catch (err) {
      appendTerminalLog(`Extension Extraction Error: ${err.message}`, "text-danger");
      alert(`Extraction Error: ${err.message}`);
      setExtractionRunning(false);
      return;
    }
  }

  // 2. LOCAL AGENT MODE (Runs via local background thread)
  const payload = {
    companies: targetCompanies,
    mode: mode,
    label: label,
    heads: targetHeadsList,
    start_date: startDate,
    end_date: endDate,
    fast_mode: fastMode
  };

  try {
    const res = await fetch("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.error || `HTTP ${res.status}`);
    }

    const data = await res.json();
    state.activeTaskId = data.task_id;
    state.lastLogIndex = 0;

    state.pollInterval = setInterval(pollExtractionStatus, 800);
  } catch (err) {
    appendTerminalLog(`Extraction trigger failed: ${err.message}`, "text-danger");
    setExtractionRunning(false);
  }
}

async function pollExtractionStatus() {
  if (!state.activeTaskId) return;

  try {
    const res = await fetch(`/api/extract/${state.activeTaskId}`);
    const data = await res.json();

    if (data.logs && data.logs.length > state.lastLogIndex) {
      const newLogs = data.logs.slice(state.lastLogIndex);
      newLogs.forEach((log) => appendTerminalLog(log));
      state.lastLogIndex = data.logs.length;
    }

    const pct = data.progress || 35;
    document.getElementById("progress-bar-fill").style.width = `${pct}%`;
    document.getElementById("progress-pct").textContent = `${pct}%`;

    if (data.status === "completed") {
      clearInterval(state.pollInterval);
      setExtractionRunning(false);
      document.getElementById("progress-bar-fill").style.width = "100%";
      document.getElementById("progress-pct").textContent = "100%";

      appendTerminalLog("EXTRACTION COMPLETED SUCCESSFULLY!", "text-success");
      appendTerminalLog(`Master Excel Workbook: ${data.file_name}`, "text-success");

      if (data.file_name) {
        state.currentDownloadFile = data.file_name;
        document.getElementById("download-filename").textContent = data.file_name;
        document.getElementById("download-success-banner").style.display = "flex";
      }

      loadPreviousOutputs();
    } else if (data.status === "failed") {
      clearInterval(state.pollInterval);
      setExtractionRunning(false);
      appendTerminalLog(`EXTRACTION FAILED: ${data.error}`, "text-danger");
      alert(`Extraction Error: ${data.error}`);
    }
  } catch (err) {
    // Retry next tick
  }
}

function setExtractionRunning(running) {
  state.isExtracting = running;
  const btn = document.getElementById("btn-extract");
  const btnText = document.getElementById("btn-extract-text");
  const prog = document.getElementById("progress-container");

  if (running) {
    btn.disabled = true;
    btnText.textContent = "EXTRACTING DATA FROM TALLY...";
    prog.style.display = "block";
    document.getElementById("download-success-banner").style.display = "none";
  } else {
    btn.disabled = false;
    btnText.textContent = "EXTRACT TO CONSOLIDATED EXCEL WORKBOOK";
  }
}

function downloadCurrentFile() {
  if (state.currentDownloadFile) {
    window.location.href = `/api/download/${encodeURIComponent(state.currentDownloadFile)}`;
  }
}

// ================= OUTPUT ARCHIVE =================
async function loadPreviousOutputs() {
  const container = document.getElementById("history-list");
  if (!container) return;

  try {
    const res = await fetch("/api/outputs");
    const data = await res.json();
    const files = data.files || [];

    if (files.length === 0) {
      container.innerHTML = '<div class="history-empty">No workbooks generated yet.</div>';
      return;
    }

    container.innerHTML = "";
    files.forEach((f) => {
      const item = document.createElement("div");
      item.className = "history-item";

      const left = document.createElement("div");
      left.innerHTML = `<div class="history-name" title="${f.name}">${f.name}</div>
                        <div class="history-meta">${formatFileSize(f.size)} &bull; ${f.timestamp}</div>`;

      const dlBtn = document.createElement("button");
      dlBtn.className = "btn btn-xs btn-outline";
      dlBtn.innerHTML = "Download";
      dlBtn.onclick = () => {
        window.location.href = `/api/download/${encodeURIComponent(f.name)}`;
      };

      item.appendChild(left);
      item.appendChild(dlBtn);
      container.appendChild(item);
    });
  } catch (err) {
    container.innerHTML = '<div class="history-empty">No archive available.</div>';
  }
}

// ================= LICENSE =================
async function loadLicenseInfo() {
  try {
    const res = await fetch("/api/license");
    const data = await res.json();
    state.licenseInfo = data;

    const badge = document.getElementById("license-status-badge");
    const tierPill = document.getElementById("lic-tier");

    if (badge) {
      badge.querySelector(".license-text").textContent = `License: [${data.tier}] ${data.status}`;
      badge.className = data.allowed ? "status-pill status-online" : "status-pill status-offline";
    }

    if (tierPill) tierPill.textContent = data.tier;
    const licMid = document.getElementById("lic-machine-id");
    if (licMid) licMid.value = data.machine_id;
  } catch (err) {
    // Cloud website mode: license managed at user/org level
  }
}

function openLicenseModal() {
  document.getElementById("modal-license").style.display = "flex";
  loadLicenseInfo();
}

function closeLicenseModal() {
  document.getElementById("modal-license").style.display = "none";
}

function copyMachineId() {
  const val = document.getElementById("lic-machine-id").value;
  navigator.clipboard.writeText(val);
  alert(`Machine ID copied to clipboard:\n\n${val}`);
}

async function checkOnlineLicense() {
  await loadLicenseInfo();
  if (state.licenseInfo && state.licenseInfo.allowed) {
    alert(`License Verified!\n\n${state.licenseInfo.message}`);
  } else {
    alert(`License Pending / Inactive:\n\n${state.licenseInfo.message}\n\nPlease provide your Machine ID to Developer (Ansh Garg).`);
  }
}

async function activateOfflineKey() {
  const input = document.getElementById("lic-key-input");
  const key = input.value.trim();
  if (!key) {
    alert("Please enter a valid offline license key.");
    return;
  }

  try {
    const res = await fetch("/api/license/activate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: key })
    });
    const data = await res.json();

    if (data.success) {
      alert(`Activation Successful!\n\n${data.message}`);
      input.value = "";
      closeLicenseModal();
      loadLicenseInfo();
    } else {
      alert(`Activation Failed:\n\n${data.message}`);
    }
  } catch (err) {
    alert(`Activation Request Error: ${err.message}`);
  }
}

// ================= ABOUT MODAL =================
function openAboutModal() {
  document.getElementById("modal-about").style.display = "flex";
}

function closeAboutModal() {
  document.getElementById("modal-about").style.display = "none";
}

// ================= TERMINAL LOGGING =================
function appendTerminalLog(text, className = "") {
  const term = document.getElementById("terminal-body");
  if (!term) return;
  const line = document.createElement("div");
  line.className = `log-line ${className}`;

  const ts = new Date().toLocaleTimeString("en-GB", { hour12: false });
  line.textContent = `[${ts}] ${text}`;

  term.appendChild(line);
  term.scrollTop = term.scrollHeight;
}

function clearLogs() {
  const term = document.getElementById("terminal-body");
  if (!term) return;
  term.innerHTML = '<div class="log-line text-muted">[System] Log cleared. Ready for next extraction.</div>';
}

// ================= HELPERS =================
function formatTallyDate(s) {
  if (!s) return "";
  s = String(s).trim();
  if (s.length === 8 && /^\d+$/.test(s)) {
    return `${s.slice(6, 8)}-${s.slice(4, 6)}-${s.slice(0, 4)}`;
  }
  return s;
}

function normalizeDateToYMD(s, defaultVal) {
  if (!s || !s.trim()) return defaultVal;
  const digits = s.replace(/\D/g, "");
  if (digits.length === 8) {
    if (s.indexOf("-") !== -1 || s.indexOf("/") !== -1) {
      return `${digits.slice(4, 8)}${digits.slice(2, 4)}${digits.slice(0, 2)}`;
    }
    return digits;
  }
  return defaultVal;
}

function formatFileSize(bytes) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}
