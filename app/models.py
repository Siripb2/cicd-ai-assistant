"""
ORM models.

Note: SQLAlchemy models (this file) are distinct from Pydantic schemas
(app/schemas.py). Models describe DB tables; schemas describe API
request/response shapes. Keeping them separate avoids leaking DB internals
(or accidentally exposing new DB columns) through the API.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnalysisStatus(str, enum.Enum):
    PENDING = "PENDING"
    ANALYZED = "ANALYZED"
    FAILED = "FAILED"


class PipelineAnalysis(Base):
    """One row per analyzed CI/CD pipeline failure."""

    __tablename__ = "pipeline_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )

    # --- Org / tenant scoping (multi-tenant ready, see README "Scaling") ---
    org_id: Mapped[str] = mapped_column(String(64), index=True, default="default")

    # --- Source context ---
    pipeline_name: Mapped[str] = mapped_column(String(255), index=True)
    repository: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- Payload / result ---
    log_content: Mapped[str] = mapped_column(Text)  # sanitized before storage
    ai_analysis_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_component: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fix_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_level: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
