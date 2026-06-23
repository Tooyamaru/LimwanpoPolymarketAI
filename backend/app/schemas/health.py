"""
Health response schemas.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float


class DetailedHealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    database: str
    redis: str
