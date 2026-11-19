/**
 * Tally Web Extractor — Commercial Website Client Script
 * Detects Chrome Extension Bridge or Local Agent to provide seamless 1-click extraction.
 * Author: Ansh Garg
 */

document.addEventListener("DOMContentLoaded", () => {
  probeBridges();
  setInterval(probeBridges, 2000);
});

// Communication with Chrome Extension via window.postMessage
function probeExtensionBridge() {
  return new Promise((resolve) => {
    if (!window.__TALLY_EXTENSION_INSTALLED__) {
      return resolve({ installed: false });
    }

    const requestId = "probe_" + Math.random().toString(36).substring(2, 9);
    function onMsg(e) {
      if (e.source === window && e.data && e.data.source === "TALLY_EXTENSION" && e.data.requestId === requestId) {
        window.removeEventListener("message", onMsg);
        resolve({ installed: true, ...e.data.data });
      }
    }
    window.addEventListener("message", onMsg);
    window.postMessage({ source: "TALLY_WEB_PAGE", action: "CHECK_TALLY", requestId }, "*");

    setTimeout(() => {
      window.removeEventListener("message", onMsg);
      resolve({ installed: true, online: false });
    }, 1500);
  });
}

async function probeBridges() {
  const navPill = document.getElementById("nav-agent-status");
  const bridgeCard = document.getElementById("hero-bridge-card");
  const bridgeTitle = document.getElementById("bridge-title");
  const bridgeDesc = document.getElementById("bridge-desc");
  const bridgeCta = document.getElementById("bridge-cta");
  const bridgeIcon = document.getElementById("bridge-status-icon");

  // 1. Check Chrome Extension first (Preferred Zero-Install Method)
  const extStatus = await probeExtensionBridge();
  if (extStatus.installed) {
    const tallyState = extStatus.online ? "Tally is ONLINE" : "Tally is OFFLINE";
    navPill.className = "nav-agent-pill status-online";
    navPill.querySelector(".status-label").textContent = "Extension: Connected";

    bridgeCard.className = "bridge-card bridge-card-online";
    bridgeIcon.textContent = "✓";
    bridgeTitle.textContent = `Chrome Extension Active (${tallyState})`;
    bridgeDesc.innerHTML = `Zero EXE mode active. Your browser is securely bridged to Tally on <code>localhost:8080</code>. You can extract directly on the web.`;

    bridgeCta.innerHTML = `
      <a href="/dashboard" class="btn btn-sm btn-primary">
        Open Web Dashboard →
      </a>
    `;
    return;
  }

  // 2. Check Local Python Agent (Fallback)
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 1200);

    const res = await fetch("http://localhost:5000/api/status", {
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    if (res.ok) {
      const data = await res.json();
      const tallyState = data.tally_online ? "Tally is ONLINE" : "Tally is OFFLINE";

      navPill.className = "nav-agent-pill status-online";
      navPill.querySelector(".status-label").textContent = "Agent: Connected";

      bridgeCard.className = "bridge-card bridge-card-online";
      bridgeIcon.textContent = "✓";
      bridgeTitle.textContent = `Local Agent Active on Port 5000 (${tallyState})`;
      bridgeDesc.innerHTML = `Local agent bridge detected. You can extract data directly in your browser.`;

      bridgeCta.innerHTML = `
        <a href="http://localhost:5000" target="_blank" class="btn btn-sm btn-primary">
          Launch Dashboard →
        </a>
      `;
      return;
    }
  } catch (err) {
    // Agent offline
  }

  // 3. Neither detected
  navPill.className = "nav-agent-pill status-offline";
  navPill.querySelector(".status-label").textContent = "Bridge: Not Detected";

  bridgeCard.className = "bridge-card bridge-card-offline";
  bridgeIcon.textContent = "⚡";
  bridgeTitle.textContent = "Chrome Extension or Local Agent Required";
  bridgeDesc.innerHTML = `To extract Tally data directly in your browser without EXEs or Python, add our lightweight Chrome Extension (1-click, 6 KB).`;

  bridgeCta.innerHTML = `
    <a href="downloads/tally-web-extension.zip" class="btn btn-sm btn-primary" download>
      Add Chrome Extension (6 KB)
    </a>
  `;
}
