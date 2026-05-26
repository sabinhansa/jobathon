# Jobathon

Jobathon is a local-first job/CV matching tool with a FastAPI backend, local embeddings, Ollama-powered analysis, a compact dashboard, and a Chromium Manifest V3 extension that feels like a browser-native job assistant.

It is designed for manual, explicit use while reading job posts. It does not mass scrape LinkedIn, automate applications, auto-message recruiters, bypass site restrictions, or send CV/job data to cloud APIs.

## What It Does

- Stores your CV locally.
- Extracts text from PDF, DOCX, TXT, or Markdown CVs.
- Chunks and embeds CV evidence locally.
- Cleans pasted job text.
- Extracts structured job requirements with Ollama when available, with deterministic fallback parsing.
- Compares job requirements against CV evidence.
- Produces a match score, requirement table, strengths, gaps, CV bullet suggestions, cover letter draft, recruiter message draft, and interview prep bullets.
- Saves analysis history locally.
- Provides a browser popup and an injected floating drawer on common job pages.

## Privacy

- No OpenAI API key is required.
- No telemetry is included.
- CVs and analyses are stored in your local Postgres Docker volume.
- Embeddings are stored in your local Chroma Docker volume.
- The extension only calls `http://localhost:8000` or `http://127.0.0.1:8000`.
- Visible page text is extracted only after you click the extraction button.

## Requirements

- Docker Desktop
- Node.js 20+ for building the extension
- Optional host Ollama, if you prefer running Ollama outside Docker

## Quickstart

```powershell
cd jobathon
Copy-Item .env.example .env
docker compose up --build
```

Check backend health:

```powershell
curl http://localhost:8000/health
```

Pull the default model inside the Ollama container:

```powershell
docker exec -it jobathon-ollama-1 ollama pull qwen3:8b
```

Or, if you run Ollama on the host:

```powershell
ollama pull qwen3:8b
```

Then set this in `.env`:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Restart the backend:

```powershell
docker compose up --build backend
```

## Upload a CV

Open the dashboard:

[http://localhost:8000/app](http://localhost:8000/app)

Upload a PDF, DOCX, or TXT CV from the CV Vault panel.

## Build the Extension

```powershell
cd extension
npm install
npm run build
```

The loadable extension is created in `extension/dist`.

## Load in Opera GX or Chrome

1. Open the browser extensions page.
2. Enable developer mode.
3. Choose **Load unpacked**.
4. Select `jobathon/extension/dist`.
5. Pin the Jobathon toolbar button if desired.

## Use With LinkedIn

1. Open a job page.
2. Click the Jobathon extension icon or the floating `JA` button.
3. Paste the job text, or click **Extract visible page text**.
4. Select your saved CV.
5. Click **Analyze Job**.

Jobathon does not scrape in the background. Extraction is explicit and limited to visible page text.

## API

- `GET /health`
- `POST /cvs/upload`
- `GET /cvs`
- `GET /cvs/{cv_id}`
- `DELETE /cvs/{cv_id}`
- `GET /preferences`
- `POST /preferences`
- `POST /jobs/clean`
- `POST /analysis/analyze`
- `GET /analysis/history`
- `GET /analysis/{analysis_id}`
- `DELETE /analysis/{analysis_id}`
- `POST /analysis/{analysis_id}/regenerate`

## Troubleshooting

Backend offline:

```powershell
docker compose ps
docker compose logs backend
```

Ollama offline:

- Confirm `OLLAMA_BASE_URL` in `.env`.
- If using Docker Ollama, confirm the `ollama` service is running.
- If using host Ollama on Windows, use `http://host.docker.internal:11434`.

Model not found:

```powershell
docker exec -it jobathon-ollama-1 ollama pull qwen3:8b
```

CORS issue:

- Reload the extension after rebuilding.
- Confirm the backend is on `localhost:8000`.

Extension cannot reach localhost:

- Try `http://127.0.0.1:8000/health` in the browser.
- Restart the browser after loading the extension.

Docker GPU issues:

- The MVP works on CPU.
- Add GPU-specific Ollama Compose settings only after the CPU path works.

## Future Upgrades

- Multiple CV versions.
- ATS keyword export.
- Job tracking Kanban.
- Optional web search.
- Cloud sync as an explicit opt-in.
- Optional OpenAI API premium mode.
- Optional MCP integrations.
