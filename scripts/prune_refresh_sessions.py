"""Delete expired refresh-token sessions (ADR-003 maintenance).

Run periodically (e.g. a cron job or systemd timer):

    python -m scripts.prune_refresh_sessions

Uses the application database role; refresh_sessions is not tenant-scoped.
"""
import asyncio

from app.core.db import SessionLocal, engine
from app.modules.auth.service import AuthService


async def main() -> None:
    async with SessionLocal() as session:
        deleted = await AuthService(session).prune_expired_refresh_sessions()
    await engine.dispose()
    print(f"Pruned {deleted} expired refresh session(s).")


if __name__ == "__main__":
    asyncio.run(main())
