/**
 * Tally Web Bridge — Content Script
 * Injected into the Web Extractor Dashboard to bridge between Web Page and Chrome Extension
 * Developed By : Ansh Garg
 */

// Inject flag into the page's execution context
const script = document.createElement("script");
script.textContent = `
  window.__TALLY_EXTENSION_INSTALLED__ = true;
  window.dispatchEvent(new CustomEvent("TallyExtensionReady", { detail: { version: "1.0.0" } }));
`;
(document.head || document.documentElement).appendChild(script);
script.remove();

// Relay messages between Web Page and Chrome Extension Service Worker
window.addEventListener("message", (event) => {
  // Only accept messages from same window and matching protocol
  if (event.source !== window || !event.data || event.data.source !== "TALLY_WEB_PAGE") {
    return;
  }

  const { action, requestId, payload, timeout } = event.data;

  // Forward to Extension Service Worker
  chrome.runtime.sendMessage({ action, payload, timeout }, (response) => {
    // If extension failed or runtime error
    const err = chrome.runtime.lastError;
    const finalData = err ? { success: false, error: err.message } : response;

    // Send response back to the web page
    window.postMessage({
      source: "TALLY_EXTENSION",
      action: `${action}_RESPONSE`,
      requestId,
      data: finalData
    }, "*");
  });
});
