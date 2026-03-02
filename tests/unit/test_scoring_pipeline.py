from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest

from backend.scoring.pipeline import run_scoring_pipeline
from backend.scoring.scorer import (
    BatchTooLargeError,
    ScoringBatchResult,
    ScoringError,
    ScoringResult,
    TagScore,
)

# Distinct titles that won't fuzzy-match each other (< 0.80 similarity)
DISTINCT_TITLES = [
    "Python Introduces New Pattern Matching Syntax",
    "Rust Memory Safety Guarantees Explained in Depth",
    "Kubernetes Cluster Autoscaling Best Practices Guide",
    "PostgreSQL Performance Tuning for High Traffic",
    "WebAssembly Runtime Reaches Production Stability",
    "Machine Learning Pipeline Orchestration with Airflow",
    "GraphQL Federation Architecture Design Patterns",
    "Distributed Consensus Algorithms Compared Thoroughly",
    "Zero Trust Security Model Implementation Steps",
    "Serverless Computing Cost Optimization Strategies",
    "React Server Components Deep Dive Tutorial",
    "Linux Kernel Scheduling Improvements Overview",
]


async def _insert_source(db: aiosqlite.Connection, name: str = "Test Source") -> int:
    cursor = await db.execute(
        "INSERT INTO sources (name, slug, source_type) VALUES (?, ?, 'rss')",
        (name, name.lower().replace(" ", "-")),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


async def _insert_article(
    db: aiosqlite.Connection,
    source_id: int,
    url: str = "https://example.com/article",
    title: str = "Test Article",
    content_full: str = "Article content here.",
) -> int:
    cursor = await db.execute(
        """
        INSERT INTO articles (source_id, url, url_normalized, title, content_full)
        VALUES (?, ?, ?, ?, ?)
        """,
        (source_id, url, url, title, content_full),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


def _make_result(
    score: float = 7.5, tags: list[TagScore] | None = None
) -> ScoringResult:
    return ScoringResult(
        relevance_score=score,
        summary="Test summary",
        explanation="Test explanation",
        tags=tags
        or [
            TagScore(name="python", confidence=0.9),
            TagScore(name="testing", confidence=0.8),
        ],
    )


def _patch_pipeline(db: aiosqlite.Connection) -> tuple[object, ...]:
    """Common patches for pipeline tests. Returns context managers."""
    return (
        patch("backend.scoring.pipeline.create_gemini_client"),
        patch("backend.scoring.pipeline.get_db", return_value=db),
        # Prevent pipeline from closing the test fixture's connection
        patch.object(db, "close", new_callable=AsyncMock),
    )


class TestRunScoringPipeline:
    @pytest.mark.asyncio
    async def test_full_flow(self, db: aiosqlite.Connection) -> None:
        source_id = await _insert_source(db)
        await _insert_article(
            db, source_id, url="https://a.com/1", title="Python Releases Major Update"
        )
        await _insert_article(
            db, source_id, url="https://b.com/2", title="Kubernetes Scaling Best Practices"
        )

        results = [
            _make_result(8.0, [TagScore(name="ai", confidence=0.95)]),
            _make_result(5.0, [TagScore(name="news", confidence=0.8)]),
        ]

        p_client, p_db, p_close = _patch_pipeline(db)
        with (
            p_client as mock_client,
            p_db,
            p_close,
            patch("backend.scoring.pipeline.score_batch", new_callable=AsyncMock) as mock_score,
        ):
            mock_client.return_value = MagicMock()
            mock_score.return_value = ScoringBatchResult(
                results=results, tokens_in=100, tokens_out=200
            )

            await run_scoring_pipeline()

        # Verify articles were scored
        rows = await db.execute_fetchall(
            "SELECT id, relevance_score, summary, scored_at FROM articles ORDER BY id"
        )
        assert len(rows) == 2
        assert float(rows[0]["relevance_score"]) == 8.0
        assert rows[0]["summary"] == "Test summary"
        assert rows[0]["scored_at"] is not None
        assert float(rows[1]["relevance_score"]) == 5.0

    @pytest.mark.asyncio
    async def test_skips_when_no_api_key(self, db: aiosqlite.Connection) -> None:
        with (
            patch(
                "backend.scoring.pipeline.create_gemini_client",
                side_effect=ValueError("No key"),
            ),
            patch("backend.scoring.pipeline.get_db", return_value=db) as mock_get_db,
        ):
            await run_scoring_pipeline()

        # get_db should NOT have been called since we bail early
        mock_get_db.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_unscored_articles(self, db: aiosqlite.Connection) -> None:
        p_client, p_db, p_close = _patch_pipeline(db)
        with (
            p_client as mock_client,
            p_db,
            p_close,
            patch("backend.scoring.pipeline.score_batch", new_callable=AsyncMock) as mock_score,
        ):
            mock_client.return_value = MagicMock()
            await run_scoring_pipeline()

        mock_score.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_batch_failure_marks_articles(self, db: aiosqlite.Connection) -> None:
        source_id = await _insert_source(db)
        art_id = await _insert_article(db, source_id)

        p_client, p_db, p_close = _patch_pipeline(db)
        with (
            p_client as mock_client,
            p_db,
            p_close,
            patch(
                "backend.scoring.pipeline.score_batch",
                new_callable=AsyncMock,
                side_effect=ScoringError("API error", batch_ids=[art_id]),
            ),
        ):
            mock_client.return_value = MagicMock()
            await run_scoring_pipeline()

        # Article should be marked as failed (-1.0) to prevent retries
        rows = await db.execute_fetchall(
            "SELECT relevance_score, scored_at FROM articles WHERE id = ?", (art_id,)
        )
        assert float(rows[0]["relevance_score"]) == -1.0
        assert rows[0]["scored_at"] is not None

    @pytest.mark.asyncio
    async def test_deduplication_same_url(self, db: aiosqlite.Connection) -> None:
        src1 = await _insert_source(db, "Source A")
        src2 = await _insert_source(db, "Source B")
        await _insert_article(db, src1, url="https://example.com/same", title="Same Article")
        await _insert_article(db, src2, url="https://example.com/same", title="Same Article")

        p_client, p_db, p_close = _patch_pipeline(db)
        with (
            p_client as mock_client,
            p_db,
            p_close,
            patch("backend.scoring.pipeline.score_batch", new_callable=AsyncMock) as mock_score,
        ):
            mock_client.return_value = MagicMock()
            # Only 1 result because dedup merges into 1 group
            mock_score.return_value = ScoringBatchResult(
                results=[_make_result(9.0)], tokens_in=50, tokens_out=100
            )

            await run_scoring_pipeline()

        # Both articles should have the same score
        rows = await db.execute_fetchall("SELECT relevance_score FROM articles ORDER BY id")
        assert len(rows) == 2
        assert float(rows[0]["relevance_score"]) == 9.0
        assert float(rows[1]["relevance_score"]) == 9.0
        # score_batch called once (1 group = 1 batch)
        mock_score.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_tags_stored(self, db: aiosqlite.Connection) -> None:
        source_id = await _insert_source(db)
        art_id = await _insert_article(db, source_id)

        p_client, p_db, p_close = _patch_pipeline(db)
        with (
            p_client as mock_client,
            p_db,
            p_close,
            patch("backend.scoring.pipeline.score_batch", new_callable=AsyncMock) as mock_score,
        ):
            mock_client.return_value = MagicMock()
            mock_score.return_value = ScoringBatchResult(
                results=[_make_result(7.0)],
                tokens_in=50,
                tokens_out=100,
            )

            await run_scoring_pipeline()

        # Check tags table
        tag_rows = await db.execute_fetchall("SELECT name FROM tags ORDER BY name")
        tag_names = [str(r["name"]) for r in tag_rows]
        assert "python" in tag_names
        assert "testing" in tag_names

        # Check article_tags
        at_rows = await db.execute_fetchall(
            "SELECT tag_id FROM article_tags WHERE article_id = ?", (art_id,)
        )
        assert len(at_rows) == 2

    @pytest.mark.asyncio
    async def test_tag_confidence_stored(self, db: aiosqlite.Connection) -> None:
        source_id = await _insert_source(db)
        art_id = await _insert_article(db, source_id)

        p_client, p_db, p_close = _patch_pipeline(db)
        with (
            p_client as mock_client,
            p_db,
            p_close,
            patch("backend.scoring.pipeline.score_batch", new_callable=AsyncMock) as mock_score,
        ):
            mock_client.return_value = MagicMock()
            mock_score.return_value = ScoringBatchResult(
                results=[
                    _make_result(
                        7.0,
                        [
                            TagScore(name="python", confidence=0.85),
                            TagScore(name="testing", confidence=0.6),
                        ],
                    )
                ],
                tokens_in=50,
                tokens_out=100,
            )

            await run_scoring_pipeline()

        # Check confidence values stored
        rows = await db.execute_fetchall(
            """
            SELECT t.name, at.confidence
            FROM article_tags at
            JOIN tags t ON at.tag_id = t.id
            WHERE at.article_id = ?
            ORDER BY t.name
            """,
            (art_id,),
        )
        assert len(rows) == 2
        confidences = {str(r["name"]): float(r["confidence"]) for r in rows}
        assert confidences["python"] == pytest.approx(0.85)
        assert confidences["testing"] == pytest.approx(0.6)

    @pytest.mark.asyncio
    async def test_batching_multiple_batches(self, db: aiosqlite.Connection) -> None:
        source_id = await _insert_source(db)
        for i in range(12):
            await _insert_article(
                db,
                source_id,
                url=f"https://example.com/{i}",
                title=DISTINCT_TITLES[i],
            )

        call_count = 0

        async def mock_score(
            client: object,
            system_prompt: str,
            batch_prompt: str,
            article_ids: list[int],
        ) -> ScoringBatchResult:
            nonlocal call_count
            call_count += 1
            return ScoringBatchResult(
                results=[_make_result(6.0) for _ in article_ids],
                tokens_in=50,
                tokens_out=100,
            )

        p_client, p_db, p_close = _patch_pipeline(db)
        with (
            p_client as mock_client,
            p_db,
            p_close,
            patch("backend.scoring.pipeline.score_batch", side_effect=mock_score),
        ):
            mock_client.return_value = MagicMock()
            await run_scoring_pipeline()

        # 12 articles / 5 per batch = 3 batches
        assert call_count == 3

        # All articles scored
        rows = await db.execute_fetchall(
            "SELECT COUNT(*) as cnt FROM articles WHERE relevance_score IS NOT NULL"
        )
        assert int(rows[0]["cnt"]) == 12

    @pytest.mark.asyncio
    async def test_batch_too_large_retries_individually(
        self, db: aiosqlite.Connection
    ) -> None:
        """When a batch hits MAX_TOKENS, the pipeline retries each article individually."""
        source_id = await _insert_source(db)
        await _insert_article(
            db, source_id, url="https://a.com/1", title="Python Releases Major Update"
        )
        await _insert_article(
            db,
            source_id,
            url="https://b.com/2",
            title="Kubernetes Scaling Best Practices",
        )

        call_count = 0

        async def mock_score(
            client: object,
            system_prompt: str,
            batch_prompt: str,
            article_ids: list[int],
        ) -> ScoringBatchResult:
            nonlocal call_count
            call_count += 1
            if len(article_ids) > 1:
                raise BatchTooLargeError(
                    "Gemini response truncated (finish_reason=MAX_TOKENS)",
                    batch_ids=article_ids,
                )
            return ScoringBatchResult(
                results=[_make_result(7.0)],
                tokens_in=50,
                tokens_out=100,
            )

        p_client, p_db, p_close = _patch_pipeline(db)
        with (
            p_client as mock_client,
            p_db,
            p_close,
            patch("backend.scoring.pipeline.score_batch", side_effect=mock_score),
        ):
            mock_client.return_value = MagicMock()
            await run_scoring_pipeline()

        # 1 batch call (fails) + 2 individual retries = 3 calls
        assert call_count == 3
        # Both articles should be scored successfully
        rows = await db.execute_fetchall(
            "SELECT relevance_score FROM articles ORDER BY id"
        )
        assert len(rows) == 2
        assert float(rows[0]["relevance_score"]) == 7.0
        assert float(rows[1]["relevance_score"]) == 7.0

    @pytest.mark.asyncio
    async def test_batch_too_large_single_article_fails(
        self, db: aiosqlite.Connection
    ) -> None:
        """A single article hitting MAX_TOKENS is marked as failed (cannot split further)."""
        source_id = await _insert_source(db)
        art_id = await _insert_article(db, source_id)

        p_client, p_db, p_close = _patch_pipeline(db)
        with (
            p_client as mock_client,
            p_db,
            p_close,
            patch(
                "backend.scoring.pipeline.score_batch",
                new_callable=AsyncMock,
                side_effect=BatchTooLargeError(
                    "Gemini response truncated", batch_ids=[art_id]
                ),
            ),
        ):
            mock_client.return_value = MagicMock()
            await run_scoring_pipeline()

        rows = await db.execute_fetchall(
            "SELECT relevance_score FROM articles WHERE id = ?", (art_id,)
        )
        assert float(rows[0]["relevance_score"]) == -1.0

    @pytest.mark.asyncio
    async def test_adjusted_score_stored(self, db: aiosqlite.Connection) -> None:
        """Score adjustment from tag weights should be applied and raw_llm_score preserved."""
        source_id = await _insert_source(db)
        await _insert_article(db, source_id)

        # Set up tag weights in user_profile
        import json

        await db.execute(
            "UPDATE user_profile SET tag_weights_json = ? WHERE id = 1",
            (json.dumps({"python": 3.0}),),
        )
        await db.commit()

        p_client, p_db, p_close = _patch_pipeline(db)
        with (
            p_client as mock_client,
            p_db,
            p_close,
            patch("backend.scoring.pipeline.score_batch", new_callable=AsyncMock) as mock_score,
        ):
            mock_client.return_value = MagicMock()
            mock_score.return_value = ScoringBatchResult(
                results=[
                    _make_result(
                        6.0,
                        [TagScore(name="python", confidence=1.0)],
                    )
                ],
                tokens_in=50,
                tokens_out=100,
            )

            await run_scoring_pipeline()

        rows = await db.execute_fetchall(
            "SELECT relevance_score, raw_llm_score FROM articles"
        )
        raw = float(rows[0]["raw_llm_score"])
        adjusted = float(rows[0]["relevance_score"])
        assert raw == 6.0
        # adjustment = 3.0 * 1.0 * 0.3 = 0.9
        assert adjusted == pytest.approx(6.9)
