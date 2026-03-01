import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/preferences", tags=["preferences"])


class PreferencesResponse(BaseModel):
    prose_profile: str
    interests: list[str]
    tag_weights: dict[str, float]
    profile_version: int
    summary_language: str = "en"


class PreferencesUpdate(BaseModel):
    prose_profile: str | None = None
    interests: list[str] | None = None
    summary_language: str | None = None


class TagWeightEntry(BaseModel):
    name: str
    weight: float


@router.get("")
async def get_preferences() -> PreferencesResponse:
    db = await get_db()
    try:
        rows = list(
            await db.execute_fetchall(
                "SELECT prose_profile, interests_json, tag_weights_json, profile_version,"
                " summary_language"
                " FROM user_profile WHERE id = 1"
            )
        )
        if not rows:
            return PreferencesResponse(
                prose_profile="", interests=[], tag_weights={}, profile_version=0
            )
        row = rows[0]
        return PreferencesResponse(
            prose_profile=str(row[0]),
            interests=json.loads(str(row[1])),
            tag_weights=json.loads(str(row[2])),
            profile_version=int(row[3]),
            summary_language=str(row[4] or "en"),
        )
    finally:
        await db.close()


@router.put("")
async def update_preferences(update: PreferencesUpdate) -> PreferencesResponse:
    db = await get_db()
    try:
        # Fetch current
        rows = list(
            await db.execute_fetchall(
                "SELECT prose_profile, interests_json, tag_weights_json, profile_version,"
                " summary_language"
                " FROM user_profile WHERE id = 1"
            )
        )
        row = rows[0]
        prose = str(row[0])
        interests: list[str] = json.loads(str(row[1]))
        tag_weights: dict[str, float] = json.loads(str(row[2]))
        version = int(row[3])
        summary_language = str(row[4] or "en")

        if update.prose_profile is not None:
            prose = update.prose_profile
        if update.interests is not None:
            interests = update.interests
        if update.summary_language is not None:
            summary_language = update.summary_language

        await db.execute(
            """
            UPDATE user_profile
            SET prose_profile = ?, interests_json = ?, summary_language = ?,
                profile_version = ?, updated_at = datetime('now')
            WHERE id = 1
            """,
            (prose, json.dumps(interests), summary_language, version + 1),
        )
        await db.commit()

        return PreferencesResponse(
            prose_profile=prose,
            interests=interests,
            tag_weights=tag_weights,
            profile_version=version + 1,
            summary_language=summary_language,
        )
    finally:
        await db.close()


@router.get("/tags")
async def get_tag_weights() -> list[TagWeightEntry]:
    db = await get_db()
    try:
        rows = list(
            await db.execute_fetchall("SELECT tag_weights_json FROM user_profile WHERE id = 1")
        )
        if not rows:
            return []
        weights: dict[str, float] = json.loads(str(rows[0][0]))
        sorted_tags = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        return [TagWeightEntry(name=name, weight=weight) for name, weight in sorted_tags]
    finally:
        await db.close()


@router.delete("/tags/{name}")
async def delete_tag_weight(name: str) -> dict[str, str]:
    db = await get_db()
    try:
        rows = list(
            await db.execute_fetchall(
                "SELECT tag_weights_json, profile_version FROM user_profile WHERE id = 1"
            )
        )
        row = rows[0]
        weights: dict[str, float] = json.loads(str(row[0]))
        version = int(row[1])

        if name not in weights:
            raise HTTPException(status_code=404, detail=f"Tag weight '{name}' not found")

        del weights[name]
        await db.execute(
            """
            UPDATE user_profile
            SET tag_weights_json = ?, profile_version = ?, updated_at = datetime('now')
            WHERE id = 1
            """,
            (json.dumps(weights), version + 1),
        )
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()
