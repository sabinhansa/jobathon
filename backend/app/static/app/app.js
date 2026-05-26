const API = window.location.origin;

const state = {
  cvs: [],
};

const $ = (id) => document.getElementById(id);

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function loadHealth() {
  try {
    const health = await request("/health");
    $("health").textContent = `Backend ${health.status} | Ollama ${health.ollama} | Chroma ${health.chroma}`;
  } catch (error) {
    $("health").textContent = "Backend offline";
  }
}

async function loadCvs() {
  state.cvs = await request("/cvs");
  $("cvSelect").innerHTML = state.cvs.map((cv) => `<option value="${cv.id}">${cv.name}</option>`).join("");
  if (!state.cvs.length) {
    $("cvSelect").innerHTML = `<option value="">Upload a CV first</option>`;
  }
}

async function loadHistory() {
  const items = await request("/analysis/history");
  $("history").innerHTML =
    items
      .map(
        (item) =>
          `<button type="button" data-id="${item.id}">${item.final_score}/100 - ${item.job_title || "Untitled role"} - ${item.company || "Unknown company"}</button>`,
      )
      .join("") || `<p class="muted">No analyses yet.</p>`;
  document.querySelectorAll("[data-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      const analysis = await request(`/analysis/${button.dataset.id}`);
      $("score").textContent = analysis.final_score;
      $("result").textContent = analysis.markdown_report;
    });
  });
}

$("cvForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("cvFile").files[0];
  if (!file) return;
  const form = new FormData();
  form.append("upload", file);
  $("cvStatus").textContent = "Uploading...";
  try {
    const result = await request("/cvs/upload", { method: "POST", body: form });
    $("cvStatus").textContent = `Saved ${result.name} with ${result.chunk_count} chunks.`;
    await loadCvs();
  } catch (error) {
    $("cvStatus").textContent = error.message;
  }
});

$("prefsForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    target_roles: $("targetRoles").value.split(",").map((item) => item.trim()).filter(Boolean),
    preferred_locations: $("locations").value.split(",").map((item) => item.trim()).filter(Boolean),
    seniority: $("seniority").value || null,
    tone: $("tone").value || "confident, concise, practical",
  };
  try {
    await request("/preferences", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    $("prefsStatus").textContent = "Preferences saved.";
  } catch (error) {
    $("prefsStatus").textContent = error.message;
  }
});

$("analyzeButton").addEventListener("click", async () => {
  const cvId = $("cvSelect").value;
  if (!cvId) {
    $("result").textContent = "Upload a CV first.";
    return;
  }
  const payload = {
    cv_id: cvId,
    job_text: $("jobText").value,
    job_title: $("jobTitle").value || null,
    company: $("company").value || null,
    mode: "fast",
  };
  $("result").textContent = "Analyzing...";
  try {
    const result = await request("/analysis/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    $("score").textContent = result.overall_score;
    $("result").textContent = result.markdown_report;
    await loadHistory();
  } catch (error) {
    $("result").textContent = error.message;
  }
});

$("refreshHistory").addEventListener("click", loadHistory);

loadHealth();
loadCvs().catch(() => {});
loadHistory().catch(() => {});
