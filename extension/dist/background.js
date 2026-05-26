chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ jobathonBaseUrl: "http://localhost:8000" });
});

