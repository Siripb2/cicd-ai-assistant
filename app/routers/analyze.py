import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import verify_api_key
from app.database import get_db
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.services.analysis_service import is_low_confidence, run_analysis
from app.services.gemini_client import GeminiClient

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analysis"])

# A single GeminiClient instance is reused across requests (the underlying
# SDK client is safe for this; avoids re-initializing per-request).
_gemini_client = GeminiClient()


@router.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(verify_api_key)])
def analyze_failure(payload: AnalyzeRequest, db: Session = Depends(get_db)) -> AnalyzeResponse:
    """
    Ingest a CI/CD failure log, run LLM root-cause analysis, persist the
    result, and return it synchronously.

    Note on scaling: this endpoint is currently synchronous (the caller
    waits ~2-5s for the Gemini round trip). For high failure volume, this
    is the seam to swap for an async task queue — see README "Scaling to
    500+ concurrent failures" for the exact migration plan.
    """
    record = run_analysis(db, payload, _gemini_client)

    return AnalyzeResponse(
        request_id=record.request_id,
        status=record.status,
        root_cause=record.root_cause,
        affected_component=record.affected_component,
        fix_suggestion=record.fix_suggestion,
        confidence_level=record.confidence_level,
        low_confidence_warning=is_low_confidence(record.confidence_level),
    )
