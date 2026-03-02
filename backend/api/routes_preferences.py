import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import get_db
from backend.preferences.tag_quality import get_noisy_tags
from backend.preferences.tag_vocabulary import (
    add_tag,
    get_candidates,
    merge_tags,
    remove_tag,
)

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


# --- Tag Vocabulary ---


class VocabularyTag(BaseModel):
    id: int
    name: str
    article_count: int


class VocabularyAddRequest(BaseModel):
    name: str


class VocabularyMergeRequest(BaseModel):
    source_id: int
    target_id: int


class CandidateTag(BaseModel):
    id: int
    name: str
    occurrences: int


@router.get("/vocabulary")
async def list_vocabulary() -> list[VocabularyTag]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT t.id, t.name, COUNT(at.article_id) as article_count
            FROM tags t
            LEFT JOIN article_tags at ON t.id = at.tag_id
            WHERE t.is_approved = 1
            GROUP BY t.id
            ORDER BY t.name
            """
        )
        return [
            VocabularyTag(id=int(r[0]), name=str(r[1]), article_count=int(r[2]))
            for r in rows
        ]
    finally:
        await db.close()


@router.post("/vocabulary")
async def add_vocabulary_tag(req: VocabularyAddRequest) -> VocabularyTag:
    db = await get_db()
    try:
        tag_id = await add_tag(db, req.name)
        await db.commit()
        # Fetch article count
        count_rows = list(
            await db.execute_fetchall(
                "SELECT COUNT(*) FROM article_tags WHERE tag_id = ?", (tag_id,)
            )
        )
        return VocabularyTag(
            id=tag_id,
            name=req.name.lower().strip(),
            article_count=int(count_rows[0][0]),
        )
    finally:
        await db.close()


@router.delete("/vocabulary/{tag_id}")
async def remove_vocabulary_tag(tag_id: int) -> dict[str, str]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT id FROM tags WHERE id = ?", (tag_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="Tag not found")
        await remove_tag(db, tag_id)
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


@router.post("/vocabulary/merge")
async def merge_vocabulary_tags(req: VocabularyMergeRequest) -> dict[str, str]:
    db = await get_db()
    try:
        # Verify both tags exist
        for tid in (req.source_id, req.target_id):
            rows = await db.execute_fetchall("SELECT id FROM tags WHERE id = ?", (tid,))
            if not rows:
                raise HTTPException(status_code=404, detail=f"Tag {tid} not found")
        if req.source_id == req.target_id:
            raise HTTPException(status_code=400, detail="Cannot merge a tag into itself")
        await merge_tags(db, req.source_id, req.target_id)
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


@router.get("/vocabulary/candidates")
async def list_candidates() -> list[CandidateTag]:
    db = await get_db()
    try:
        candidates = await get_candidates(db)
        return [
            CandidateTag(
                id=int(str(c["id"])),
                name=str(c["name"]),
                occurrences=int(str(c["occurrences"])),
            )
            for c in candidates
        ]
    finally:
        await db.close()


@router.post("/vocabulary/candidates/{tag_id}/approve")
async def approve_candidate(tag_id: int) -> dict[str, str]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT id FROM tags WHERE id = ? AND is_approved = 0", (tag_id,)
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Candidate tag not found")
        await db.execute("UPDATE tags SET is_approved = 1 WHERE id = ?", (tag_id,))
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


@router.delete("/vocabulary/candidates/{tag_id}")
async def reject_candidate(tag_id: int) -> dict[str, str]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT id FROM tags WHERE id = ? AND is_approved = 0", (tag_id,)
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Candidate tag not found")
        await db.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


# --- Tag Quality ---


class TagQualityEntry(BaseModel):
    tag_id: int
    name: str
    positive_votes: int
    negative_votes: int
    total_votes: int
    disagreement_ratio: float


@router.get("/vocabulary/quality")
async def get_vocabulary_quality() -> list[TagQualityEntry]:
    db = await get_db()
    try:
        noisy = await get_noisy_tags(db)
        return [
            TagQualityEntry(
                tag_id=t.tag_id,
                name=t.name,
                positive_votes=t.positive_votes,
                negative_votes=t.negative_votes,
                total_votes=t.total_votes,
                disagreement_ratio=t.disagreement_ratio,
            )
            for t in noisy
        ]
    finally:
        await db.close()
