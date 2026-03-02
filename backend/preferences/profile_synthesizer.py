"""Profile synthesizer — periodically updates prose profile from tag weights and feedback."""

import json
import logging

import aiosqlite
from google import genai
from google.genai import types

from backend.config import settings
from backend.preferences.decay import apply_decay

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """\
Given the following user profile data from a news aggregator, write a concise 2-3 sentence \
description of the user's interests and preferences. Focus on what topics they care about most \
and what they want to avoid.

Tag weights (positive = likes, negative = dislikes):
{tag_weights}

Recent feedback (last 50 items):
{feedback_summary}

Write only the interest description, nothing else."""

MAX_RECENT_FEEDBACK = 50
FEEDBACK_RECENCY_DAYS = 7


async def synthesize_profile(db: aiosqlite.Connection) -> bool:
    """Run one synthesis cycle: decay weights, generate prose profile, bump version.

    Returns True if synthesis was performed.
    """
    rows = list(
        await db.execute_fetchall(
            "SELECT tag_weights_json, prose_profile, profile_version FROM user_profile WHERE id = 1"
        )
    )
    if not rows:
        return False

    tag_weights: dict[str, float] = json.loads(str(rows[0][0]))
    current_prose = str(rows[0][1])
    version = int(rows[0][2])

    if not tag_weights:
        logger.debug("No tag weights — skipping synthesis")
        return False

    # Apply decay
    decayed_weights = apply_decay(tag_weights)

    # Fetch recent feedback for context
    feedback_rows = await db.execute_fetchall(
        """
        SELECT a.title, f.rating
        FROM feedback f
        JOIN articles a ON f.article_id = a.id
        WHERE f.created_at >= datetime('now', ?)
        ORDER BY f.created_at DESC
        LIMIT ?
        """,
        (f"-{FEEDBACK_RECENCY_DAYS} days", MAX_RECENT_FEEDBACK),
    )
    feedback_lines: list[str] = []
    for row in feedback_rows:
        symbol = "+" if int(row[1]) == 1 else "-"
        feedback_lines.append(f"  {symbol} {row[0]}")
    feedback_summary = "\n".join(feedback_lines) if feedback_lines else "(no recent feedback)"

    # Build weights summary for the prompt
    sorted_weights = sorted(decayed_weights.items(), key=lambda x: abs(x[1]), reverse=True)[:20]
    weights_text = "\n".join(f"  {tag}: {w:+.2f}" for tag, w in sorted_weights)

    prompt = SYNTHESIS_PROMPT.format(tag_weights=weights_text, feedback_summary=feedback_summary)

    # Call Gemini to synthesize
    try:
        if not settings.gemini_api_key:
            logger.warning("Synthesis skipped: no Gemini API key")
            return False

        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=256,
            ),
        )
        new_prose = (response.text or "").strip()
        if not new_prose:
            logger.warning("Synthesis returned empty prose, keeping existing")
            new_prose = current_prose
    except Exception:
        logger.exception("Profile synthesis LLM call failed, keeping existing prose")
        new_prose = current_prose

    # Save decayed weights + new prose + bump version
    await db.execute(
        """
        UPDATE user_profile
        SET tag_weights_json = ?, prose_profile = ?,
            profile_version = ?, updated_at = datetime('now')
        WHERE id = 1
        """,
        (json.dumps(decayed_weights), new_prose, version + 1),
    )
    await db.commit()

    logger.info(
        "Profile synthesized (version %d → %d, %d weights after decay)",
        version,
        version + 1,
        len(decayed_weights),
    )
    return True
