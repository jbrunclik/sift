import json

import aiosqlite
import pytest

from backend.preferences.tag_vocabulary import (
    AUTO_PROMOTE_COUNT,
    add_tag,
    get_candidates,
    get_vocabulary,
    merge_tags,
    record_candidate,
    remove_tag,
    resolve_tag,
)


class TestResolveTag:
    def test_exact_match(self) -> None:
        vocab = ["python", "rust", "kubernetes"]
        name, is_candidate = resolve_tag("python", vocab)
        assert name == "python"
        assert is_candidate is False

    def test_exact_match_case_insensitive(self) -> None:
        vocab = ["python", "rust"]
        name, is_candidate = resolve_tag("Python", vocab)
        assert name == "python"
        assert is_candidate is False

    def test_fuzzy_match_above_threshold(self) -> None:
        vocab = ["machine-learning", "rust", "kubernetes"]
        name, is_candidate = resolve_tag("machine-learnin", vocab)
        assert name == "machine-learning"
        assert is_candidate is False

    def test_no_match_returns_candidate(self) -> None:
        vocab = ["python", "rust"]
        name, is_candidate = resolve_tag("quantum-computing", vocab)
        assert name == "quantum-computing"
        assert is_candidate is True

    def test_empty_vocabulary_returns_candidate(self) -> None:
        name, is_candidate = resolve_tag("python", [])
        assert name == "python"
        assert is_candidate is True

    def test_strips_whitespace(self) -> None:
        vocab = ["python"]
        name, is_candidate = resolve_tag("  python  ", vocab)
        assert name == "python"
        assert is_candidate is False

    def test_fuzzy_below_threshold_is_candidate(self) -> None:
        vocab = ["python"]
        name, is_candidate = resolve_tag("xyz", vocab)
        assert name == "xyz"
        assert is_candidate is True

    def test_picks_best_fuzzy_match(self) -> None:
        vocab = ["machine-learning", "machine-vision", "deep-learning"]
        # "machine-learnng" is closest to "machine-learning"
        name, is_candidate = resolve_tag("machine-learnng", vocab)
        assert name == "machine-learning"
        assert is_candidate is False


async def _setup_source_and_article(
    db: aiosqlite.Connection,
) -> tuple[int, int]:
    cursor = await db.execute(
        "INSERT INTO sources (name, slug, source_type) VALUES ('Test', 'test', 'rss')"
    )
    source_id = cursor.lastrowid
    cursor = await db.execute(
        "INSERT INTO articles (source_id, url, url_normalized, title)"
        " VALUES (?, 'https://a.com/1', 'https://a.com/1', 'Art 1')",
        (source_id,),
    )
    article_id = cursor.lastrowid
    await db.commit()
    return source_id, article_id  # type: ignore[return-value]


class TestGetVocabulary:
    @pytest.mark.asyncio
    async def test_returns_approved_tags(self, db: aiosqlite.Connection) -> None:
        await db.execute("INSERT INTO tags (name, is_approved) VALUES ('python', 1)")
        await db.execute("INSERT INTO tags (name, is_approved) VALUES ('draft-tag', 0)")
        await db.commit()

        vocab = await get_vocabulary(db)
        assert "python" in vocab
        assert "draft-tag" not in vocab

    @pytest.mark.asyncio
    async def test_empty_when_no_approved(self, db: aiosqlite.Connection) -> None:
        assert await get_vocabulary(db) == []


class TestRecordCandidate:
    @pytest.mark.asyncio
    async def test_records_candidate(self, db: aiosqlite.Connection) -> None:
        _, article_id = await _setup_source_and_article(db)
        promoted = await record_candidate(db, "new-tag", article_id)
        await db.commit()

        assert promoted is False
        rows = await db.execute_fetchall("SELECT * FROM tag_candidates")
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_auto_promotes_at_threshold(self, db: aiosqlite.Connection) -> None:
        source_id, _ = await _setup_source_and_article(db)

        # Create enough articles to hit the threshold
        article_ids = []
        for i in range(AUTO_PROMOTE_COUNT):
            cursor = await db.execute(
                "INSERT INTO articles (source_id, url, url_normalized, title)"
                f" VALUES (?, 'https://a.com/{i+10}', 'https://a.com/{i+10}', 'Art {i+10}')",
                (source_id,),
            )
            article_ids.append(cursor.lastrowid)
        await db.commit()

        promoted = False
        for aid in article_ids:
            promoted = await record_candidate(db, "new-topic", aid)
        await db.commit()

        assert promoted is True

        # Tag should now be approved
        rows = await db.execute_fetchall(
            "SELECT is_approved FROM tags WHERE name = 'new-topic'"
        )
        assert int(rows[0][0]) == 1

    @pytest.mark.asyncio
    async def test_idempotent_insert(self, db: aiosqlite.Connection) -> None:
        _, article_id = await _setup_source_and_article(db)
        await record_candidate(db, "tag-x", article_id)
        await record_candidate(db, "tag-x", article_id)
        await db.commit()

        rows = await db.execute_fetchall("SELECT * FROM tag_candidates")
        assert len(rows) == 1


class TestMergeTags:
    @pytest.mark.asyncio
    async def test_repoints_article_tags(self, db: aiosqlite.Connection) -> None:
        _, article_id = await _setup_source_and_article(db)

        await db.execute("INSERT INTO tags (name, is_approved) VALUES ('ml', 1)")
        await db.execute(
            "INSERT INTO tags (name, is_approved) VALUES ('machine-learning', 1)"
        )
        await db.commit()

        ml_rows = await db.execute_fetchall("SELECT id FROM tags WHERE name = 'ml'")
        target_rows = await db.execute_fetchall(
            "SELECT id FROM tags WHERE name = 'machine-learning'"
        )
        source_id = int(ml_rows[0][0])
        target_id = int(target_rows[0][0])

        await db.execute(
            "INSERT INTO article_tags (article_id, tag_id) VALUES (?, ?)",
            (article_id, source_id),
        )
        await db.commit()

        await merge_tags(db, source_id, target_id)
        await db.commit()

        # Source tag should be deleted
        rows = await db.execute_fetchall("SELECT id FROM tags WHERE name = 'ml'")
        assert len(rows) == 0

        # Article should now point to target
        at_rows = await db.execute_fetchall(
            "SELECT tag_id FROM article_tags WHERE article_id = ?", (article_id,)
        )
        assert len(at_rows) == 1
        assert int(at_rows[0][0]) == target_id

    @pytest.mark.asyncio
    async def test_transfers_weight(self, db: aiosqlite.Connection) -> None:
        await db.execute("INSERT INTO tags (name, is_approved) VALUES ('ml', 1)")
        await db.execute(
            "INSERT INTO tags (name, is_approved) VALUES ('machine-learning', 1)"
        )
        await db.commit()

        ml_rows = await db.execute_fetchall("SELECT id FROM tags WHERE name = 'ml'")
        target_rows = await db.execute_fetchall(
            "SELECT id FROM tags WHERE name = 'machine-learning'"
        )
        source_id = int(ml_rows[0][0])
        target_id = int(target_rows[0][0])

        # Set up weights
        weights = {"ml": 2.5, "machine-learning": 1.0, "python": 3.0}
        await db.execute(
            "UPDATE user_profile SET tag_weights_json = ? WHERE id = 1",
            (json.dumps(weights),),
        )
        await db.commit()

        await merge_tags(db, source_id, target_id)
        await db.commit()

        rows = await db.execute_fetchall(
            "SELECT tag_weights_json FROM user_profile WHERE id = 1"
        )
        new_weights = json.loads(str(rows[0][0]))
        assert "ml" not in new_weights
        assert new_weights["machine-learning"] == 3.5  # 1.0 + 2.5
        assert new_weights["python"] == 3.0

    @pytest.mark.asyncio
    async def test_handles_duplicate_article_tags(
        self, db: aiosqlite.Connection
    ) -> None:
        _, article_id = await _setup_source_and_article(db)

        await db.execute("INSERT INTO tags (name, is_approved) VALUES ('ml', 1)")
        await db.execute(
            "INSERT INTO tags (name, is_approved) VALUES ('machine-learning', 1)"
        )
        await db.commit()

        ml_rows = await db.execute_fetchall("SELECT id FROM tags WHERE name = 'ml'")
        target_rows = await db.execute_fetchall(
            "SELECT id FROM tags WHERE name = 'machine-learning'"
        )
        source_id = int(ml_rows[0][0])
        target_id = int(target_rows[0][0])

        # Article has both tags
        await db.execute(
            "INSERT INTO article_tags (article_id, tag_id) VALUES (?, ?)",
            (article_id, source_id),
        )
        await db.execute(
            "INSERT INTO article_tags (article_id, tag_id) VALUES (?, ?)",
            (article_id, target_id),
        )
        await db.commit()

        # Should not raise
        await merge_tags(db, source_id, target_id)
        await db.commit()

        at_rows = await db.execute_fetchall(
            "SELECT tag_id FROM article_tags WHERE article_id = ?", (article_id,)
        )
        assert len(at_rows) == 1
        assert int(at_rows[0][0]) == target_id


class TestAddRemoveTag:
    @pytest.mark.asyncio
    async def test_add_new_tag(self, db: aiosqlite.Connection) -> None:
        tag_id = await add_tag(db, "New Tag")
        await db.commit()

        rows = await db.execute_fetchall(
            "SELECT name, is_approved FROM tags WHERE id = ?", (tag_id,)
        )
        assert str(rows[0][0]) == "new tag"
        assert int(rows[0][1]) == 1

    @pytest.mark.asyncio
    async def test_add_promotes_existing_unapproved(
        self, db: aiosqlite.Connection
    ) -> None:
        await db.execute("INSERT INTO tags (name, is_approved) VALUES ('draft', 0)")
        await db.commit()

        tag_id = await add_tag(db, "draft")
        await db.commit()

        rows = await db.execute_fetchall(
            "SELECT is_approved FROM tags WHERE id = ?", (tag_id,)
        )
        assert int(rows[0][0]) == 1

    @pytest.mark.asyncio
    async def test_remove_tag(self, db: aiosqlite.Connection) -> None:
        await db.execute("INSERT INTO tags (name, is_approved) VALUES ('remove-me', 1)")
        await db.commit()
        rows = await db.execute_fetchall("SELECT id FROM tags WHERE name = 'remove-me'")
        tag_id = int(rows[0][0])

        await remove_tag(db, tag_id)
        await db.commit()

        rows = await db.execute_fetchall(
            "SELECT is_approved FROM tags WHERE id = ?", (tag_id,)
        )
        assert int(rows[0][0]) == 0


class TestGetCandidates:
    @pytest.mark.asyncio
    async def test_returns_unapproved_with_occurrences(
        self, db: aiosqlite.Connection
    ) -> None:
        _, article_id = await _setup_source_and_article(db)
        await db.execute("INSERT INTO tags (name, is_approved) VALUES ('candidate-a', 0)")
        await db.commit()

        rows = await db.execute_fetchall("SELECT id FROM tags WHERE name = 'candidate-a'")
        tag_id = int(rows[0][0])

        await db.execute(
            "INSERT INTO tag_candidates (tag_id, article_id) VALUES (?, ?)",
            (tag_id, article_id),
        )
        await db.commit()

        candidates = await get_candidates(db)
        assert len(candidates) == 1
        assert candidates[0]["name"] == "candidate-a"
        assert candidates[0]["occurrences"] == 1

    @pytest.mark.asyncio
    async def test_excludes_approved_tags(self, db: aiosqlite.Connection) -> None:
        await db.execute("INSERT INTO tags (name, is_approved) VALUES ('approved', 1)")
        await db.commit()

        candidates = await get_candidates(db)
        assert len(candidates) == 0
