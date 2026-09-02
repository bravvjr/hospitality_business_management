"""Builds the versioned API router and mounts system + feature-module routers.

Feature modules are added here as they gain endpoints, e.g.:

    from app.modules.tenant import router as tenant_router
    api_router.include_router(tenant_router.router, prefix="/tenants")
"""
from fastapi import APIRouter

from app.api import system
from app.modules.auth.router import router as auth_router
from app.modules.inventory.router import router as inventory_router
from app.modules.pos.router import router as pos_router
from app.modules.tenant.router import router as tenant_router

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(tenant_router, prefix="/tenants", tags=["tenants"])
api_router.include_router(inventory_router, prefix="/inventory", tags=["inventory"])
api_router.include_router(pos_router, prefix="/pos", tags=["pos"])
