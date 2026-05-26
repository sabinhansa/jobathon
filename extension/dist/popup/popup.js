const DEFAULT_BASE_URL = "http://localhost:8000";

let cvs = [];
let result = null;
let activeTab = "overview";

const $ = (id) => document.getElementById(id);

async function getBaseUrl() {
  const stored = await chrome.storage.local.get(["jobathonBaseUrl"]);
  return stored.jobathonBaseUrl || DEFAULT_BASE_URL;
}

async function apiRequest(path, options = {}) {
  const baseUrl = await getBaseUrl();
  let response;
  try {
    response = await fetch(`${baseUrl}${path}`, options);
  } catch {
    throw new Error("Start Jobathon backend with docker compose up.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

const api = {
  health: () => apiRequest("/health"),
  cvs: () => apiRequest("/cvs"),
  analyze: (payload) =>
    apiRequest("/analysis/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
};

async function init() {
  bindTabs();
  $("dashboard").addEventListener("click", openDashboard);
  $("extract").addEventListener("click", extractVisibleText);
  $("analyze").addEventListener("click", analyze);
  await Promise.all([loadHealth(), loadCvs()]);
  renderTab();
}

async function loadHealth() {
  try {
    const health = await api.health();
    $("status").textContent = health.ollama === "ok" ? "Ready" : "Ollama offline";
  } catch (error) {
    $("status").textContent = "Offline";
    setMessage(error.message);
  }
}

async function loadCvs() {
  try {
    cvs = await api.cvs();
    const select = $("cvSelect");
    select.innerHTML = cvs.map((cv) => `<option value="${cv.id}">${escapeHtml(cv.name)}</option>`).join("");
    if (!cvs.length) select.innerHTML = `<option value="">Upload a CV in dashboard first</option>`;
  } catch (error) {
    setMessage(error.message);
  }
}

async function analyze() {
  const cvId = $("cvSelect").value;
  const jobText = $("jobText").value.trim();
  if (!cvId) return setMessage("Upload a CV first.");
  if (!jobText) return setMessage("Paste job description or extract visible page text.");
  setMessage("Analyzing locally...");
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    result = await api.analyze({
      cv_id: cvId,
      job_text: jobText,
      job_url: tab?.url,
      mode: "fast",
    });
    $("score").textContent = String(result.overall_score);
    $("summary").textContent = result.summary;
    setMessage("Analysis saved.");
    renderTab();
  } catch (error) {
    const message = error.message;
    setMessage(message.includes("Ollama") ? "Ollama is not reachable." : message);
  }
}

async function extractVisibleText() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab.id) return;
  const [injection] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => document.body?.innerText?.slice(0, 60000) || "",
  });
  $("jobText").value = String(injection.result || "");
  setMessage("Visible page text extracted by explicit click.");
}

async function openDashboard() {
  const baseUrl = await getBaseUrl();
  chrome.tabs.create({ url: `${baseUrl}/app` });
}

function bindTabs() {
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      activeTab = button.dataset.tab || "overview";
      document.querySelectorAll("[data-tab]").forEach((node) => node.classList.remove("active"));
      button.classList.add("active");
      renderTab();
    });
  });
}

function renderTab() {
  const content = $("tabContent");
  if (!result) {
    content.innerHTML = `<p class="muted">Run an analysis to fill this panel.</p>`;
    return;
  }
  if (activeTab === "overview") {
    content.innerHTML = list([...result.strengths, ...result.warnings]);
  } else if (activeTab === "requirements") {
    content.innerHTML = result.requirement_matches
      .map((item) => `<div class="item"><b>${escapeHtml(item.status)}</b><br>${escapeHtml(item.requirement)}<br><span class="muted">${escapeHtml(item.explanation)}</span></div>`)
      .join("");
  } else if (activeTab === "gaps") {
    content.innerHTML = list(result.gaps);
  } else if (activeTab === "fixes") {
    content.innerHTML = result.cv_improvements
      .map((item) => `<div class="item"><b>${escapeHtml(item.target_section)}</b><br>${escapeHtml(item.suggested_bullet)}</div>`)
      .join("");
  } else if (activeTab === "cover") {
    content.innerHTML = `<div class="item">${escapeHtml(result.cover_letter).replace(/\n/g, "<br>")}</div><div class="item"><b>Recruiter</b><br>${escapeHtml(result.recruiter_message)}</div>`;
  } else {
    content.innerHTML = `<p class="muted">Open the dashboard for saved history.</p>`;
  }
}

function list(items) {
  return items.length ? items.map((item) => `<div class="item">${escapeHtml(item)}</div>`).join("") : `<p class="muted">Nothing to show yet.</p>`;
}

function setMessage(message) {
  $("message").textContent = message;
}

function escapeHtml(value) {
  const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
  return String(value).replace(/[&<>"']/g, (char) => entities[char] || char);
}

init();

