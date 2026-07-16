"""
NewsScore model — News Engine (Phase Next, supporting engine — DEFERRED).

Placeholder/scaffold only: no external news/sentiment data source is wired
up in this phase (per the original Decision Engine brief, news/sentiment is
explicitly deferred). This engine always reports NEUTRAL with confidence 0
so the Decision Engine can already read a News row from day one and light up
automatically once a real news feed is connected later — no Decision Engine
changes will be required at that point.

One row per asset (or 'GLOBAL' for macro-only rows) — UPSERT on every cycle.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NewsScore(Base):
    __tablename__ = "news_scores"
    __table_args__ = (
        Index("ix_news_asset", "asset", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    asset: Mapped[str] = mapped_column(String(16), nullable=False)

    sentiment: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="POSITIVE | NEUTRAL | NEGATIVE",
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<NewsScore {self.asset} sentiment={self.sentiment}>"
