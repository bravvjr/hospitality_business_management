"""Reports route dependencies (Phase 2c)."""
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.rate_limit import get_limiter
from app.modules.auth.deps import TenantContext
from app.modules.reports.permissions import REPORTS_READ
from app.modules.tenant.deps import require_module
from app.modules.tenant.entitlements import FINANCE


async def require_reports_export_reader(
    context: Annotated[TenantContext, Depends(require_module(FINANCE, REPORTS_READ))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TenantContext:
    """Require reports access and enforce per-user export rate limits."""
    if settings.rate_limit_enabled:
        key = f"rate_limit:reports:export:{context.tenant_id}:{context.user_id}"
        allowed = get_limiter().allow(
            key,
            max_requests=settings.reports_export_rate_limit_max,
            window_seconds=settings.reports_export_rate_limit_window_seconds,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many report exports, please slow down.",
                headers={
                    "Retry-After": str(settings.reports_export_rate_limit_window_seconds)
                },
            )
    return context


ReportsExportReader = Annotated[TenantContext, Depends(require_reports_export_reader)]
