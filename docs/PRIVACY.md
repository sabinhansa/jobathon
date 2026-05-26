# Privacy

- CVs are stored locally only.
- Analyses are stored locally only.
- Embeddings are stored in the local Chroma volume.
- No telemetry is included.
- No cloud API is required for the MVP.
- Uploaded files are parsed as documents and never executed.
- Raw HTML from job postings is cleaned as text and not rendered as trusted HTML.

The extension calls only the local backend. Do not expose the backend port publicly unless you add authentication.

