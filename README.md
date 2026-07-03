# CI/CD AI Assistant

LLM-powered root-cause analysis for CI/CD pipeline failures. When a GitHub
Actions job fails, this service analyzes the raw log with Google Gemini and
returns a structured root cause + fix suggestion — typically in place of
30+ minutes of manual log spelunking.

## Architecture

```
GitHub Actions job fails
        │  if: failure()
        ▼
curl POST /analyze  ──────────────►  FastAPI service
                                          │
                                          ├─ sanitize_log()      (strip secrets)
                                          ├─ build_prompt()      (4-part structured prompt)
                                          ├─ GeminiClient.generate()  (retry + backoff)
                                          ├─ parse_llm_response() (defensive JSON parsing)
                                          └─ persist to DB (SQLAlchemy)
                                          │
        ◄─────────────────────────────────
   JSON: root_cause, fix_suggestion, confidence_level
        │
        ▼
Posted as a PR comment via GitHub API (see examples/consumer-workflow.yml)
```

## Stack

| Layer | Choice | Why |
|---|---|---|
| API framework | FastAPI | Native async — critical since the Gemini call takes 2-5s; auto OpenAPI docs; Pydantic validation built in |
| LLM | Google Gemini 1.5 Flash | Generous free tier, large context window for long logs, JSON-friendly output |
| ORM | SQLAlchemy 2.0 | DB-engine abstraction — swapping SQLite for Postgres is a one-line `DATABASE_URL` change |
| Migrations | Alembic | Schema changes in production without data loss |
| Container | Docker (multi-stage) | Small, build-tool-free runtime image |
| Registry | GHCR | Free, integrated with `GITHUB_TOKEN`, no extra secrets needed |
| Retry | `tenacity` | Exponential backoff on Gemini API failures |

## Project layout

```
app/
  main.py              FastAPI app, exception handling, health check
  config.py            Settings via env vars (pydantic-settings)
  database.py          Engine/session (swap DATABASE_URL for Postgres)
  models.py            SQLAlchemy ORM models
  schemas.py            Pydantic request/response contracts
  core/security.py      Shared-secret API key auth
  routers/
    analyze.py          POST /analyze
    reports.py           GET /reports, GET /reports/{id}
  services/
    sanitizer.py         Secret redaction + log truncation
    prompt_builder.py     4-part structured prompt construction
    gemini_client.py      Gemini SDK wrapper, retry/backoff
    parser.py             Defensive JSON parsing with fallback
    analysis_service.py   Orchestrates the end-to-end flow
alembic/                 DB migrations
tests/                   pytest: unit + integration (mocked Gemini)
.github/workflows/       CI (lint+test) and Docker publish (this repo's own pipeline)
examples/consumer-workflow.yml   Drop-in snippet for ANY repo to call this service
```

## Running locally

```bash
cp .env.example .env        # fill in GEMINI_API_KEY
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for interactive API docs.

### With Docker

```bash
docker compose up --build
```

> Note: the default database is SQLite at `./pipeline_analysis.db`. In a container, make sure the app can write to the working directory or override `DATABASE_URL` to a writable path such as `sqlite:////tmp/pipeline_analysis.db`.

## Running tests

```bash
pytest --cov=app --cov-report=term-missing
```

Tests mock the Gemini client (`GeminiClient.generate`) — no real API key or
network call is needed to run the suite.

## GitHub Actions integration

This repository includes an example automated consumer workflow at
`.github/workflows/consumer-failure-analysis.yml`.

To use it in any repository:

1. Copy `.github/workflows/consumer-failure-analysis.yml` into your target
   repository's `.github/workflows/` directory.
2. Add these two GitHub Actions secrets in the target repository:
   - `CICD_ASSISTANT_API_URL` — the deployed URL of your AI Assistant,
     e.g. `https://your-service.example.com`
   - `CICD_ASSISTANT_API_KEY` — the shared secret API key accepted by the
     `/analyze` endpoint
3. Ensure your existing workflow defines a build/test job. The example file
   includes a placeholder `build-and-test` job, which you should replace with
   your repository's real commands.

Once configured, the `analyze-on-failure` job runs only if the build/test job
fails, sends the real GitHub Actions log to `/analyze`, and posts the
structured analysis as a PR comment.

## API

| Endpoint | Purpose |
|---|---|
| `POST /analyze` | Ingest a log, run analysis, persist + return result |
| `GET /reports` | Paginated history (`?page=&page_size=&pipeline_name=&org_id=`) |
| `GET /reports/{id}` | Single report by ID |
| `GET /health` | Liveness/readiness check |

All endpoints (except `/health`) require an `X-API-Key` header matching the
`API_KEY` env var if one is configured.

## Prompt engineering

The prompt sent to Gemini has four explicit parts (see `prompt_builder.py`):

1. **System context** — role + task definition.
2. **Log input** — wrapped in `<log>...</log>` delimiters and explicitly
   marked as data-not-instructions, to mitigate prompt injection from
   adversarial log content.
3. **Output schema** — explicit JSON field definitions.
4. **Hard constraint** — "respond with ONLY valid JSON."

Logs are truncated to the last `MAX_LOG_CHARS` characters (default 8000)
before sending — the actual failure is almost always at the tail of a CI
log, not the head.

## Reliability decisions

| Problem | Mitigation |
|---|---|
| Gemini returns freeform text instead of JSON | `parser.py` strips code fences, extracts the first `{...}` block, and as a last resort returns the raw text as `fix_suggestion` with `confidence_level: null` rather than crashing |
| Gemini API down/timeout | `tenacity` retries with exponential backoff (3 attempts); if still failing, the record is persisted as `FAILED` and a clean error is returned — never a bare 500 |
| Long logs exceed token limits | Tail-truncation to `MAX_LOG_CHARS` |
| Low-confidence / hallucinated fixes | `confidence_level` surfaced in the response; `low_confidence_warning: true` when below 0.5 or unparseable, so the PR comment can show a disclaimer |
| Secrets leaking into logs sent to a third-party LLM | `sanitizer.py` regex-redacts API keys, tokens, passwords, AWS/GitHub credential patterns, and PEM private keys before the log ever leaves this service |

## Security

- API keys/secrets are injected via environment variables, never committed.
- Inbound requests require a shared-secret `X-API-Key` header (see
  `core/security.py`) — appropriate since the caller is a CI runner, not an
  end user; would upgrade to per-org JWT if multi-tenant.
- The Docker image runs as a non-root user.
- Log content is sanitized before both LLM submission and persistence.

## Scaling beyond a single instance

The current `/analyze` endpoint is synchronous — the caller waits for the
full Gemini round trip. To handle high concurrent failure volume:

1. Replace the synchronous Gemini call with a Celery + Redis task queue;
   `/analyze` enqueues and returns `202 Accepted` with a job ID immediately.
2. Run multiple FastAPI workers behind a load balancer.
3. Migrate `DATABASE_URL` to PostgreSQL with `pgBouncer` connection pooling
   (no code change required beyond the connection string, by design).
4. Add per-org rate limiting on Gemini calls.
5. The caller polls `GET /reports/{id}` until `status` flips from
   `PENDING` to `ANALYZED`.

## Multi-tenant readiness

The `org_id` field already exists on `PipelineAnalysis` and is accepted on
`POST /analyze` and filterable on `GET /reports`. Promoting this to full
multi-tenancy means: resolving `org_id` from the API key/JWT instead of
trusting the request body, and scoping all queries by the authenticated
org — both small, contained changes given the schema is already in place.

## What's intentionally deferred (and why)

- **SQLite, not Postgres** — correct for current single-instance write
  volume; the ORM makes the future migration a connection-string change.
- **No async task queue yet** — adds operational complexity (Redis, worker
  processes) not justified until failure volume requires it; the
  synchronous path is the simplest thing that works today.
- **No formal LLM accuracy metric yet** — see `confidence_level` and the
  low-confidence disclaimer as the interim mitigation; a labeled
  precision/recall benchmark is the natural next step once enough
  human-labeled feedback (thumbs up/down on PR comments) is collected.
