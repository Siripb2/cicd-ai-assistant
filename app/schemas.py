"""
Pydantic schemas — the API's public contract. Validated automatically by
FastAPI on every request/response; never hand-roll validation logic.
"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.models import AnalysisStatus


class AnalyzeRequest(BaseModel):
    pipeline_name: str = Field(..., min_length=1, max_length=255)
    log: str = Field(..., min_length=1, description="Raw CI/CD log content")
    repository: str | None = Field(None, max_length=255)
    commit_sha: str | None = Field(None, max_length=64)
    org_id: str = Field("default", max_length=64)


class AnalyzeResponse(BaseModel):
    request_id: str
    status: AnalysisStatus
    root_cause: str | None = None
    affected_component: str | None = None
    fix_suggestion: str | None = None
    confidence_level: float | None = None
    low_confidence_warning: bool = False
    additional_context: str | None = None


class ReportOut(BaseModel):
    id: int
    request_id: str
    pipeline_name: str
    repository: str | None
    commit_sha: str | None
    status: AnalysisStatus
    root_cause: str | None
    fix_suggestion: str | None
    confidence_level: float | None
    created_at: datetime
    analyzed_at: datetime | None

    model_config = {"from_attributes": True}


class PaginatedReports(BaseModel):
    items: list[ReportOut]
    total: int
    page: int
    page_size: int


class HealthResponse(BaseModel):
    status: str = "ok"
    environment: str
