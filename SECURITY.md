# Security and data handling

ModalityOps v0.1 is a **single-user, local-only service**. Do not expose its API directly to the internet. It has no authentication, tenant isolation, encryption-at-rest or retention scheduler.

- Docker publishes port 8000 on `127.0.0.1` only. The application rejects unexpected hostnames and cross-origin POST requests.
- Request bodies are capped at 32 MiB; schemas bound streams, channels and samples. Two analysis jobs may execute concurrently per process. These are safeguards, not a guarantee against resource exhaustion. Keep the service local.
- API requests accept session data, not arbitrary filesystem paths or remote URLs. The CLI intentionally reads user-selected local files.
- The API stores derived reports only, using atomic writes. Reports still contain signal summaries, labels and identifiers. Protect them as you would the original recording. Host operators control the storage volume and retention.
- Do not commit research data, recordings, transcripts, notebook outputs, model caches, credentials or private event labels. `.gitignore` helps but is not a privacy control by itself.
- Media parsing is a trust boundary. Import files from trusted sources, use a constrained environment for unknown files, and keep PyAV/FFmpeg and MNE dependencies updated.
- Keep required third-party license notices. Do not include participant data in bug reports.

For security reports, use GitHub private vulnerability reporting if enabled. Otherwise contact the repository owner privately before disclosing exploitable details. The public issue tracker should contain only sanitized reproductions.
