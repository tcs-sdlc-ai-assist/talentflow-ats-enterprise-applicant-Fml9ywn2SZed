# TalentFlow ATS — Deployment Guide

## Overview

TalentFlow ATS is a Python + FastAPI application designed for deployment on Vercel's serverless platform. This guide covers environment setup, configuration, database considerations, build steps, CI/CD integration, and troubleshooting.

---

## Prerequisites

- Python 3.11+
- A Vercel account with CLI installed (`npm i -g vercel`)
- A hosted PostgreSQL database (Vercel Postgres, Neon, Supabase, or Railway)
- Git repository connected to Vercel

---

## Environment Variables

Configure the following environment variables in the Vercel dashboard under **Settings → Environment Variables**. Set them for **Production**, **Preview**, and **Development** as appropriate.

### Required

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string (async driver) | `postgresql+asyncpg://user:pass@host:5432/talentflow` |
| `SECRET_KEY` | JWT signing key — generate with `openssl rand -hex 64` | `a3f8c9...` |
| `ENVIRONMENT` | Deployment environment identifier | `production` |

### Optional

| Variable | Description | Default |
|---|---|---|
| `ALLOWED_ORIGINS` | Comma-separated CORS origins | `*` (override in production) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token lifetime in minutes | `30` |
| `DATABASE_POOL_SIZE` | SQLAlchemy connection pool size | `5` |
| `DATABASE_MAX_OVERFLOW` | Max overflow connections | `10` |
| `LOG_LEVEL` | Python logging level | `INFO` |
| `BCRYPT_ROUNDS` | Bcrypt hashing cost factor | `12` |

### Setting Variables via CLI

```bash
vercel env add DATABASE_URL production
vercel env add SECRET_KEY production
vercel env add ENVIRONMENT production
```

### Local Development

Create a `.env` file in the project root (never commit this file):

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/talentflow
SECRET_KEY=dev-secret-key-change-in-production
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
LOG_LEVEL=DEBUG
```

---

## Vercel Configuration

### `vercel.json`

Place this file in the project root:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "main.py"
    }
  ],
  "env": {
    "ENVIRONMENT": "production"
  },
  "regions": ["iad1"],
  "functions": {
    "main.py": {
      "memory": 1024,
      "maxDuration": 30
    }
  }
}
```

### Key Configuration Notes

- **`@vercel/python`** — Vercel's Python runtime expects an ASGI-compatible app. FastAPI is ASGI-native and works out of the box.
- **`regions`** — Choose the region closest to your database. `iad1` (US East) pairs well with Vercel Postgres and Neon's default regions.
- **`memory`** — 1024 MB is recommended. Reduce to 512 MB for cost savings if your workload allows.
- **`maxDuration`** — 30 seconds max for Pro plans. Free tier is limited to 10 seconds.

### Entry Point

Vercel looks for an `app` variable in the file specified by `builds.src`. Ensure `main.py` exposes the FastAPI instance:

```python
# main.py
from fastapi import FastAPI

app = FastAPI(title="TalentFlow ATS")

# ... routes, middleware, etc.
```

---

## Database Considerations for Serverless

### Connection Pooling

Serverless functions spin up and down frequently. Without connection pooling, you will exhaust database connections quickly.

**Recommended: Use an external connection pooler.**

| Provider | Pooler | Notes |
|---|---|---|
| Neon | Built-in pooler (PgBouncer) | Use the pooled connection string ending in `-pooler` |
| Supabase | Built-in PgBouncer on port 6543 | Use `?pgbouncer=true` parameter |
| Vercel Postgres | Built-in pooling | Use `POSTGRES_URL` (pooled) not `POSTGRES_URL_NON_POOLING` |
| Self-hosted | Deploy PgBouncer separately | Transaction mode recommended |

### SQLAlchemy Async Engine Settings for Serverless

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    DATABASE_URL,
    pool_size=1,          # Minimal pool for serverless
    max_overflow=2,        # Allow small burst
    pool_timeout=30,
    pool_recycle=300,      # Recycle connections every 5 minutes
    pool_pre_ping=True,    # Verify connections before use
)
```

### Migrations

Vercel does not run migrations automatically. Run migrations **before** deploying or as part of your CI/CD pipeline.

```bash
# Using Alembic
alembic upgrade head

# Or using a migration script
python -m scripts.migrate
```

**Important:** Use the **non-pooled / direct** connection string for migrations, not the pooled one. Migrations require DDL operations that are incompatible with PgBouncer in transaction mode.

### SQLite (Development Only)

For local development without PostgreSQL:

```env
DATABASE_URL=sqlite+aiosqlite:///./talentflow.db
```

**Do not use SQLite in production on Vercel.** The serverless filesystem is ephemeral — data will be lost between invocations.

---

## Build Steps

### Local Build Verification

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run database migrations
alembic upgrade head

# 4. Start development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 5. Run tests
pytest -v
```

### Vercel Build

Vercel automatically:

1. Detects `requirements.txt` and installs dependencies
2. Bundles the application using `@vercel/python`
3. Deploys the serverless function

No custom build command is needed. If you require a build step (e.g., generating static assets), add it to `vercel.json`:

```json
{
  "buildCommand": "pip install -r requirements.txt && python scripts/prebuild.py"
}
```

### Deploying

```bash
# Preview deployment
vercel

# Production deployment
vercel --prod

# Deploy from specific branch
vercel --prod --scope your-team
```

---

## CI/CD Integration

### GitHub Actions (Recommended)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Vercel

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
  VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: talentflow_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run linting
        run: |
          pip install ruff
          ruff check .

      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/talentflow_test
          SECRET_KEY: test-secret-key
          ENVIRONMENT: test
        run: pytest -v --tb=short

  deploy-preview:
    needs: test
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Vercel CLI
        run: npm install -g vercel

      - name: Pull Vercel Environment
        run: vercel pull --yes --environment=preview --token=${{ secrets.VERCEL_TOKEN }}

      - name: Build
        run: vercel build --token=${{ secrets.VERCEL_TOKEN }}

      - name: Deploy Preview
        run: vercel deploy --prebuilt --token=${{ secrets.VERCEL_TOKEN }}

  deploy-production:
    needs: test
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Vercel CLI
        run: npm install -g vercel

      - name: Pull Vercel Environment
        run: vercel pull --yes --environment=production --token=${{ secrets.VERCEL_TOKEN }}

      - name: Build
        run: vercel build --prod --token=${{ secrets.VERCEL_TOKEN }}

      - name: Deploy Production
        run: vercel deploy --prebuilt --prod --token=${{ secrets.VERCEL_TOKEN }}
```

### Required GitHub Secrets

| Secret | How to obtain |
|---|---|
| `VERCEL_TOKEN` | Vercel Dashboard → Settings → Tokens |
| `VERCEL_ORG_ID` | Run `vercel link` locally, check `.vercel/project.json` |
| `VERCEL_PROJECT_ID` | Run `vercel link` locally, check `.vercel/project.json` |

### Database Migrations in CI/CD

Add a migration step before deployment:

```yaml
- name: Run migrations
  env:
    DATABASE_URL: ${{ secrets.PRODUCTION_DATABASE_URL_DIRECT }}
  run: alembic upgrade head
```

Use the **direct (non-pooled)** database URL for migrations.

---

## Troubleshooting

### Common Issues

#### 1. `ModuleNotFoundError: No module named 'xyz'`

**Cause:** Missing dependency in `requirements.txt`.

**Fix:** Ensure all dependencies are listed:

```bash
pip freeze > requirements.txt
# Or maintain requirements.txt manually and verify:
pip install -r requirements.txt
```

#### 2. `Function timed out` (Vercel 504)

**Cause:** Cold start + slow database connection or heavy initialization.

**Fix:**
- Use connection pooling (see Database section above)
- Set `pool_pre_ping=True` on the SQLAlchemy engine
- Reduce `maxDuration` expectations or upgrade Vercel plan
- Minimize top-level imports — lazy-load heavy modules

#### 3. `CORS errors in browser`

**Cause:** `ALLOWED_ORIGINS` not configured or mismatched.

**Fix:** Set the exact frontend origin:

```env
ALLOWED_ORIGINS=https://your-app.vercel.app,https://your-custom-domain.com
```

Never use `*` in production with credentials.

#### 4. `MissingGreenlet: greenlet_spawn has not been called`

**Cause:** SQLAlchemy lazy loading triggered in async context.

**Fix:** Ensure ALL `relationship()` declarations use `lazy="selectin"`:

```python
class Job(Base):
    applications = relationship("Application", back_populates="job", lazy="selectin")
```

#### 5. `Connection refused` or `too many connections`

**Cause:** Serverless functions opening too many database connections.

**Fix:**
- Use an external connection pooler (PgBouncer, Neon pooler, Supabase pooler)
- Set `pool_size=1` and `max_overflow=2` in SQLAlchemy engine config
- Enable `pool_pre_ping=True` to discard stale connections

#### 6. `Internal Server Error` with no logs

**Cause:** Unhandled exception before logging middleware initializes.

**Fix:**
- Check Vercel Function Logs: **Dashboard → Deployments → Functions tab**
- Add a global exception handler:

```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import logging
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

#### 7. `File not found` for templates or static files

**Cause:** Relative paths break when CWD differs in serverless.

**Fix:** Always use absolute paths resolved from `__file__`:

```python
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
```

#### 8. Database migrations fail on deploy

**Cause:** Using pooled connection string for DDL operations.

**Fix:** Use the direct (non-pooled) connection string for Alembic:

```bash
DATABASE_URL_DIRECT=postgresql+asyncpg://user:pass@host:5432/talentflow alembic upgrade head
```

#### 9. `JWT decode error` or `401 Unauthorized` after deploy

**Cause:** `SECRET_KEY` differs between environments or was not set.

**Fix:**
- Verify the environment variable is set: `vercel env ls`
- Ensure the same `SECRET_KEY` is used across all instances
- After rotating keys, all existing tokens become invalid — users must re-authenticate

#### 10. Slow cold starts

**Cause:** Large dependency tree or heavy initialization.

**Fix:**
- Audit `requirements.txt` — remove unused packages
- Use lightweight alternatives where possible (e.g., `orjson` instead of default JSON)
- Move heavy initialization into lazy singletons
- Consider Vercel's **Fluid Compute** (if available) to reuse warm instances

---

## Production Checklist

- [ ] `SECRET_KEY` is a cryptographically random value (64+ hex characters)
- [ ] `ALLOWED_ORIGINS` is set to exact frontend domains (not `*`)
- [ ] `ENVIRONMENT` is set to `production`
- [ ] Database uses connection pooling
- [ ] Database migrations are run before deployment
- [ ] All `relationship()` declarations use `lazy="selectin"`
- [ ] Logging is configured (no `print()` statements)
- [ ] Passwords are hashed with bcrypt (never stored in plain text)
- [ ] HTTPS is enforced (Vercel handles this automatically)
- [ ] Error monitoring is configured (Sentry, LogRocket, or similar)
- [ ] Rate limiting is in place for authentication endpoints
- [ ] Sensitive environment variables are not logged or exposed in responses

---

## Useful Commands

```bash
# Check deployment status
vercel ls

# View function logs (real-time)
vercel logs --follow

# Rollback to previous deployment
vercel rollback

# List environment variables
vercel env ls

# Remove a deployment
vercel remove <deployment-url>

# Inspect build output
vercel inspect <deployment-url>
```