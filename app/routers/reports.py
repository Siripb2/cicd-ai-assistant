from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import verify_api_key
from app.database import get_db
from app.models import PipelineAnalysis
from app.schemas import PaginatedReports, ReportOut

router = APIRouter(tags=["reports"], dependencies=[Depends(verify_api_key)])


@router.get("/reports", response_model=PaginatedReports)
def list_reports(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
    pipeline_name: str | None = None,
    org_id: str | None = None,
) -> PaginatedReports:
    """Paginated history of all pipeline failure analyses, newest first."""
    stmt = select(PipelineAnalysis)
    if pipeline_name:
        stmt = stmt.where(PipelineAnalysis.pipeline_name == pipeline_name)
    if org_id:
        stmt = stmt.where(PipelineAnalysis.org_id == org_id)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = stmt.order_by(PipelineAnalysis.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(stmt).scalars().all()

    return PaginatedReports(
        items=[ReportOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: int, db: Session = Depends(get_db)) -> ReportOut:
    record = db.get(PipelineAnalysis, report_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportOut.model_validate(record)
