# Local LLM Setup

Default model:

```env
LOCAL_LLM_MODEL=qwen3:8b
```

Docker Ollama:

```powershell
docker compose up ollama
docker exec -it jobathon-ollama-1 ollama pull qwen3:8b
```

Host Ollama:

```powershell
ollama serve
ollama pull qwen3:8b
```

Set:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

The backend falls back to deterministic parsing/matching when Ollama is unreachable, but generated report quality is better with the model pulled.

