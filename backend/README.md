# StreamDoctor backend

FastAPI backend for volunteer stream observations, private photo uploads, AI second
opinions, explainable trust assessments, independent expert review, stream diagnosis cards,
Trust Lens comparisons, monitoring needs, synthetic FHIR export, and reproducible benchmarks.

Python 3.12+ is required. PostgreSQL is the deployment database; SQLite is supported for
local development. Run commands from `StreamDoctor/backend/`.

## Windows quick start

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.cli seed-demo-sites
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --no-proxy-headers
```

## macOS/Linux quick start

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m app.cli seed-demo-sites
.venv/bin/python -m uvicorn app.main:app --reload --no-proxy-headers
```

Open http://localhost:8000/docs. Register an account, log in, and paste the returned token
into **Authorize**. The default configuration uses SQLite and leaves AI disabled.
Demo sites are fictional and require reports labelled `is_synthetic: true`.

## Complete local demo

```bash
python -m app.demo --directory demo
python -m uvicorn app.main:app --env-file demo/demo.env --reload --no-proxy-headers
```

This creates a separate database with fictional accounts, generated passwords, synthetic
images, scripted review decisions, and a working Trust Lens comparison. See `docs/DEMO.md`.
Run `python -m app.benchmark --output benchmarks/results.json` to reproduce the test-set metrics.

## PostgreSQL with Docker

Copy `.env.example` to `.env`. Generate a URL-safe password with:

```bash
python -c "import secrets; print(secrets.token_hex(24))"
```

Set `POSTGRES_PASSWORD` to that value in `.env`, then run:

```bash
docker compose up --build
```

Compose starts the API and PostgreSQL, applies migrations, and persists both database and
photo files in named volumes. `docker compose down` retains those volumes; adding `-v`
deletes them. The AI service is supplied separately.

For a hosted PostgreSQL database, set `DATABASE_URL` to its connection URL and run
`python -m alembic upgrade head`. URL-encode special characters in database passwords and
use the provider's TLS settings.

## Updating an existing installation

Keep `.env`, your database, and photo storage. Update the backend source and replace the
backend documentation directory with the current one. In the existing Python environment:

```bash
python -m pip install -r requirements.txt
python -m alembic upgrade head
```

Do not downgrade or delete the database to upgrade. Existing migration identifiers are
preserved. Existing submitted reports can be assessed with
`POST /api/v1/reports/{report_id}/assessment`; new submissions are assessed automatically.
Retain the same Docker Compose project name when moving directories so existing volumes
are reused. Run migrations once before starting multiple production instances.

## Accounts and reviewers

New accounts always have the volunteer role. Passwords use Argon2. Bearer sessions expire
and are revoked immediately on logout; only token digests are stored.

Register the reviewer account first, then assign its role from a trusted server terminal:

```bash
python -m app.cli set-role reviewer@example.com reviewer
```

For Docker, prefix the command with `docker compose exec api`. Role changes revoke existing
sessions, so sign in again afterward. Reviewers cannot review their own reports.

```bash
python -m app.cli set-role reviewer@example.com volunteer
python -m app.cli disable-user reviewer@example.com
```

## Configuration

Copy `.env.example` and keep your actual `.env` out of Git.

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | Production requires PostgreSQL and disallows mock AI |
| `DATABASE_URL` | `sqlite:///./streamdoctor.db` | Database connection |
| `CORS_ORIGINS` | localhost ports 5173/3000 | JSON array of exact frontend origins |
| `SESSION_TTL_MINUTES` | `60` | Bearer session duration |
| `AUTH_RATE_LIMIT` | `10` | Authentication attempts per IP/window |
| `AUTH_RATE_WINDOW_SECONDS` | `60` | Authentication rate-limit window |
| `UPLOAD_DIR` | `storage/photos` | Private photo directory |
| `MAX_PHOTO_BYTES` | `8388608` | Maximum uploaded bytes |
| `MAX_STORED_PHOTO_BYTES` | `33554432` | Maximum normalized photo bytes |
| `MAX_PHOTO_PIXELS` | `16000000` | Maximum decoded pixels |
| `MAX_PHOTOS_PER_REPORT` | `5` | Photo count limit |
| `AI_MODE` | `disabled` | `disabled`, `mock`, or `http` |
| `AI_SERVICE_URL` | unset | Complete inference endpoint for HTTP mode |
| `AI_SERVICE_TOKEN` | unset | Optional server-to-server credential |
| `AI_TIMEOUT_SECONDS` | `30` | AI network timeout |
| `AI_MAX_RESPONSE_BYTES` | `65536` | AI JSON response limit |
| `AI_RATE_LIMIT` | `6` | New AI requests per user/minute |

