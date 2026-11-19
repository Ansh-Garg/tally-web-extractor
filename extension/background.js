/**
 * Tally Web Bridge — Background Service Worker (Manifest V3)
 * Handles cross-origin requests to local Tally (localhost:8080)
 * Developed By : Ansh Garg
 */

const DEFAULT_TALLY_URL = "http://localhost:8080";

// Retrieve configured Tally URL
async function getTallyUrl() {
  return new Promise((resolve) => {
    chrome.storage.local.get(["tallyUrl"], (res) => {
      resolve(res.tallyUrl || DEFAULT_TALLY_URL);
    });
  });
}

// Check connectivity to Tally
async function checkTallyConnection() {
  const tallyUrl = await getTallyUrl();
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2500);

    // Quick dummy XML request to probe Tally
    const probeXML = `<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>Dummy</ID></HEADER><BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY></ENVELOPE>`;

    const res = await fetch(tallyUrl, {
      method: "POST",
      headers: { "Content-Type": "text/xml; charset=utf-8" },
      body: probeXML,
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    return { online: res.status === 200 || res.status === 400 || res.status === 500, url: tallyUrl };
  } catch (err) {
    return { online: false, url: tallyUrl, error: err.message };
  }
}

// Forward XML request to Tally
async function postTallyXML(payload, customTimeout = 60000) {
  const tallyUrl = await getTallyUrl();
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), customTimeout);

    const res = await fetch(tallyUrl, {
      method: "POST",
      headers: { "Content-Type": "text/xml; charset=utf-8" },
      body: payload,
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      throw new Error(`HTTP Error from Tally: ${res.status} ${res.statusText}`);
    }

    const xmlText = await res.text();
    return { success: true, xml: xmlText };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

// Message Listener for Content Scripts and Popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "CHECK_TALLY") {
    checkTallyConnection().then(sendResponse);
    return true; // Keep channel open for async response
  }

  if (request.action === "POST_TALLY") {
    postTallyXML(request.payload, request.timeout || 120000).then(sendResponse);
    return true;
  }

  if (request.action === "SET_TALLY_URL") {
    chrome.storage.local.set({ tallyUrl: request.url }, () => {
      sendResponse({ success: true, url: request.url });
    });
    return true;
  }

  if (request.action === "GET_TALLY_URL") {
    getTallyUrl().then((url) => sendResponse({ url }));
    return true;
  }
});
