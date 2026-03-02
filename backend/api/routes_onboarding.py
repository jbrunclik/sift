"""Cold-start onboarding endpoint — seeds initial profile from user interests."""

import json
import logging

from fastapi import APIRouter
from pydantic import BaseModel

from backend.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


class OnboardingRequest(BaseModel):
    interests: list[str]
    prose_profile: str = ""


class OnboardingResponse(BaseModel):
    profile_version: int
    tags_seeded: int


@router.post("")
async def onboard(req: OnboardingRequest) -> OnboardingResponse:
    """Seed initial profile from user-provided interests.

    Each interest is added as a tag weight at +1.0.
    Only works when profile_version == 0 (cold start).
    """
    db = await get_db()
    try:
        rows = list(
            await db.execute_fetchall(
                "SELECT profile_version, tag_weights_json FROM user_profile WHERE id = 1"
            )
        )
        if not rows:
            return OnboardingResponse(profile_version=0, tags_seeded=0)

        version = int(rows[0][0])
        if version > 0:
            # Already onboarded — return current state without changes
            return OnboardingResponse(profile_version=version, tags_seeded=0)

        # Seed weights at +1.0 per interest
        weights: dict[str, float] = {}
        for interest in req.interests:
            tag = interest.lower().strip()
            if tag:
                weights[tag] = 1.0

        interests_list = [i.strip() for i in req.interests if i.strip()]

        await db.execute(
            """
            UPDATE user_profile
            SET tag_weights_json = ?, interests_json = ?, prose_profile = ?,
                profile_version = 1, updated_at = datetime('now')
            WHERE id = 1
            """,
            (json.dumps(weights), json.dumps(interests_list), req.prose_profile),
        )
        await db.commit()

        return OnboardingResponse(profile_version=1, tags_seeded=len(weights))
    finally:
        await db.close()
