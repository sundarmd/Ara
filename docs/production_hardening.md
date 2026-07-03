# Production Hardening Boundary

ARA is currently a local development and demo reference implementation. It is not a production enterprise research platform yet.

## Current State

The repository has a local Docker Compose setup, explicit CORS allowlists, upload file count and size limits, an optional coarse API-key gate, local SQLite metadata stores, ChromaDB vector persistence, and local test/eval commands. These are useful for development and interview demos, but they do not replace production controls.

## Required Before Production

### Authentication And RBAC

Replace the optional API-key gate with real identity, session handling, and role-based access control. Document-level access should be enforced server-side for uploads, document listing, file serving, chat, debug endpoints, and deletion.

### CORS And Public URLs

Lock CORS to deployed frontend origins. Configure `API_PUBLIC_BASE_URL` for public API and citation-link base URLs behind reverse proxies, HTTPS domains, and non-local deployments instead of relying on local host/port inference.

### Secrets

Keep provider keys and deployment secrets out of source control. Use a secret manager or deployment platform secret store, rotate exposed keys, and separate development, staging, and production credentials.

### CI And Evals

GitHub Actions now runs a lightweight quality gate on pushes and pull requests to `main` and `beta`. The workflow checks backend unit tests, frontend lint, frontend build, golden eval dry-run validation, and Docker Compose configuration. This is a development and demo-readiness gate; production release governance would still need branch protection, deployment smoke tests, eval thresholds, monitoring, and rollback procedures.

### Observability And Audit Logs

Add structured request logs, provider-call metrics, ingestion traces, error monitoring, and durable audit logs for uploads, deletes, document reads, and chat interactions.

### Rate Limits And Abuse Controls

Add request throttling, upload quotas, provider-budget limits, and safe failure behavior for OCR, embeddings, chat, and web-search providers.

### Backups And Migrations

Define database migration procedures, backup schedules, restore tests, and retention policies for SQLite data, ChromaDB persistence, uploaded PDFs, extracted images, and table artifacts.

### Data Privacy

Classify uploaded documents, document what leaves the machine for OCR/LLM/web providers, and add retention, deletion, and redaction policies before handling sensitive enterprise research at scale.

### Deployment

Use immutable production images, pinned runtime configuration, health checks, TLS, reverse-proxy headers, resource limits, and separate persistent volumes or managed storage.

### Governance

Define model/provider review, prompt-change review, eval thresholds, incident response, and ownership for operational runbooks.
