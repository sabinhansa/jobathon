# Optional MCP Server

MCP is intentionally not required for JobFit GX runtime.

A future optional MCP server can expose:

- `upload_cv`
- `list_cvs`
- `analyze_job`
- `get_job_history`
- `update_preferences`
- `generate_cover_letter`

It should call the same FastAPI backend or share the same Python service layer. Keep it isolated from the browser extension and normal user workflow.

