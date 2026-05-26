const ROOT_ID = "jobfit-gx-root";

function injectButton() {
  if (document.getElementById(ROOT_ID)) return;

  const root = document.createElement("div");
  root.id = ROOT_ID;
  root.innerHTML = `
    <button id="jobfit-gx-fab" title="Open JobFit GX">JF</button>
    <aside id="jobfit-gx-drawer" aria-label="JobFit GX panel">
      <div class="jfgx-head">
        <div>
          <p>JobFit GX</p>
          <h2>Local match</h2>
        </div>
        <button id="jfgx-close" title="Close">x</button>
      </div>
      <select id="jfgx-cv"></select>
      <textarea id="jfgx-text" placeholder="Paste job text or extract visible page text."></textarea>
      <div class="jfgx-row">
        <button id="jfgx-extract">Extract visible text</button>
        <button id="jfgx-open">Dashboard</button>
      </div>
      <button id="jfgx-analyze" class="jfgx-primary">Analyze Job</button>
      <p id="jfgx-message"></p>
      <section class="jfgx-score">
        <strong id="jfgx-score">--</strong>
        <span id="jfgx-summary">No analysis yet.</span>
      </section>
      <nav class="jfgx-tabs">
        <button data-jfgx-tab="overview" class="active">Overview</button>
        <button data-jfgx-tab="requirements">Reqs</button>
        <button data-jfgx-tab="gaps">Gaps</button>
        <button data-jfgx-tab="cover">Cover</button>
      </nav>
      <div id="jfgx-result"></div>
    </aside>
  `;
  document.documentElement.append(root);

  const style = document.createElement("style");
  style.textContent = css;
  root.append(style);

  setupPanel(root);
}

type AnalysisResult = {
  overall_score: number;
  summary: string;
  requirement_matches: Array<{ requirement: string; status: string; explanation: string }>;
  strengths: string[];
  gaps: string[];
  cover_letter: string;
  recruiter_message: string;
};

function setupPanel(root: HTMLElement) {
  const drawer = root.querySelector<HTMLElement>("#jobfit-gx-drawer")!;
  const fab = root.querySelector<HTMLButtonElement>("#jobfit-gx-fab")!;
  const close = root.querySelector<HTMLButtonElement>("#jfgx-close")!;
  const text = root.querySelector<HTMLTextAreaElement>("#jfgx-text")!;
  const cv = root.querySelector<HTMLSelectElement>("#jfgx-cv")!;
  const message = root.querySelector<HTMLElement>("#jfgx-message")!;
  const resultBox = root.querySelector<HTMLElement>("#jfgx-result")!;
  let latest: AnalysisResult | null = null;
  let activeTab = "overview";

  const setMessage = (value: string) => {
    message.textContent = value;
  };

  fab.addEventListener("click", async () => {
    drawer.classList.add("open");
    await loadCvs();
  });
  close.addEventListener("click", () => drawer.classList.remove("open"));
  root.querySelector<HTMLButtonElement>("#jfgx-extract")!.addEventListener("click", () => {
    text.value = document.body?.innerText?.slice(0, 60000) || "";
    setMessage("Visible page text extracted by explicit click.");
  });
  root.querySelector<HTMLButtonElement>("#jfgx-open")!.addEventListener("click", () => {
    window.open("http://localhost:8000/app", "_blank", "noopener");
  });
  root.querySelector<HTMLButtonElement>("#jfgx-analyze")!.addEventListener("click", async () => {
    if (!cv.value) return setMessage("Upload a CV first.");
    if (!text.value.trim()) return setMessage("Paste job description or extract visible page text.");
    setMessage("Analyzing locally...");
    try {
      latest = await apiPost<AnalysisResult>("/analysis/analyze", {
        cv_id: cv.value,
        job_text: text.value,
        job_url: location.href,
        mode: "fast",
      });
      root.querySelector<HTMLElement>("#jfgx-score")!.textContent = String(latest.overall_score);
      root.querySelector<HTMLElement>("#jfgx-summary")!.textContent = latest.summary;
      setMessage("Analysis saved.");
      render();
    } catch (error) {
      setMessage((error as Error).message);
    }
  });
  root.querySelectorAll<HTMLButtonElement>("[data-jfgx-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      activeTab = button.dataset.jfgxTab || "overview";
      root.querySelectorAll("[data-jfgx-tab]").forEach((node) => node.classList.remove("active"));
      button.classList.add("active");
      render();
    });
  });

  async function loadCvs() {
    try {
      const cvs = await apiGet<Array<{ id: string; name: string }>>("/cvs");
      cv.innerHTML = cvs.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join("");
      if (!cvs.length) cv.innerHTML = `<option value="">Upload a CV in dashboard first</option>`;
      setMessage(cvs.length ? "Ready." : "No CV uploaded yet.");
    } catch {
      cv.innerHTML = `<option value="">Backend offline</option>`;
      setMessage("Start JobFit GX backend with docker compose up.");
    }
  }

  function render() {
    if (!latest) {
      resultBox.innerHTML = `<p class="muted">Run an analysis to fill this panel.</p>`;
      return;
    }
    if (activeTab === "requirements") {
      resultBox.innerHTML = latest.requirement_matches
        .map((item) => `<div class="jfgx-item"><b>${escapeHtml(item.status)}</b><br>${escapeHtml(item.requirement)}<br><span>${escapeHtml(item.explanation)}</span></div>`)
        .join("");
    } else if (activeTab === "gaps") {
      resultBox.innerHTML = list(latest.gaps);
    } else if (activeTab === "cover") {
      resultBox.innerHTML = `<div class="jfgx-item">${escapeHtml(latest.cover_letter).replace(/\n/g, "<br>")}</div><div class="jfgx-item"><b>Recruiter</b><br>${escapeHtml(latest.recruiter_message)}</div>`;
    } else {
      resultBox.innerHTML = list(latest.strengths);
    }
  }
}

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`http://localhost:8000${path}`);
  if (!response.ok) throw new Error("Backend offline.");
  return response.json() as Promise<T>;
}

async function apiPost<T>(path: string, payload: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`http://localhost:8000${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error("Start JobFit GX backend with docker compose up.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Backend request failed.");
  }
  return response.json() as Promise<T>;
}

function list(items: string[]) {
  return items.length ? items.map((item) => `<div class="jfgx-item">${escapeHtml(item)}</div>`).join("") : `<p class="muted">Nothing to show yet.</p>`;
}

function escapeHtml(value: string) {
  const entities: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
  return value.replace(/[&<>"']/g, (char) => entities[char] || char);
}

const css = `
#jobfit-gx-root {
  all: initial;
  position: relative;
  z-index: 2147483647;
  font-family: Inter, ui-sans-serif, system-ui, "Segoe UI", sans-serif;
}
#jobfit-gx-root * { box-sizing: border-box; }
#jobfit-gx-fab {
  position: fixed;
  right: 18px;
  bottom: 18px;
  width: 50px;
  height: 50px;
  border-radius: 50%;
  border: 1px solid rgba(0,229,255,.75);
  background: linear-gradient(135deg, #ff304f, #8b2cff);
  color: #fff;
  font: 800 15px/1 Inter, system-ui, sans-serif;
  box-shadow: 0 14px 35px rgba(0,0,0,.45), 0 0 18px rgba(0,229,255,.22);
  cursor: pointer;
}
#jobfit-gx-drawer {
  position: fixed;
  top: 18px;
  right: 18px;
  bottom: 18px;
  width: min(390px, calc(100vw - 28px));
  transform: translateX(calc(100% + 28px));
  transition: transform .18s ease;
  border: 1px solid #2c3042;
  border-radius: 8px;
  background: #090a12;
  color: #f4f7fb;
  box-shadow: 0 22px 70px rgba(0,0,0,.55);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font: 13px/1.4 Inter, system-ui, sans-serif;
}
#jobfit-gx-drawer.open { transform: translateX(0); }
.jfgx-head, .jfgx-row, .jfgx-score, .jfgx-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
}
.jfgx-head { justify-content: space-between; }
.jfgx-head p { margin: 0; color: #00e5ff; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; }
.jfgx-head h2 { margin: 0; font-size: 19px; color: #f4f7fb; }
#jobfit-gx-root button, #jobfit-gx-root select, #jobfit-gx-root textarea {
  border: 1px solid #2c3042;
  border-radius: 6px;
  background: #141622;
  color: #f4f7fb;
  padding: 9px;
  font: inherit;
}
#jobfit-gx-root button { cursor: pointer; font-weight: 700; }
#jfgx-close { width: 34px; }
#jfgx-text { min-height: 130px; resize: vertical; }
.jfgx-row > *, .jfgx-tabs > * { flex: 1; }
.jfgx-primary { background: linear-gradient(135deg, #ff304f, #8b2cff) !important; border-color: rgba(255,48,79,.7) !important; }
#jfgx-message { min-height: 18px; margin: 0; color: #9aa4b7; }
.jfgx-score {
  border: 1px solid #2c3042;
  border-radius: 8px;
  padding: 9px;
  background: #10121c;
}
#jfgx-score {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  border: 2px solid #00e5ff;
  color: #00e5ff;
  font-size: 18px;
}
.jfgx-tabs button.active { border-color: #00e5ff !important; color: #00e5ff !important; }
#jfgx-result {
  overflow: auto;
  min-height: 120px;
  border: 1px solid #2c3042;
  border-radius: 8px;
  padding: 9px;
  background: #0f111b;
}
.jfgx-item { padding: 8px 0; border-bottom: 1px solid #2c3042; color: #f4f7fb; }
.jfgx-item:last-child { border-bottom: 0; }
.jfgx-item span, .muted { color: #9aa4b7; }
`;

injectButton();
