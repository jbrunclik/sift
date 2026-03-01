import logging

from fastapi import APIRouter, HTTPException

from backend.database import get_db
from backend.models import Feedback, FeedbackCreate
from backend.preferences.feedback_processor import process_feedback

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("")
async def create_feedback(feedback: FeedbackCreate) -> Feedback:
    db = await get_db()
    try:
        # Verify article exists
        article = await db.execute_fetchall(
            "SELECT id FROM articles WHERE id = ?", (feedback.article_id,)
        )
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        # Upsert feedback
        await db.execute(
            """
            INSERT INTO feedback (article_id, rating)
            VALUES (?, ?)
            ON CONFLICT (article_id) DO UPDATE SET
                rating = excluded.rating,
                created_at = datetime('now')
            """,
            (feedback.article_id, feedback.rating),
        )
        # Vote marks article as read
        if feedback.rating != 0:
            await db.execute(
                "UPDATE articles SET is_read = 1 WHERE id = ?",
                (feedback.article_id,),
            )
        await process_feedback(db, feedback.article_id, feedback.rating)
        await db.commit()

        rows = list(
            await db.execute_fetchall(
                "SELECT * FROM feedback WHERE article_id = ?", (feedback.article_id,)
            )
        )
        return Feedback(**dict(rows[0]))
    finally:
        await db.close()


@router.get("")
async def list_feedback(limit: int = 50) -> list[Feedback]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM feedback ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [Feedback(**dict(row)) for row in rows]
    finally:
        await db.close()
