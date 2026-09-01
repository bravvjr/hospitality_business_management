"""Builds the versioned API router and mounts system + feature-module routers.

Feature modules are added here as they gain endpoints, e.g.:

    from app.modules.tenant import router as tenant_router
    api_router.include_router(tenant_router.router, prefix="/tenants")
"""
from fastapi import APIRouter

from app.api import system

api_router = APIRouter()
api_router.include_router(system.router)
