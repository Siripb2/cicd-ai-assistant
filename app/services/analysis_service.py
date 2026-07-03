"""
Orchestrates a single end-to-end analysis: build prompt -> call LLM -> parse
-> persist. Kept separate from the router so it's independently unit-testable
and reusable from a future async worker (see README "Scaling to 500+
concurrent failures").
"""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AnalysisStatus, PipelineAnalysis
from app.schemas import AnalyzeRequest
from app.services.gemini_client import GeminiClient, GeminiUnavailableError
from app.services.parser import parse_llm_response
from app.services.prompt_builder import build_prompt
from app.services.sanitizer import sanitize_log

logger = logging.getLogger(__name__)

# Below this confidence, the API surfaces a disclaimer to the caller so a
# human knows to double check before blindly applying the suggested fix.
LOW_CONFIDENCE_THRESHOLD = 0.5


def run_analysis(db: Session, request: AnalyzeRequest, gemini_client: GeminiClient) -> PipelineAnalysis:
    sanitized_log = sanitize_log(request.log)

    record = PipelineAnalysis(
        pipeline_name=request.pipeline_name,
        repository=request.repository,
        commit_sha=request.commit_sha,
        org_id=request.org_id,
        log_content=sanitized_log,
        status=AnalysisStatus.PENDING,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    prompt = build_prompt(sanitized_log, request.pipeline_name, settings.max_log_chars)

    try:
        raw_response = gemini_client.generate(prompt)
    except GeminiUnavailableError as exc:
        # Provider down/unreachable: don't crash the caller. Persist as FAILED
        # so it shows up in /reports for later retry, and return 202-style
        # semantics from the router rather than a 500.
        record.status = AnalysisStatus.FAILED
        record.error_message = str(exc)
        db.commit()
        logger.warning("Analysis %s failed: provider unavailable", record.request_id)
        return record

    parsed = parse_llm_response(raw_response)

    record.ai_analysis_raw = raw_response
    record.root_cause = parsed.root_cause
    record.affected_component = parsed.affected_component
    record.fix_suggestion = parsed.fix_suggestion
    record.confidence_level = parsed.confidence_level
    record.status = AnalysisStatus.ANALYZED
    record.analyzed_at = datetime.utcnow()

    if not parsed.parse_succeeded:
        # Don't fail the request — surface the degraded result with a note;
        # this is the fallback path described in README "LLM Reliability".
        record.error_message = "LLM response was not valid JSON; returned best-effort text."

    db.commit()
    db.refresh(record)
    return record


def is_low_confidence(confidence: float | None) -> bool:
    """None (unparsed) and low scores both count as 'flag for human review'."""
    return confidence is None or confidence < LOW_CONFIDENCE_THRESHOLD
