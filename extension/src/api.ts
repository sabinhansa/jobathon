import type { AnalyzeRequest, AnalyzeResponse, CVListItem, HealthResponse } from "./types";

const DEFAULT_BASE_URL = "http://localhost:8000";

export async function getBaseUrl(): Promise<string> {
  const stored = await chrome.storage.local.get(["jobathonBaseUrl"]);
  return stored.jobathonBaseUrl || DEFAULT_BASE_URL;
}

export async function setBaseUrl(baseUrl: string): Promise<void> {
  await chrome.storage.local.set({ jobathonBaseUrl: baseUrl.replace(/\/$/, "") });
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const baseUrl = await getBaseUrl();
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, options);
  } catch {
    throw new Error("Start Jobathon backend with docker compose up.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => apiRequest<HealthResponse>("/health"),
  cvs: () => apiRequest<CVListItem[]>("/cvs"),
  analyze: (payload: AnalyzeRequest) =>
    apiRequest<AnalyzeResponse>("/analysis/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  uploadCv: (file: File) => {
    const form = new FormData();
    form.append("upload", file);
    return apiRequest("/cvs/upload", { method: "POST", body: form });
  },
  preferences: () => apiRequest("/preferences"),
};

