# AGENTS.md

Orientation for AI agents (and humans) working in this repository. Read this first,
then follow the links into Notion for the authoritative product and architecture docs.

## What this project is

The **Hospitality Business Management Platform** — a multi-tenant SaaS that starts by
solving one hospitality/food business's inventory, sales (POS), expense and financial
tracking, and grows into an integrated, multi-business platform.

**Mission:** build a practical business management platform that solves the immediate
inventory, sales and financial tracking problems, then expand incrementally toward an
integrated hospitality platform and eventually a multi-business SaaS product.

## Source of truth: Notion

Product scope, architecture, roadmap, and **accepted** Architecture Decision Records live
in Notion. Read the relevant pages **before** implementing a feature:

- **Project Hub** — high-level product context: https://app.notion.com/p/3cd89b75501c81708b90c53049b516a9
- **Product Requirements & Functional Scope**: https://app.notion.com/p/3cd89b75501c81b3b92dca8d3253eedb
- **Architecture — Initial Direction**: https://app.notion.com/p/3cd89b75501c817e9abbeaf2da79277b
- **Development Roadmap & Agent Tasks** (phase checklists — **source of truth for progress**):
  https://app.notion.com/p/3cd89b75501c8114ad41cc437a8c1be2

## Current focus (backend)

**Phase 1 — Foundation.** Completed in this repo: project structure, Docker/local dev,
Postgres + migrations, health endpoints, GitHub Actions CI, JWT auth + tenant context.
**Next:** basic roles/permissions enforcement (`require_permission`), then inventory module.
Update the Notion roadmap when a checklist item is done — do not duplicate the full
checklist here.
- **Architecture Decision Records (ADRs)**: https://app.notion.com/p/3cd89b75501c814fa389e77472d40d03

## Repository scope

This is the **backend** repository (FastAPI); the project lives at the repo root. The
frontend (Next.js) is maintained in a **separate** repository (ADR-002 repository strategy).

- Backend repo: `https://github.com/bravvjr/hospitality_business_management`

## Tech stack (ADR-001)

- Python 3.14 · FastAPI · PostgreSQL
- Async SQLAlchemy 2.0 (asyncpg) · Alembic · Pydantic v2 / pydantic-settings
- Docker + Docker Compose for local development
- Frontend (separate repo): Next.js 16 · TypeScript · shadcn/ui · Tailwind

## Canonical terminology & key accepted decisions

Use these terms and honor these decisions (see the ADR page for full context):

- **tenant** is the canonical name for a SaaS account / business boundary (`tenant_id`).
  Tenants are hierarchical: a `tenants.parent_tenant_id` self-reference makes **sub-tenants**
  children of a parent (e.g. branches). RBAC inherits **downward** (ADR-002, ADR-012).
- **subproducts / modules** = platform capabilities (inventory, pos, finance, …), gated by
  entitlements — the app is a **modular monolith**, not per-module services. "Products" is
  reserved for **sellable items / menu items** (ADR-012).
- **Multi-tenancy:** shared database + shared schema, `tenant_id` on every tenant-scoped
  table, PostgreSQL **RLS** as defense-in-depth; tenant context only from a verified JWT
  claim (ADR-002).
- **Auth:** hand-rolled **JWT + RBAC**, tenant-scoped, data-driven roles/permissions (ADR-003).
- **Money:** integer **minor units + ISO-4217 currency** on every monetary row; never floats.
  Multi-currency from day one (ADR-004).
- **Inventory:** append-only `stock_movements` ledger + derived `stock_levels`; corrections
  are reversing entries. Units of measure use a base unit + per-product conversion factors
  with an immutable per-line UoM snapshot (ADR-005).
- **POS/payments:** one order/sale domain shared by POS and future online store; Cash +
  M-Pesa (Daraja). The async callback is the source of truth; credit idempotently (ADR-006).
- **API architecture:** FastAPI application-factory + lifespan; **package-by-feature**
  modules under `app/modules/<name>/`, each owning its `models`, `schemas`, `router`,
  `service`, and `repository` (layering lives inside the module). Ops endpoints (health)
  live in `app/api/system.py`. Versioned under `/api/v1` — a routing prefix, not a folder
  (ADR-008).

## Running & testing

See `README.md` for full instructions. Quick reference:

```bash
docker compose up --build          # API on :8000 (+ Postgres on :5432)
pytest                             # unit + integration (integration needs a database)
ruff check app tests alembic       # lint
alembic upgrade head               # apply migrations
```

## Working agreement for agents

From the roadmap "Agent Rules" and architecture guardrails:

1. Read the Project Hub and the relevant requirement/architecture/ADR pages first.
2. Confirm the task belongs to the current roadmap phase and is in scope.
3. Make the smallest coherent implementation; avoid building future-phase features early.
4. Add or update tests appropriate to the change.
5. Do **not** silently change architectural decisions. If a change introduces a significant
   decision, document it as a new ADR in Notion before proceeding.
6. Keep changes deployable, and keep the MVP usable throughout.
7. Enforce correct tenant scoping on every data path; never expose cross-tenant data.
8. Treat inventory and financial records as business-critical: ledgers are append-only,
   money is never stored as floats.
9. Update task status and record important, non-obvious implementation notes in Notion.

## Definition of Done

A feature is not done merely because the UI works. It should have: a working implementation,
appropriate validation, tests where applicable, correct business/tenant scoping, error
handling, no known critical regression, deployment compatibility, and documentation for
non-obvious decisions.
