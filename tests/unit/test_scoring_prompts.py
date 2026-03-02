import json

from backend.scoring.prompts import (
    COLD_START_SYSTEM_PROMPT,
    MAX_CONTENT_CHARS,
    ArticlePromptData,
    build_batch_prompt,
    build_system_prompt,
)


class TestBuildSystemPrompt:
    def test_empty_profile_returns_cold_start(self) -> None:
        result = build_system_prompt("", "{}", "[]")
        assert result == COLD_START_SYSTEM_PROMPT

    def test_empty_strings_return_cold_start(self) -> None:
        result = build_system_prompt("", "", "")
        assert result == COLD_START_SYSTEM_PROMPT

    def test_full_profile_includes_all_parts(self) -> None:
        tag_weights = json.dumps({"python": 8.5, "rust": 7.0, "javascript": 3.0})
        interests = json.dumps(["machine learning", "systems programming"])
        prose = "I'm a backend engineer interested in distributed systems."

        result = build_system_prompt(prose, tag_weights, interests)

        assert "I'm a backend engineer" in result
        assert "machine learning, systems programming" in result
        assert "python" in result
        assert "rust" in result
        assert "javascript" in result
        assert "Strongly prefer" in result
        assert "relevance_score" in result

    def test_prose_only_does_not_fall_back(self) -> None:
        result = build_system_prompt("I like tech news", "{}", "[]")
        assert result != COLD_START_SYSTEM_PROMPT
        assert "I like tech news" in result

    def test_tag_weights_limited_to_top_15_positive(self) -> None:
        weights = {f"tag{i}": float(i) for i in range(25)}
        result = build_system_prompt("", json.dumps(weights), "[]")
        # Should include tag24 (highest) but not tag0 (zero, excluded)
        assert "tag24" in result
        assert "Strongly prefer" in result
        # tag0 = 0.0 is not positive, so excluded
        assert "tag0" not in result

    def test_negative_weights_in_seen_enough(self) -> None:
        weights = {"python": 5.0, "sports": -2.0, "gossip": -1.0}
        result = build_system_prompt("", json.dumps(weights), "[]")
        assert "Strongly prefer" in result
        assert "python" in result
        assert "Seen enough" in result
        assert "sports" in result
        assert "gossip" in result

    def test_language_instruction_added_for_non_english(self) -> None:
        result = build_system_prompt("I like tech", "{}", "[]", summary_language="cs")
        assert "Write all summaries in Czech" in result

    def test_no_language_instruction_for_english(self) -> None:
        result = build_system_prompt("I like tech", "{}", "[]", summary_language="en")
        assert "Write all summaries" not in result

    def test_language_instruction_cold_start(self) -> None:
        result = build_system_prompt("", "{}", "[]", summary_language="cs")
        assert "Write all summaries in Czech" in result
        assert COLD_START_SYSTEM_PROMPT in result

    def test_approved_tags_vocabulary_in_prompt(self) -> None:
        result = build_system_prompt(
            "I like tech", "{}", "[]", approved_tags=["ai", "python", "rust"]
        )
        assert "ai, python, rust" in result
        assert "Preferred tags:" in result
        assert "Do NOT force-fit" in result
        assert '"+' in result  # escape hatch instruction

    def test_approved_tags_in_cold_start(self) -> None:
        result = build_system_prompt("", "{}", "[]", approved_tags=["python", "rust"])
        assert "python, rust" in result
        assert "Preferred tags:" in result

    def test_no_vocabulary_when_empty_tags(self) -> None:
        result = build_system_prompt("I like tech", "{}", "[]", approved_tags=[])
        assert "Preferred tags:" not in result

    def test_vocabulary_before_user_profile(self) -> None:
        result = build_system_prompt(
            "I like tech", "{}", "[]", approved_tags=["python"]
        )
        vocab_pos = result.index("Tag Vocabulary")
        profile_pos = result.index("User Profile")
        assert vocab_pos < profile_pos


class TestBuildBatchPrompt:
    def _make_article(self, **overrides: object) -> ArticlePromptData:
        defaults = {
            "title": "Test Article",
            "source_name": "Test Source",
            "author": "Test Author",
            "published_at": "2024-01-01T12:00:00",
            "url": "https://example.com/article",
            "content": "This is the article content.",
        }
        defaults.update(overrides)
        return ArticlePromptData(**defaults)  # type: ignore[arg-type]

    def test_single_article_includes_all_fields(self) -> None:
        article = self._make_article()
        result = build_batch_prompt([article])

        assert "## Article 1" in result
        assert "Test Article" in result
        assert "Test Source" in result
        assert "Test Author" in result
        assert "2024-01-01T12:00:00" in result
        assert "https://example.com/article" in result
        assert "This is the article content." in result

    def test_none_author_and_published_at_omitted(self) -> None:
        article = self._make_article(author=None, published_at=None)
        result = build_batch_prompt([article])

        assert "**Author**" not in result
        assert "**Published**" not in result

    def test_content_truncated_at_limit(self) -> None:
        long_content = "x" * (MAX_CONTENT_CHARS + 500)
        article = self._make_article(content=long_content)
        result = build_batch_prompt([article])

        assert "..." in result
        # Content in result should be truncated
        assert "x" * (MAX_CONTENT_CHARS + 500) not in result

    def test_multiple_articles_numbered(self) -> None:
        articles = [
            self._make_article(title="First"),
            self._make_article(title="Second"),
            self._make_article(title="Third"),
        ]
        result = build_batch_prompt(articles)

        assert "## Article 1" in result
        assert "## Article 2" in result
        assert "## Article 3" in result
        assert "First" in result
        assert "Second" in result
        assert "Third" in result

    def test_empty_content_shows_placeholder(self) -> None:
        article = self._make_article(content="")
        result = build_batch_prompt([article])
        assert "(no content available)" in result


class TestTagConfidenceInPrompts:
    def test_cold_start_mentions_confidence(self) -> None:
        assert "confidence" in COLD_START_SYSTEM_PROMPT

    def test_personalized_prompt_mentions_confidence(self) -> None:
        result = build_system_prompt("I like tech", "{}", "[]")
        assert "confidence" in result
