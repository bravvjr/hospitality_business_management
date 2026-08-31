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

```
app/
  main.py              # create_app() factory + lifespan
  core/
    config.py          # Pydantic settings (env-driven)
    db.py              # async engine, session factory, get_session dependency
  api/v1/
    router.py          # v1 router aggregation
    routes/health.py   # liveness + readiness endpoints
  models/              # SQLAlchemy models (Base, Tenant)
  schemas/             # Pydantic response models
alembic/               # async migrations (env.py + versions/)
scripts/entrypoint.sh  # migrate then launch (container entrypoint)
tests/                 # pytest (unit + integration)
Dockerfile
docker-compose.yml
```

## Run with Docker (recommended)

```bash
docker compose up --build
```

This starts PostgreSQL (persisted on a named volume) and the API. The API container
applies Alembic migrations on startup, then serves on http://localhost:8000.

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
