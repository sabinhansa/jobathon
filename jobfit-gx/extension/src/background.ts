chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ jobfitBaseUrl: "http://localhost:8000" });
});

