"""Pydantic response schemas for health endpoints."""
from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    service: str
    environment: str


class ReadyStatus(BaseModel):
    status: str
    database: str
