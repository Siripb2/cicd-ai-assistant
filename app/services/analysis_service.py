"""
Orchestrates a single end-to-end analysis: build prompt -> call LLM -> parse
-> persist. Kept separate from the router so it's independently unit-testable
and reusable from a future async worker (see README "Scaling to 500+
concurrent failures").
"""
import logging
import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AnalysisStatus, PipelineAnalysis
from app.schemas import AnalyzeRequest
from app.services.gemini_client import GeminiClient
from app.services.parser import ParsedAnalysis, parse_llm_response
from app.services.prompt_builder import build_prompt
from app.services.sanitizer import sanitize_log

logger = logging.getLogger(__name__)

# Below this confidence, the API surfaces a disclaimer to the caller so a
# human knows to double check before blindly applying the suggested fix.
LOW_CONFIDENCE_THRESHOLD = 0.5


def _build_fallback_analysis(log_text: str) -> ParsedAnalysis:
    lowered = log_text.lower()
    package_match = re.search(r"for ([a-zA-Z0-9_.-]+)", log_text)
    package_name = package_match.group(1) if package_match else None
    version_match = re.search(r"([a-zA-Z0-9_.-]+)==([0-9A-Za-z_.+-]+)", log_text)

    if "no matching distribution found" in lowered or "could not find a version that satisfies the requirement" in lowered:
        if package_name and version_match:
            requested_version = version_match.group(2)
            return ParsedAnalysis(
                root_cause=(
                    f"Dependency resolution failed while installing {package_name} {requested_version}. "
                    "The requested package version is likely invalid, unavailable, or not published for the current environment."
                ),
                affected_component="dependency resolution",
                fix_suggestion=(
                    f"Verify that {package_name} {requested_version} exists on the configured package index, "
                    "then pin to a valid version or update the dependency declaration."
                ),
                confidence_level=0.25,
                additional_context="Fallback analysis used because the AI provider was unavailable.",
                parse_succeeded=False,
            )

        return ParsedAnalysis(
            root_cause="Dependency resolution failed during package installation.",
            affected_component="dependency resolution",
            fix_suggestion="Inspect the package version pins and package index configuration, then retry the install with a valid version.",
            confidence_level=0.25,
            additional_context="Fallback analysis used because the AI provider was unavailable.",
            parse_succeeded=False,
        )

    return ParsedAnalysis(
        root_cause="The CI log could not be fully analyzed by the AI provider.",
        affected_component="pipeline failure",
        fix_suggestion="Review the raw CI log and rerun analysis once the provider is available.",
        confidence_level=0.2,
        additional_context="Fallback analysis used because the AI provider was unavailable.",
        parse_succeeded=False,
    )


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
    except Exception as exc:  # noqa: BLE001
        fallback = _build_fallback_analysis(sanitized_log)
        record.ai_analysis_raw = None
        record.root_cause = fallback.root_cause
        record.affected_component = fallback.affected_component
        record.fix_suggestion = fallback.fix_suggestion
        record.confidence_level = fallback.confidence_level
        record.status = AnalysisStatus.ANALYZED
        record.analyzed_at = datetime.utcnow()
        record.error_message = f"AI provider unavailable; used heuristic fallback analysis. Details: {exc}"
        db.commit()
        db.refresh(record)
        logger.warning("Analysis %s used fallback due to provider error: %s", record.request_id, exc)
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
