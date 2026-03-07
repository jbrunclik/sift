import asyncio
import json
import logging

from google import genai
from google.genai import types
from pydantic import BaseModel, model_validator

from backend.config import settings

logger = logging.getLogger(__name__)

BATCH_SIZE = 5
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds


class TagScore(BaseModel):
    name: str
    confidence: float = 1.0


class ScoringResult(BaseModel):
    relevance_score: float
    summary: str
    explanation: str
    tags: list[TagScore]

    @model_validator(mode="before")
    @classmethod
    def _coerce_tags(cls, data: object) -> object:
        """Handle Gemini returning flat strings instead of TagScore objects."""
        if isinstance(data, dict) and "tags" in data:
            raw_tags = data["tags"]
            if isinstance(raw_tags, list):
                coerced: list[object] = []
                for item in raw_tags:
                    if isinstance(item, str):
                        coerced.append({"name": item, "confidence": 1.0})
                    else:
                        coerced.append(item)
                data["tags"] = coerced
        return data


class BatchScoringResponse(BaseModel):
    results: list[ScoringResult]


class ScoringBatchResult(BaseModel):
    results: list[ScoringResult]
    tokens_in: int
    tokens_out: int


class ScoringError(Exception):
    def __init__(self, reason: str, batch_ids: list[int] | None = None) -> None:
        self.reason = reason
        self.batch_ids = batch_ids or []
        super().__init__(reason)


class BatchTooLargeError(ScoringError):
    """Raised when Gemini response is truncated (MAX_TOKENS), signaling split."""

    pass


def create_gemini_client() -> genai.Client:
    """Create a Gemini API client. Raises ValueError if API key is missing."""
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not configured")
    return genai.Client(api_key=settings.gemini_api_key)


async def score_batch(
    client: genai.Client,
    system_prompt: str,
    batch_prompt: str,
    article_ids: list[int],
) -> ScoringBatchResult:
    """Score a batch of articles via Gemini, returning results and token usage."""
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=batch_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                    max_output_tokens=8192,
                    response_mime_type="application/json",
                    response_schema=BatchScoringResponse,
                ),
            )
            break  # Success — exit retry loop
        except Exception as e:
            last_error = e
            error_str = str(e)
            is_retryable = "429" in error_str or "quota" in error_str.lower()
            if is_retryable and attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "Gemini API rate limited (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    delay,
                    error_str[:100],
                )
                await asyncio.sleep(delay)
                continue
            raise ScoringError(f"Gemini API error: {e}", batch_ids=article_ids) from e
    else:
        raise ScoringError(
            f"Gemini API error after {MAX_RETRIES} retries: {last_error}",
            batch_ids=article_ids,
        )

    # Extract token usage
    tokens_in = 0
    tokens_out = 0
    if response.usage_metadata:
        tokens_in = response.usage_metadata.prompt_token_count or 0
        tokens_out = response.usage_metadata.candidates_token_count or 0

    # Check finish reason — truncated responses produce invalid JSON
    finish_reason = None
    if response.candidates:
        finish_reason = response.candidates[0].finish_reason
    if finish_reason and str(finish_reason) not in ("STOP", "FinishReason.STOP"):
        finish_str = str(finish_reason)
        if "MAX_TOKENS" in finish_str:
            raise BatchTooLargeError(
                f"Gemini response truncated (finish_reason={finish_reason})",
                batch_ids=article_ids,
            )
        raise ScoringError(
            f"Gemini response truncated (finish_reason={finish_reason})",
            batch_ids=article_ids,
        )

    # Try structured parsed output first
    results: list[ScoringResult] | None = None

    if response.parsed is not None:
        parsed = response.parsed
        if isinstance(parsed, BatchScoringResponse):
            results = parsed.results

    # Fallback: parse from text
    if results is None:
        text = response.text
        if not text:
            raise ScoringError("Empty response from Gemini", batch_ids=article_ids)
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "results" in data:
                batch_resp = BatchScoringResponse.model_validate(data)
                results = batch_resp.results
            elif isinstance(data, list):
                results = [ScoringResult.model_validate(item) for item in data]
            else:
                raise ScoringError(
                    f"Unexpected JSON structure: {type(data)}", batch_ids=article_ids
                )
        except (json.JSONDecodeError, ValueError) as e:
            text_preview = text[:200] if text else "(empty)"
            raise ScoringError(
                f"Failed to parse Gemini response ({len(text)} chars, "
                f"finish={finish_reason}): {e}\nPreview: {text_preview}",
                batch_ids=article_ids,
            ) from e

    if len(results) != len(article_ids):
        raise ScoringError(
            f"Result count mismatch: got {len(results)}, expected {len(article_ids)}",
            batch_ids=article_ids,
        )

    # Normalize results (preserve '+' prefix for new-tag suggestions)
    for result in results:
        result.relevance_score = max(0.0, min(10.0, result.relevance_score))
        normalized_tags: list[TagScore] = []
        for tag_score in result.tags:
            stripped = tag_score.name.strip()
            if stripped.startswith("+"):
                name = "+" + stripped[1:].lower().strip()
            else:
                name = stripped.lower()
            confidence = max(0.0, min(1.0, tag_score.confidence))
            normalized_tags.append(TagScore(name=name, confidence=confidence))
        result.tags = normalized_tags

    return ScoringBatchResult(results=results, tokens_in=tokens_in, tokens_out=tokens_out)
