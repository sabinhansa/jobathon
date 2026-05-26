# Architecture

Jobathon is local-first. The extension is a thin client and the FastAPI backend owns storage, parsing, embeddings, LLM calls, and report generation.

## Services

- `backend`: FastAPI, SQLModel, CV parsing, matching, report generation.
- `db`: Postgres for CV metadata, raw text, preferences, and analysis history.
- `chroma`: Vector store for CV chunk embeddings.
- `ollama`: Local LLM runtime.

## Flow

1. User uploads a CV.
2. Backend extracts text, sanitizes metadata, chunks CV evidence, and stores embeddings.
3. User pastes or explicitly extracts visible job text.
4. Backend cleans and structures the job post.
5. Backend retrieves relevant CV chunks per requirement.
6. LLM compares requirements only against provided evidence.
7. Backend computes deterministic score and stores report.

## Trust Boundary

The extension never stores model credentials and never calls cloud LLM APIs. It sends data only to the local backend.

