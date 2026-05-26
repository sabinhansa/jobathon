import { api, getBaseUrl } from "../api";
import type { AnalyzeResponse, CVListItem } from "../types";

let cvs: CVListItem[] = [];
let result: AnalyzeResponse | null = null;
let activeTab = "overview";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

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
    setMessage((error as Error).message);
  }
}

async function loadCvs() {
  try {
    cvs = await api.cvs();
    const select = $("cvSelect") as HTMLSelectElement;
    select.innerHTML = cvs.map((cv) => `<option value="${cv.id}">${escapeHtml(cv.name)}</option>`).join("");
    if (!cvs.length) select.innerHTML = `<option value="">Upload a CV in dashboard first</option>`;
  } catch (error) {
    setMessage((error as Error).message);
  }
}

async function analyze() {
  const cvId = ($("cvSelect") as HTMLSelectElement).value;
  const jobText = ($("jobText") as HTMLTextAreaElement).value.trim();
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
    const message = (error as Error).message;
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
  ($("jobText") as HTMLTextAreaElement).value = String(injection.result || "");
  setMessage("Visible page text extracted by explicit click.");
}

async function openDashboard() {
  const baseUrl = await getBaseUrl();
  chrome.tabs.create({ url: `${baseUrl}/app` });
}

function bindTabs() {
  document.querySelectorAll<HTMLButtonElement>("[data-tab]").forEach((button) => {
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

function list(items: string[]) {
  return items.length ? items.map((item) => `<div class="item">${escapeHtml(item)}</div>`).join("") : `<p class="muted">Nothing to show yet.</p>`;
}

function setMessage(message: string) {
  $("message").textContent = message;
}

function escapeHtml(value: string) {
  const entities: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
  return value.replace(/[&<>"']/g, (char) => entities[char] || char);
}

init();
