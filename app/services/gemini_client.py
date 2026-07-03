"""
Thin wrapper around the Gemini SDK.

Isolating the SDK call behind this module means: (1) tests can monkeypatch
`GeminiClient.generate` instead of mocking the SDK directly, and (2) if we
ever swap providers (OpenAI, Anthropic, a self-hosted model for sensitive
environments — see README "Security"), only this file changes.
"""
import logging

import google.generativeai as genai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
)

from app.config import settings

logger = logging.getLogger(__name__)


class GeminiUnavailableError(Exception):
    """Raised when the provider call fails after all retries are exhausted."""


class GeminiClient:
    def __init__(self) -> None:
        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(settings.gemini_model)

    # Bug fixed: stop_after_attempt alone has no ceiling on *wall-clock*
    # time — if each individual attempt hangs close to its own
    # gemini_timeout_seconds, 3 attempts + backoff between them could take
    # 70+ seconds even though the per-call timeout is configured at 20s.
    # stop_after_delay caps total retry time regardless of attempt count, so
    # callers get a predictable worst-case latency instead of an unbounded hang.
    @retry(
        reraise=True,
        stop=(
            stop_after_attempt(settings.gemini_max_retries)
            | stop_after_delay(settings.gemini_max_total_wait_seconds)
        ),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def _call(self, prompt: str) -> str:
        response = self._model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=settings.gemini_temperature,
                max_output_tokens=settings.gemini_max_output_tokens,
            ),
            request_options={"timeout": settings.gemini_timeout_seconds},
        )
        if not response.text:
            raise ValueError("Empty response from Gemini")
        return response.text

    def generate(self, prompt: str) -> str:
        try:
            return self._call(prompt)
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini call failed after retries: %s", exc)
            raise GeminiUnavailableError(str(exc)) from exc