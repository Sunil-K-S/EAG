
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "GET_URL") {
    chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
      const url = tabs[0].url;
      sendResponse({ url });
    });
    return true;
  }
});
