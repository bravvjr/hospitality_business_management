#!/usr/bin/env bash
# Runs once on first DB init (as POSTGRES_USER on POSTGRES_DB). Creates the
# non-owner, non-superuser runtime role the API connects as, so PostgreSQL RLS
# is actually enforced (ADR-002). Migrations run as the owner (POSTGRES_USER);
# the app runs as this role.
set -euo pipefail

APP_ROLE="${APP_DB_ROLE:-hbm_app}"
APP_PASSWORD="${APP_DB_PASSWORD:-hbm_app}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${APP_ROLE}') THEN
        CREATE ROLE ${APP_ROLE} LOGIN PASSWORD '${APP_PASSWORD}' NOSUPERUSER NOBYPASSRLS;
    END IF;
END
\$\$;

GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${APP_ROLE};
GRANT USAGE ON SCHEMA public TO ${APP_ROLE};

-- Tables/sequences created later by the owner are auto-granted to the app role.
ALTER DEFAULT PRIVILEGES FOR ROLE ${POSTGRES_USER} IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${APP_ROLE};
ALTER DEFAULT PRIVILEGES FOR ROLE ${POSTGRES_USER} IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO ${APP_ROLE};
SQL
