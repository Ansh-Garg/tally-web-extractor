/**
 * Tally Web Bridge — Popup Controller
 * Developed By : Ansh Garg
 */

document.addEventListener("DOMContentLoaded", () => {
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");
  const statusDetail = document.getElementById("status-detail");
  const urlInput = document.getElementById("tally-url-input");
  const btnSave = document.getElementById("btn-save-url");
  const btnOpen = document.getElementById("btn-open-dashboard");
  const btnCheck = document.getElementById("btn-check-again");

  // Load configured URL
  chrome.runtime.sendMessage({ action: "GET_TALLY_URL" }, (res) => {
    if (res && res.url) {
      urlInput.value = res.url;
    }
    checkStatus();
  });

  function checkStatus() {
    statusDot.className = "dot checking";
    statusText.textContent = "Checking Tally...";
    statusDetail.textContent = `Probing ${urlInput.value}...`;

    chrome.runtime.sendMessage({ action: "CHECK_TALLY" }, (res) => {
      if (res && res.online) {
        statusDot.className = "dot online";
        statusText.textContent = "Tally is ONLINE";
        statusDetail.textContent = `Connected successfully on ${res.url}`;
      } else {
        statusDot.className = "dot offline";
        statusText.textContent = "Tally is OFFLINE";
        statusDetail.textContent = `Cannot reach ${res ? res.url : urlInput.value}`;
      }
    });
  }

  btnSave.addEventListener("click", () => {
    const newUrl = urlInput.value.trim();
    if (newUrl) {
      chrome.runtime.sendMessage({ action: "SET_TALLY_URL", url: newUrl }, () => {
        checkStatus();
      });
    }
  });

  btnCheck.addEventListener("click", checkStatus);

  btnOpen.addEventListener("click", () => {
    chrome.tabs.create({ url: "https://tally-web-extractor.onrender.com/dashboard" });
  });
});
