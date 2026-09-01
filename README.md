# hospitality_business_management

Small hospitality and food businesses often face a common challenge: the business may be generating revenue, but the owner does not always have a clear, real-time picture of where the money is going, what stock is available, which products are profitable, or how the business is performing.

This repository is the **backend** for the Hospitality Business Management platform — a
multi-tenant SaaS built to grow from a single business into an integrated hospitality
platform. Product context, requirements, and the accepted Architecture Decision Records
(ADRs) live in the project's Notion hub. The frontend (Next.js) lives in a separate repository.

## Tech stack (ADR-001)

- Python 3.14 · FastAPI · PostgreSQL
- Async SQLAlchemy 2.0 (asyncpg) · Alembic
- Pydantic v2 / pydantic-settings
- Docker + Docker Compose for local development

## Project layout (ADR-008)

Package-by-feature (vertical slices): each module under `app/modules/` owns its own
models, schemas, router, service, and repository. Layering lives *inside* each module.
API versioning is a routing concern (`/api/v1`), not a folder.

```
app/
  main.py                  # create_app() factory + lifespan
  core/
    config.py              # Pydantic settings (env-driven)
    db.py                  # async engine, session factory, Base + mixins, get_session
  api/
    router.py              # builds the /api/v1 router; mounts system + module routers
    system.py              # liveness + readiness (ops endpoints, not a domain)
  modules/
    tenant/                # feature module
      models.py            # SQLAlchemy models
      schemas.py           # Pydantic schemas
      # router.py / service.py / repository.py added as the module gains behavior
alembic/                   # async migrations (env.py imports each module's models)
scripts/entrypoint.sh      # migrate then launch (container entrypoint)
tests/                     # pytest (unit + integration)
Dockerfile
docker-compose.yml
```

New modules (e.g. `auth`, `inventory`, `pos`, `finance`) are added as
`app/modules/<name>/`, mounted in `app/api/router.py`, and imported in `alembic/env.py`.

## Run with Docker (recommended)

```bash
docker compose up --build
```

This starts PostgreSQL (persisted on a named volume) and the API. The API container
applies Alembic migrations on startup, then serves on http://localhost:8000 with
**hot reload** — edits under `app/` are picked up automatically (no rebuild needed).

Rebuild the image only when `requirements.txt` or the `Dockerfile` changes:

```bash
docker compose up --build
```

- API docs: http://localhost:8000/docs
- Liveness: http://localhost:8000/api/v1/health/live
- Readiness (checks DB): http://localhost:8000/api/v1/health/ready

## Run without Docker

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env                 # adjust DATABASE_URL to your local Postgres
alembic upgrade head
uvicorn app.main:app --reload
```

## Migrations

```bash
alembic upgrade head                 # apply
alembic revision --autogenerate -m "message"   # create a new migration
alembic downgrade -1                 # roll back one
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest -m unit                       # fast, no database
pytest                               # full suite (integration needs a database)
```

Integration tests read `DATABASE_URL`; point it at a running Postgres before running them.
