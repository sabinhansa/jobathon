const ROOT_ID = "jobathon-root";

if (!document.getElementById(ROOT_ID)) {
  injectButton();
}

function injectButton() {
  const root = document.createElement("div");
  root.id = ROOT_ID;
  root.innerHTML = `
    <button id="jobathon-fab" title="Open Jobathon">JA</button>
    <aside id="jobathon-drawer" aria-label="Jobathon panel">
      <div class="jathon-head">
        <div>
          <p>Jobathon</p>
          <h2>Local match</h2>
        </div>
        <button id="jathon-close" title="Close">x</button>
      </div>
      <select id="jathon-cv"></select>
      <select id="jathon-mode">
        <option value="fast">Quick scan</option>
        <option value="deep">Deep LLM</option>
      </select>
      <textarea id="jathon-text" placeholder="Paste job text or extract visible page text."></textarea>
      <div class="jathon-row">
        <button id="jathon-extract">Extract visible text</button>
        <button id="jathon-open">Dashboard</button>
      </div>
      <button id="jathon-analyze" class="jathon-primary">Analyze Job</button>
      <p id="jathon-message"></p>
      <section class="jathon-score">
        <strong id="jathon-score">--</strong>
        <span id="jathon-summary">No analysis yet.</span>
      </section>
      <nav class="jathon-tabs">
        <button data-jathon-tab="overview" class="active">Overview</button>
        <button data-jathon-tab="requirements">Reqs</button>
        <button data-jathon-tab="gaps">Gaps</button>
        <button data-jathon-tab="cover">Cover</button>
      </nav>
      <div id="jathon-result"></div>
    </aside>
  `;
  document.documentElement.append(root);

  const style = document.createElement("style");
  style.textContent = css;
  root.append(style);

  setupPanel(root);
}

function setupPanel(root) {
  const drawer = root.querySelector("#jobathon-drawer");
  const fab = root.querySelector("#jobathon-fab");
  const close = root.querySelector("#jathon-close");
  const text = root.querySelector("#jathon-text");
  const cv = root.querySelector("#jathon-cv");
  const mode = root.querySelector("#jathon-mode");
  const message = root.querySelector("#jathon-message");
  const resultBox = root.querySelector("#jathon-result");
  let latest = null;
  let activeTab = "overview";

  const setMessage = (value) => {
    message.textContent = value;
  };

  fab.addEventListener("click", async () => {
    drawer.classList.add("open");
    await loadCvs();
  });
  close.addEventListener("click", () => drawer.classList.remove("open"));
  root.querySelector("#jathon-extract").addEventListener("click", () => {
    text.value = document.body?.innerText?.slice(0, 60000) || "";
    setMessage("Visible page text extracted by explicit click.");
  });
  root.querySelector("#jathon-open").addEventListener("click", () => {
    window.open("http://localhost:8000/app", "_blank", "noopener");
  });
  root.querySelector("#jathon-analyze").addEventListener("click", async () => {
    if (!cv.value) return setMessage("Upload a CV first.");
    if (!text.value.trim()) return setMessage("Paste job description or extract visible page text.");
    setMessage(mode.value === "deep" ? "Running Deep LLM analysis..." : "Running quick local scan...");
    try {
      latest = await apiPost("/analysis/analyze", {
        cv_id: cv.value,
        job_text: text.value,
        job_url: location.href,
        mode: mode.value,
      });
      root.querySelector("#jathon-score").textContent = String(latest.overall_score);
      root.querySelector("#jathon-summary").textContent = latest.summary;
      setMessage("Analysis saved.");
      render();
    } catch (error) {
      setMessage(error.message);
    }
  });
  root.querySelectorAll("[data-jathon-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      activeTab = button.dataset.jathonTab || "overview";
      root.querySelectorAll("[data-jathon-tab]").forEach((node) => node.classList.remove("active"));
      button.classList.add("active");
      render();
    });
  });

  drawer.classList.add("open");
  void loadCvs();

  async function loadCvs() {
    try {
      const cvs = await apiGet("/cvs");
      cv.innerHTML = cvs.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join("");
      if (!cvs.length) cv.innerHTML = `<option value="">Upload a CV in dashboard first</option>`;
      setMessage(cvs.length ? "Ready." : "No CV uploaded yet.");
    } catch {
      cv.innerHTML = `<option value="">Backend offline</option>`;
      setMessage("Start Jobathon backend with docker compose up.");
    }
  }

  function render() {
    if (!latest) {
      resultBox.innerHTML = `<p class="muted">Run an analysis to fill this panel.</p>`;
      return;
    }
    if (activeTab === "requirements") {
      resultBox.innerHTML = latest.requirement_matches
        .map((item) => `<div class="jathon-item"><b>${escapeHtml(item.status)}</b><br>${escapeHtml(item.requirement)}<br><span>${escapeHtml(item.explanation)}</span></div>`)
        .join("");
    } else if (activeTab === "gaps") {
      resultBox.innerHTML = list(latest.gaps);
    } else if (activeTab === "cover") {
      resultBox.innerHTML = `<div class="jathon-item">${escapeHtml(latest.cover_letter).replace(/\n/g, "<br>")}</div><div class="jathon-item"><b>Recruiter</b><br>${escapeHtml(latest.recruiter_message)}</div>`;
    } else {
      resultBox.innerHTML = list(latest.strengths);
    }
  }
}

async function apiGet(path) {
  const response = await fetch(`http://localhost:8000${path}`);
  if (!response.ok) throw new Error("Backend offline.");
  return response.json();
}

async function apiPost(path, payload) {
  let response;
  try {
    response = await fetch(`http://localhost:8000${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error("Start Jobathon backend with docker compose up.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Backend request failed.");
  }
  return response.json();
}

function list(items) {
  return items.length ? items.map((item) => `<div class="jathon-item">${escapeHtml(item)}</div>`).join("") : `<p class="muted">Nothing to show yet.</p>`;
}

function escapeHtml(value) {
  const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
  return String(value).replace(/[&<>"']/g, (char) => entities[char] || char);
}

const css = `
#jobathon-root {
  all: initial;
  position: relative;
  z-index: 2147483647;
  font-family: Inter, ui-sans-serif, system-ui, "Segoe UI", sans-serif;
}
#jobathon-root * { box-sizing: border-box; letter-spacing: 0; }
#jobathon-fab {
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
#jobathon-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(420px, calc(100vw - 28px));
  transform: translateX(calc(100% + 28px));
  transition: transform .18s ease;
  border: 1px solid #2c3042;
  border-radius: 8px 0 0 8px;
  background: #090a12;
  color: #f4f7fb;
  box-shadow: 0 22px 70px rgba(0,0,0,.55);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font: 13px/1.4 Inter, system-ui, sans-serif;
}
#jobathon-drawer.open { transform: translateX(0); }
.jathon-head, .jathon-row, .jathon-score, .jathon-tabs { display: flex; align-items: center; gap: 8px; }
.jathon-head { justify-content: space-between; }
.jathon-head p { margin: 0; color: #00e5ff; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; }
.jathon-head h2 { margin: 0; font-size: 19px; color: #f4f7fb; }
#jobathon-root button, #jobathon-root select, #jobathon-root textarea {
  border: 1px solid #2c3042;
  border-radius: 6px;
  background: #141622;
  color: #f4f7fb;
  padding: 9px;
  font: inherit;
}
#jobathon-root button { cursor: pointer; font-weight: 700; }
#jathon-close { width: 34px; }
#jathon-text { min-height: 130px; resize: vertical; }
.jathon-row > *, .jathon-tabs > * { flex: 1; }
.jathon-primary { background: linear-gradient(135deg, #ff304f, #8b2cff) !important; border-color: rgba(255,48,79,.7) !important; }
#jathon-message { min-height: 18px; margin: 0; color: #9aa4b7; }
.jathon-score { border: 1px solid #2c3042; border-radius: 8px; padding: 9px; background: #10121c; }
#jathon-score {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  border: 2px solid #00e5ff;
  color: #00e5ff;
  font-size: 18px;
}
.jathon-tabs button.active { border-color: #00e5ff !important; color: #00e5ff !important; }
#jathon-result { overflow: auto; min-height: 120px; border: 1px solid #2c3042; border-radius: 8px; padding: 9px; background: #0f111b; }
.jathon-item { padding: 8px 0; border-bottom: 1px solid #2c3042; color: #f4f7fb; }
.jathon-item:last-child { border-bottom: 0; }
.jathon-item span, .muted { color: #9aa4b7; }
`;
