"""
Alert schemas — Phase 12: Monitoring / Alert / Operator Safety System.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class Alert(BaseModel):
    code: str
    severity: str  # INFO | WARNING | CRITICAL
    message: str
    evidence: dict[str, Any]
    recommended_action: str


class AlertSummaryCounts(BaseModel):
    critical: int
    warning: int
    info: int


class AlertSnapshot(BaseModel):
    status: str  # OK | WARNING | CRITICAL
    generated_at: datetime
    alerts: list[Alert]
    summary: AlertSummaryCounts
