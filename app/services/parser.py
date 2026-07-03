"""
Parses the Gemini response into structured fields.

LLM output is probabilistic, not deterministic — even with strong prompting,
the model occasionally returns markdown-fenced JSON, trailing commentary, or
(rarely) freeform text. This parser is defensive: it tries the strict path
first, then progressively degrades rather than raising, so a parsing hiccup
never bubbles up as a crash to the caller (GitHub Actions).
"""
import json
import re
from dataclasses import dataclass


@dataclass
class ParsedAnalysis:
    root_cause: str | None
    affected_component: str | None
    fix_suggestion: str | None
    confidence_level: float | None
    additional_context: str | None
    parse_succeeded: bool


_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")


def _strip_code_fences(text: str) -> str:
    match = _FENCE_RE.search(text)
    return match.group(1).strip() if match else text.strip()


def parse_llm_response(raw_text: str) -> ParsedAnalysis:
    candidate = _strip_code_fences(raw_text)

    # Try direct parse first, then fall back to extracting the first {...} block
    # in case the model added stray preamble/trailing text despite instructions.
    for attempt in (candidate, _extract_json_block(candidate)):
        if attempt is None:
            continue
        try:
            data = json.loads(attempt)
            return ParsedAnalysis(
                root_cause=data.get("root_cause"),
                affected_component=data.get("affected_component"),
                fix_suggestion=data.get("fix_suggestion"),
                confidence_level=_safe_float(data.get("confidence_level")),
                additional_context=data.get("additional_context"),
                parse_succeeded=True,
            )
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue

    # Total fallback: surface the raw text as the fix suggestion so the human
    # still gets *something* useful, with confidence explicitly set to None
    # (the API layer treats None confidence as "flag as low confidence").
    return ParsedAnalysis(
        root_cause=None,
        affected_component=None,
        fix_suggestion=raw_text.strip()[:2000] or None,
        confidence_level=None,
        additional_context="AI response could not be parsed as structured JSON; raw text shown.",
        parse_succeeded=False,
    )


def _extract_json_block(text: str) -> str | None:
    match = _JSON_OBJECT_RE.search(text)
    return match.group(0) if match else None


def _safe_float(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
