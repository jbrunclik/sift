import json
import logging

from google import genai
from google.genai import types
from pydantic import BaseModel

from backend.config import settings

logger = logging.getLogger(__name__)

BATCH_SIZE = 5


class ScoringResult(BaseModel):
    relevance_score: float
    summary: str
    explanation: str
    tags: list[str]


class BatchScoringResponse(BaseModel):
    results: list[ScoringResult]


class ScoringError(Exception):
    def __init__(self, reason: str, batch_ids: list[int] | None = None) -> None:
        self.reason = reason
        self.batch_ids = batch_ids or []
        super().__init__(reason)


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
) -> list[ScoringResult]:
    """Score a batch of articles via Gemini, returning one ScoringResult per article."""
    try:
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=batch_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,
                max_output_tokens=2048,
                response_mime_type="application/json",
                response_schema=BatchScoringResponse,
            ),
        )
    except Exception as e:
        raise ScoringError(f"Gemini API error: {e}", batch_ids=article_ids) from e

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
            raise ScoringError(
                f"Failed to parse Gemini response: {e}", batch_ids=article_ids
            ) from e

    if len(results) != len(article_ids):
        raise ScoringError(
            f"Result count mismatch: got {len(results)}, expected {len(article_ids)}",
            batch_ids=article_ids,
        )

    # Normalize results
    for result in results:
        result.relevance_score = max(0.0, min(10.0, result.relevance_score))
        result.tags = [tag.lower().strip() for tag in result.tags]

    return results
