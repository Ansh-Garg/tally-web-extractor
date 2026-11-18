/**
 * Tally Web Extractor — Commercial Website Client Script
 * Probes the local agent (http://localhost:5000) and enables seamless bridge detection.
 * Author: Ansh Garg
 */

document.addEventListener("DOMContentLoaded", () => {
  probeLocalAgent();
  setInterval(probeLocalAgent, 2500);
});

async function probeLocalAgent() {
  const navPill = document.getElementById("nav-agent-status");
  const bridgeCard = document.getElementById("hero-bridge-card");
  const bridgeTitle = document.getElementById("bridge-title");
  const bridgeDesc = document.getElementById("bridge-desc");
  const bridgeCta = document.getElementById("bridge-cta");
  const bridgeIcon = document.getElementById("bridge-status-icon");

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 1800);

    const res = await fetch("http://localhost:5000/api/status", {
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    if (res.ok) {
      const data = await res.json();
      const tallyState = data.tally_online ? "Tally is ONLINE" : "Tally is OFFLINE";

      // Navbar badge
      navPill.className = "nav-agent-pill status-online";
      navPill.querySelector(".status-label").textContent = "Agent: Connected";

      // Hero bridge card
      bridgeCard.className = "bridge-card bridge-card-online";
      bridgeIcon.textContent = "✓";
      bridgeTitle.textContent = `Local Agent Active on Port 5000 (${tallyState})`;
      bridgeDesc.innerHTML = `Your browser is successfully bridged to your local Tally engine. You can now extract data directly in your browser.`;

      bridgeCta.innerHTML = `
        <a href="http://localhost:5000" target="_blank" class="btn btn-sm btn-primary">
          Launch Dashboard →
        </a>
      `;
      return;
    }
  } catch (err) {
    // Agent is offline or not running
  }

  // Fallback: Agent is offline
  navPill.className = "nav-agent-pill status-offline";
  navPill.querySelector(".status-label").textContent = "Agent: Not Running";

  bridgeCard.className = "bridge-card bridge-card-offline";
  bridgeIcon.textContent = "⚡";
  bridgeTitle.textContent = "Local Agent Not Detected";
  bridgeDesc.innerHTML = `To allow your web browser to extract data from Tally, download and launch the 35 KB local bridge agent on your PC.`;

  bridgeCta.innerHTML = `
    <a href="#download" class="btn btn-sm btn-outline-white">
      Download Agent (35 KB)
    </a>
  `;
}
