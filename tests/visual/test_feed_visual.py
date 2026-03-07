"""Visual regression tests for Sift.

Run with only the Vite frontend dev server active:
  cd frontend && npm run dev
  uv run pytest tests/visual/ -v

For visible browser:
  uv run pytest tests/visual/ --headed -v
"""

from pathlib import Path

import pytest
from playwright.async_api import Page

from tests.visual.mock_data import MockState

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


# ── Feed page ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_feed_page_loads(page: Page, base_url: str, mock_api: MockState) -> None:
    """Feed page renders with nav bar, toolbar, and article cards."""
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".nav-bar")
    await page.wait_for_selector(".feed-toolbar")
    await page.wait_for_selector(".article-card", timeout=5000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "feed.png"), full_page=True)


@pytest.mark.asyncio
async def test_feed_training_mode(page: Page, base_url: str, mock_api: MockState) -> None:
    """Training mode toggle activates and shows all-score articles."""
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".btn-training")
    await page.click(".btn-training")
    btn = page.locator(".btn-training")
    assert "active" in (await btn.get_attribute("class") or "")
    await page.wait_for_selector(".article-card", timeout=5000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "feed-training.png"), full_page=True)
    await page.click(".btn-training")


@pytest.mark.asyncio
async def test_feed_article_card_hover(page: Page, base_url: str, mock_api: MockState) -> None:
    """Article card shows action buttons on hover."""
    await page.goto(f"{base_url}/#/feed")
    card = page.locator(".article-card").first
    await card.wait_for(timeout=5000)
    await card.hover()
    actions = card.locator(".card-actions")
    await actions.wait_for(state="visible", timeout=2000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "feed-card-hover.png"))


@pytest.mark.asyncio
async def test_feed_card_action_order(page: Page, base_url: str, mock_api: MockState) -> None:
    """Card actions: up, read-toggle, down, spacer, then secondary."""
    await page.goto(f"{base_url}/#/feed")
    card = page.locator(".article-card").first
    await card.wait_for(timeout=5000)
    await card.hover()
    actions = card.locator(".card-actions")
    buttons = actions.locator("button.btn-feedback")
    count = await buttons.count()
    if count >= 3:
        classes = []
        for i in range(count):
            cls = await buttons.nth(i).get_attribute("class") or ""
            classes.append(cls)
        assert "btn-up" in classes[0]
        assert "btn-read-toggle" in classes[1]
        assert "btn-down" in classes[2]


@pytest.mark.asyncio
async def test_feed_card_actions_always_subtly_visible(page: Page, base_url: str, mock_api: MockState) -> None:
    """Card actions are subtly visible (opacity > 0) even without hover."""
    await page.goto(f"{base_url}/#/feed")
    card = page.locator(".article-card").first
    await card.wait_for(timeout=5000)
    # Without hover, actions should have opacity > 0 (subtly visible)
    actions = card.locator(".card-actions")
    opacity = await actions.evaluate("el => getComputedStyle(el).opacity")
    assert float(opacity) > 0
    await page.screenshot(path=str(SCREENSHOT_DIR / "feed-card-actions-subtle.png"))


@pytest.mark.asyncio
async def test_feed_keyboard_navigation(page: Page, base_url: str, mock_api: MockState) -> None:
    """j/k keyboard shortcuts navigate between cards."""
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".article-card", timeout=5000)
    await page.keyboard.press("j")
    focused = page.locator(".article-card.focused")
    await focused.wait_for(timeout=2000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "feed-keyboard-focus.png"))


@pytest.mark.asyncio
async def test_feed_search(page: Page, base_url: str, mock_api: MockState) -> None:
    """Search input filters the feed."""
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".search-input")
    await page.fill(".search-input", "test query")
    await page.wait_for_timeout(500)
    await page.screenshot(path=str(SCREENSHOT_DIR / "feed-search.png"), full_page=True)


@pytest.mark.asyncio
async def test_feed_source_filter(page: Page, base_url: str, mock_api: MockState) -> None:
    """Source filter dropdown is rendered."""
    await page.goto(f"{base_url}/#/feed")
    select = page.locator(".filter-source")
    await select.wait_for(timeout=5000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "feed-source-filter.png"))


# ── Keyboard Help ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_keyboard_help_overlay(page: Page, base_url: str, mock_api: MockState) -> None:
    """? key opens the help overlay with all shortcuts."""
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".feed-toolbar")
    await page.keyboard.press("?")
    overlay = page.locator(".help-overlay")
    await overlay.wait_for(timeout=2000)
    rows = page.locator(".help-row")
    assert await rows.count() >= 6
    await page.screenshot(path=str(SCREENSHOT_DIR / "keyboard-help.png"))
    await page.keyboard.press("Escape")
    await overlay.wait_for(state="hidden", timeout=2000)


# ── Stats page ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stats_page_overview(page: Page, base_url: str, mock_api: MockState) -> None:
    """Stats page renders overview cards and all sections."""
    await page.goto(f"{base_url}/#/stats")
    await page.wait_for_selector(".stats-section")
    grid = page.locator(".stats-grid")
    await grid.wait_for(timeout=5000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "stats.png"), full_page=True)


@pytest.mark.asyncio
async def test_stats_score_distribution(page: Page, base_url: str, mock_api: MockState) -> None:
    """Stats page shows the SVG score distribution chart."""
    await page.goto(f"{base_url}/#/stats")
    chart = page.locator(".score-chart")
    await chart.wait_for(timeout=5000)
    await chart.screenshot(path=str(SCREENSHOT_DIR / "stats-score-chart.png"))


@pytest.mark.asyncio
async def test_stats_job_table_with_run_buttons(page: Page, base_url: str, mock_api: MockState) -> None:
    """Stats page shows background jobs table with Run buttons in each row."""
    await page.goto(f"{base_url}/#/stats")
    await page.wait_for_selector(".stats-section", timeout=5000)
    buttons = page.locator(".btn-trigger")
    assert await buttons.count() == 3
    # Each Run button should have an SVG icon
    for i in range(3):
        svg = buttons.nth(i).locator("svg")
        assert await svg.count() >= 1
    await page.screenshot(path=str(SCREENSHOT_DIR / "stats-job-table.png"), full_page=True)


@pytest.mark.asyncio
async def test_stats_issues_banner(page: Page, base_url: str, mock_api: MockState) -> None:
    """Stats page shows issues banner when errors exist."""
    await page.goto(f"{base_url}/#/stats")
    await page.wait_for_selector(".stats-section", timeout=5000)
    banner = page.locator(".issues-banner")
    await banner.wait_for(timeout=3000)
    await banner.screenshot(path=str(SCREENSHOT_DIR / "stats-issues-banner.png"))


@pytest.mark.asyncio
async def test_stats_scoring_failures_table(page: Page, base_url: str, mock_api: MockState) -> None:
    """Stats page shows detailed scoring failures table."""
    await page.goto(f"{base_url}/#/stats")
    await page.wait_for_selector(".stats-section", timeout=5000)
    failures_table = page.locator(".issues-table").first
    await failures_table.wait_for(timeout=5000)
    # Should have article title, source, attempts, error columns
    headers = failures_table.locator("th")
    assert await headers.count() >= 4
    rows = failures_table.locator("tbody tr")
    assert await rows.count() >= 1
    # Take a screenshot of just the issues section
    issues_section = page.locator(".issues-section")
    await issues_section.screenshot(path=str(SCREENSHOT_DIR / "stats-scoring-failures.png"))


@pytest.mark.asyncio
async def test_stats_source_health_table(page: Page, base_url: str, mock_api: MockState) -> None:
    """Stats page shows source health table."""
    await page.goto(f"{base_url}/#/stats")
    await page.wait_for_selector(".stats-section")
    tables = page.locator(".stats-table")
    await tables.first.wait_for(timeout=5000)
    await tables.first.screenshot(path=str(SCREENSHOT_DIR / "stats-source-health.png"))


@pytest.mark.asyncio
async def test_stats_tag_cloud(page: Page, base_url: str, mock_api: MockState) -> None:
    """Stats page renders the tag cloud."""
    await page.goto(f"{base_url}/#/stats")
    cloud = page.locator(".tag-cloud")
    await cloud.wait_for(timeout=5000)
    await cloud.screenshot(path=str(SCREENSHOT_DIR / "stats-tag-cloud.png"))


# ── Preferences page ──────────────────────────────────────


@pytest.mark.asyncio
async def test_preferences_page_sections(page: Page, base_url: str, mock_api: MockState) -> None:
    """Preferences page renders sections: language, profile, interests."""
    await page.goto(f"{base_url}/#/preferences")
    sections = page.locator(".prefs-section")
    await sections.first.wait_for(timeout=5000)
    count = await sections.count()
    assert count >= 3
    await page.screenshot(path=str(SCREENSHOT_DIR / "preferences.png"), full_page=True)


@pytest.mark.asyncio
async def test_preferences_language_pills_with_flags(page: Page, base_url: str, mock_api: MockState) -> None:
    """Language pills show flag emojis and one is active."""
    await page.goto(f"{base_url}/#/preferences")
    pills = page.locator(".language-pills .btn-pill")
    await pills.first.wait_for(timeout=5000)
    count = await pills.count()
    assert count >= 2
    active = page.locator(".language-pills .btn-pill.active")
    assert await active.count() >= 1
    await page.screenshot(path=str(SCREENSHOT_DIR / "preferences-language.png"))


@pytest.mark.asyncio
async def test_preferences_save_buttons_have_icons(page: Page, base_url: str, mock_api: MockState) -> None:
    """Save buttons on preferences page have SVG icons."""
    await page.goto(f"{base_url}/#/preferences")
    save_btns = page.locator(".btn-icon-text")
    await save_btns.first.wait_for(timeout=5000)
    # Should have at least 2 save buttons (profile + interests)
    assert await save_btns.count() >= 2
    # Each should contain an SVG
    for i in range(await save_btns.count()):
        svg = save_btns.nth(i).locator("svg")
        assert await svg.count() >= 1
    await page.screenshot(path=str(SCREENSHOT_DIR / "preferences-save-icons.png"), full_page=True)


# ── Tags page ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tags_page_loads(page: Page, base_url: str, mock_api: MockState) -> None:
    """Tags page renders with vocabulary section and add input."""
    await page.goto(f"{base_url}/#/tags")
    await page.wait_for_selector(".prefs-section", timeout=5000)
    add_row = page.locator(".vocab-add-row")
    await add_row.wait_for(timeout=5000)
    add_input = page.locator(".vocab-add-input")
    assert await add_input.count() == 1
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "tags-page.png"), full_page=True
    )


@pytest.mark.asyncio
async def test_tags_add_row_alignment(page: Page, base_url: str, mock_api: MockState) -> None:
    """Add tag input and button should have matching heights."""
    await page.goto(f"{base_url}/#/tags")
    add_row = page.locator(".vocab-add-row")
    await add_row.wait_for(timeout=5000)
    input_box = await add_row.locator("input").bounding_box()
    btn_box = await add_row.locator("button").bounding_box()
    if input_box and btn_box:
        # Heights should be within 2px of each other
        assert abs(input_box["height"] - btn_box["height"]) <= 2, (
            f"Input height {input_box['height']}px != button height {btn_box['height']}px"
        )
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "tags-add-alignment.png"),
        clip=await add_row.bounding_box() or None,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_tags_vocabulary_pills(page: Page, base_url: str, mock_api: MockState) -> None:
    """Tags page shows approved tags as pill chips with remove buttons."""
    await page.goto(f"{base_url}/#/tags")
    pills = page.locator(".vocab-pill")
    await pills.first.wait_for(timeout=5000)
    count = await pills.count()
    assert count >= 1
    remove_btns = page.locator(".vocab-pill-x")
    assert await remove_btns.count() >= 1
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "tags-vocabulary-pills.png"), full_page=True
    )


@pytest.mark.asyncio
async def test_tags_merge_section(page: Page, base_url: str, mock_api: MockState) -> None:
    """Tags page shows merge section with source/target dropdowns."""
    await page.goto(f"{base_url}/#/tags")
    merge = page.locator(".vocab-merge-row")
    await merge.wait_for(timeout=5000)
    selects = merge.locator("select")
    assert await selects.count() == 2
    merge_btn = merge.locator("button")
    assert await merge_btn.count() >= 1
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "tags-merge.png"), full_page=True
    )


@pytest.mark.asyncio
async def test_tags_candidates_section(page: Page, base_url: str, mock_api: MockState) -> None:
    """Tags page shows candidates with approve/reject buttons and article count pills."""
    await page.goto(f"{base_url}/#/tags")
    candidates = page.locator(".vocab-candidate-row")
    await candidates.first.wait_for(timeout=5000)
    assert await candidates.count() >= 1
    approve = page.locator(".btn-approve")
    reject = page.locator(".btn-reject")
    assert await approve.count() >= 1
    assert await reject.count() >= 1
    # Each candidate should have an article count pill
    count_pills = page.locator(".vocab-candidate-row .section-count")
    assert await count_pills.count() >= 1
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "tags-candidates.png"), full_page=True
    )


@pytest.mark.asyncio
async def test_tags_add_and_remove(page: Page, base_url: str, mock_api: MockState) -> None:
    """Add a tag to vocabulary and verify it appears, then remove it."""
    await page.goto(f"{base_url}/#/tags")
    add_input = page.locator(".vocab-add-input")
    await add_input.wait_for(timeout=5000)
    await add_input.fill("visual-test-tag")
    add_btn = page.locator(".vocab-add-row button")
    await add_btn.click()
    await page.wait_for_timeout(1000)
    pills = page.locator(".vocab-pill")
    pill_texts: list[str] = []
    for i in range(await pills.count()):
        text = await pills.nth(i).inner_text()
        pill_texts.append(text.strip())
    found = False
    for i in range(await pills.count()):
        text = await pills.nth(i).inner_text()
        if "visual-test-tag" in text:
            remove_btn = pills.nth(i).locator(".vocab-pill-x")
            await remove_btn.click()
            found = True
            break
    assert found, f"visual-test-tag not found in pills: {pill_texts}"
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "tags-add-remove.png"), full_page=True
    )


@pytest.mark.asyncio
async def test_tags_section_count_pills(page: Page, base_url: str, mock_api: MockState) -> None:
    """Section headings on Tags page use pill badges for counts."""
    await page.goto(f"{base_url}/#/tags")
    await page.wait_for_selector(".prefs-section", timeout=5000)
    count_pills = page.locator("h2 .section-count")
    await count_pills.first.wait_for(timeout=5000)
    assert await count_pills.count() >= 1
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "tags-section-counts.png"), full_page=True
    )


@pytest.mark.asyncio
async def test_tags_learned_weights(page: Page, base_url: str, mock_api: MockState) -> None:
    """Tags page displays learned tag weights with bars and reset buttons."""
    await page.goto(f"{base_url}/#/tags")
    weights = page.locator(".tag-weight-row")
    await weights.first.wait_for(timeout=5000)
    reset_btns = page.locator(".btn-reset svg")
    assert await reset_btns.count() > 0
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "tags-weights.png"), full_page=True
    )


@pytest.mark.asyncio
async def test_tags_dark_mode(page: Page, base_url: str, mock_api: MockState) -> None:
    """Dark mode: tags page renders correctly."""
    await page.emulate_media(color_scheme="dark")
    await page.goto(f"{base_url}/#/tags")
    await page.wait_for_selector(".prefs-section", timeout=5000)
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "dark-tags.png"), full_page=True
    )


# ── Sources page ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_sources_page_form(page: Page, base_url: str, mock_api: MockState) -> None:
    """Sources page renders the add-source form with segmented control and add button."""
    await page.goto(f"{base_url}/#/sources")
    await page.wait_for_selector(".source-form")
    category = page.locator(".input-category")
    await category.wait_for(timeout=3000)
    # Add button should have SVG icon
    add_btn = page.locator(".btn-icon-text svg")
    assert await add_btn.count() >= 1
    await page.screenshot(path=str(SCREENSHOT_DIR / "sources.png"), full_page=True)


@pytest.mark.asyncio
async def test_sources_segmented_control(page: Page, base_url: str, mock_api: MockState) -> None:
    """Sources form has a segmented control with RSS Feed and Web Page options."""
    await page.goto(f"{base_url}/#/sources")
    segmented = page.locator(".segmented-control")
    await segmented.wait_for(timeout=3000)
    btns = page.locator(".segmented-btn")
    assert await btns.count() == 2
    # First button (RSS) should be active by default
    rss_btn = btns.first
    assert "segmented-active" in (await rss_btn.get_attribute("class") or "")
    # Click Web Page — it should become active
    web_btn = btns.nth(1)
    await web_btn.click()
    assert "segmented-active" in (await web_btn.get_attribute("class") or "")
    assert "segmented-active" not in (await rss_btn.get_attribute("class") or "")
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "sources-segmented-web.png"), full_page=True
    )


@pytest.mark.asyncio
async def test_sources_list_with_icons(page: Page, base_url: str, mock_api: MockState) -> None:
    """Sources page shows source rows with icon action buttons and fetch info."""
    await page.goto(f"{base_url}/#/sources")
    rows = page.locator(".source-row")
    await rows.first.wait_for(timeout=5000)
    # Should have icon action buttons (refresh + trash SVGs)
    icon_btns = page.locator(".btn-icon-action")
    assert await icon_btns.count() >= 2
    # Should show fetch interval
    intervals = page.locator(".source-interval")
    assert await intervals.count() >= 1
    # Should show next run info
    next_runs = page.locator(".source-next-run")
    assert await next_runs.count() >= 1
    await page.screenshot(path=str(SCREENSHOT_DIR / "sources-list.png"), full_page=True)


@pytest.mark.asyncio
async def test_sources_type_badges(page: Page, base_url: str, mock_api: MockState) -> None:
    """Source rows display type badges (RSS or WEB)."""
    await page.goto(f"{base_url}/#/sources")
    badges = page.locator(".source-type-badge")
    await badges.first.wait_for(timeout=5000)
    assert await badges.count() >= 1
    # Badge should contain text RSS or WEB
    text = await badges.first.text_content()
    assert text in ("RSS", "WEB")
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "sources-type-badges.png"), full_page=True
    )


@pytest.mark.asyncio
async def test_sources_category_display(page: Page, base_url: str, mock_api: MockState) -> None:
    """Sources show category labels that are clickable."""
    await page.goto(f"{base_url}/#/sources")
    cats = page.locator(".source-category")
    await cats.first.wait_for(timeout=5000)
    assert await cats.count() >= 1
    await page.screenshot(path=str(SCREENSHOT_DIR / "sources-categories.png"), full_page=True)


@pytest.mark.asyncio
async def test_sources_category_edit_inline(page: Page, base_url: str, mock_api: MockState) -> None:
    """Clicking a category label opens an inline input editor."""
    await page.goto(f"{base_url}/#/sources")
    cat = page.locator(".source-category").first
    await cat.wait_for(timeout=5000)
    await cat.click()
    inline_input = page.locator(".input-inline")
    await inline_input.wait_for(timeout=2000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "sources-category-edit.png"), full_page=True)
    await page.keyboard.press("Escape")


@pytest.mark.asyncio
async def test_sources_delete_modal(page: Page, base_url: str, mock_api: MockState) -> None:
    """Delete button opens a custom modal dialog (not browser confirm)."""
    await page.goto(f"{base_url}/#/sources")
    delete_btn = page.locator(".btn-icon-danger").first
    await delete_btn.wait_for(timeout=5000)
    await delete_btn.click()
    modal = page.locator(".modal-overlay")
    await modal.wait_for(timeout=2000)
    dialog = page.locator(".modal-dialog")
    assert await dialog.count() == 1
    danger_btn = page.locator(".modal-btn-danger")
    assert await danger_btn.count() == 1
    await page.screenshot(path=str(SCREENSHOT_DIR / "sources-delete-modal.png"))
    await page.click(".modal-btn-cancel")
    await modal.wait_for(state="hidden", timeout=2000)


@pytest.mark.asyncio
async def test_sources_favicons(page: Page, base_url: str, mock_api: MockState) -> None:
    """Sources show favicons from their feed domains."""
    await page.goto(f"{base_url}/#/sources")
    favicons = page.locator(".source-favicon")
    await favicons.first.wait_for(timeout=5000)
    assert await favicons.count() >= 1
    await page.screenshot(path=str(SCREENSHOT_DIR / "sources-favicons.png"))


@pytest.mark.asyncio
async def test_sources_extraction_rules_toggle(page: Page, base_url: str, mock_api: MockState) -> None:
    """Web page sources show an extraction rules toggle bar."""
    await page.goto(f"{base_url}/#/sources")
    toggle = page.locator(".source-rules-toggle")
    await toggle.first.wait_for(timeout=5000)
    # Should have brain icon and label
    icon = toggle.first.locator(".source-rules-icon")
    assert await icon.count() >= 1
    label = toggle.first.locator(".source-rules-label")
    assert await label.count() == 1
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "sources-rules-toggle.png"), full_page=True
    )


@pytest.mark.asyncio
async def test_sources_extraction_rules_panel(page: Page, base_url: str, mock_api: MockState) -> None:
    """Clicking the rules toggle expands the extraction rules panel."""
    await page.goto(f"{base_url}/#/sources")
    toggle = page.locator(".source-rules-toggle:not(.source-auth-toggle)")
    await toggle.first.wait_for(timeout=5000)
    # Click to expand
    await toggle.first.click()
    panel = page.locator(".source-rules-panel")
    await panel.first.wait_for(state="visible", timeout=2000)
    # Should show rules grid with key-value pairs
    keys = panel.first.locator(".rules-key")
    values = panel.first.locator(".rules-value")
    assert await keys.count() >= 2  # At least Items + Title
    assert await values.count() >= 2
    # Should have re-learn button
    relearn = panel.first.locator(".source-rules-relearn")
    assert await relearn.count() == 1
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "sources-rules-panel.png"), full_page=True
    )
    # Click again to collapse
    await toggle.first.click()


@pytest.mark.asyncio
async def test_sources_auth_toggle(page: Page, base_url: str, mock_api: MockState) -> None:
    """Every source card shows an authentication disclosure toggle."""
    await page.goto(f"{base_url}/#/sources")
    card = page.locator(".source-card")
    await card.first.wait_for(timeout=5000)
    # Auth toggle should exist on every source card
    toggle = page.locator(".source-auth-toggle")
    assert await toggle.count() >= 1
    # Should have lock icon and label
    lock = toggle.first.locator(".source-rules-icon")
    assert await lock.count() == 1
    label = toggle.first.locator(".source-rules-label")
    assert await label.count() == 1
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "sources-auth-toggle.png"), full_page=True
    )


@pytest.mark.asyncio
async def test_sources_auth_panel(page: Page, base_url: str, mock_api: MockState) -> None:
    """Clicking the auth toggle expands the authentication panel with textarea and buttons."""
    await page.goto(f"{base_url}/#/sources")
    toggle = page.locator(".source-auth-toggle")
    await toggle.first.wait_for(timeout=5000)
    # Click to expand
    await toggle.first.click()
    panel = page.locator(".source-auth-panel")
    await panel.first.wait_for(state="visible", timeout=2000)
    # Should have cookie textarea, Save and Test buttons
    textarea = panel.first.locator("textarea")
    assert await textarea.count() == 1
    save_btn = panel.first.locator("button", has_text="Save")
    test_btn = panel.first.locator("button", has_text="Test")
    assert await save_btn.count() == 1
    assert await test_btn.count() == 1
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "sources-auth-panel.png"), full_page=True
    )
    # Click again to collapse
    await toggle.first.click()
    await panel.first.wait_for(state="hidden", timeout=2000)


@pytest.mark.asyncio
async def test_sources_auth_independent_toggle(page: Page, base_url: str, mock_api: MockState) -> None:
    """Auth and extraction rules disclosures toggle independently."""
    await page.goto(f"{base_url}/#/sources")
    rules_toggle = page.locator(".source-rules-toggle:not(.source-auth-toggle)")
    await rules_toggle.first.wait_for(timeout=5000)
    # Open both
    await rules_toggle.first.click()
    rules_panel = page.locator(".source-rules-panel")
    await rules_panel.first.wait_for(state="visible", timeout=2000)
    # Find the auth toggle on the same card
    card = rules_toggle.first.locator("xpath=ancestor::div[contains(@class,'source-card')]")
    card_auth_toggle = card.locator(".source-auth-toggle")
    await card_auth_toggle.click()
    auth_panel = card.locator(".source-auth-panel")
    await auth_panel.wait_for(state="visible", timeout=2000)
    # Both panels should be visible
    assert await rules_panel.first.is_visible()
    assert await auth_panel.is_visible()
    # Close rules — auth should stay open
    await rules_toggle.first.click()
    await rules_panel.first.wait_for(state="hidden", timeout=2000)
    assert await auth_panel.is_visible(), "Auth panel should stay open when rules panel closes"
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "sources-auth-independent.png"), full_page=True
    )
    # Clean up
    await card_auth_toggle.click()


# ── Platform sources ──────────────────────────────────────


@pytest.mark.asyncio
async def test_platform_section_visible(
    page: Page, base_url: str, mock_api: MockState
) -> None:
    """Sources page shows a Platforms section with heading and cards."""
    await page.goto(f"{base_url}/#/sources")
    heading = page.locator(".section-heading", has_text="Platforms")
    await heading.wait_for(timeout=5000)
    grid = page.locator(".platform-grid")
    assert await grid.count() == 1
    cards = page.locator(".platform-card")
    assert await cards.count() >= 1
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "platforms-section.png"), full_page=True
    )


@pytest.mark.asyncio
async def test_platform_card_collapsed(
    page: Page, base_url: str, mock_api: MockState
) -> None:
    """Platform card is collapsed by default showing header only."""
    await page.goto(f"{base_url}/#/sources")
    card = page.locator(".platform-card").first
    await card.wait_for(timeout=5000)
    # Card should NOT have .platform-open class
    cls = await card.get_attribute("class") or ""
    assert "platform-open" not in cls
    # Header should be visible
    header = card.locator(".platform-header")
    assert await header.is_visible()
    # Body should be hidden
    body = card.locator(".platform-body")
    assert await body.count() == 0 or not await body.is_visible()
    await card.screenshot(
        path=str(SCREENSHOT_DIR / "platform-card-collapsed.png")
    )


@pytest.mark.asyncio
async def test_platform_card_expand(
    page: Page, base_url: str, mock_api: MockState
) -> None:
    """Clicking platform card header expands config, status, actions."""
    await page.goto(f"{base_url}/#/sources")
    card = page.locator(".platform-card").first
    await card.wait_for(timeout=5000)
    header = card.locator(".platform-header")
    await header.click()
    # Should now be open
    cls = await card.get_attribute("class") or ""
    assert "platform-open" in cls
    # Body should be visible
    body = card.locator(".platform-body")
    await body.wait_for(state="visible", timeout=2000)
    # Config fields should be present
    fields = body.locator(".platform-field")
    assert await fields.count() >= 1
    # Actions should be present
    actions = body.locator(".platform-actions")
    assert await actions.count() == 1
    await card.screenshot(
        path=str(SCREENSHOT_DIR / "platform-card-expanded.png")
    )


@pytest.mark.asyncio
async def test_platform_toggle_switch(
    page: Page, base_url: str, mock_api: MockState
) -> None:
    """Platform card has a toggle switch that reflects enabled state."""
    await page.goto(f"{base_url}/#/sources")
    card = page.locator(".platform-card").first
    await card.wait_for(timeout=5000)
    toggle = card.locator(".platform-toggle input[type='checkbox']")
    assert await toggle.count() == 1
    # HN mock is enabled, so checkbox should be checked
    assert await toggle.is_checked()
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "platform-toggle.png")
    )


@pytest.mark.asyncio
async def test_platform_icon_renders(
    page: Page, base_url: str, mock_api: MockState
) -> None:
    """HN platform card shows the Y Combinator icon."""
    await page.goto(f"{base_url}/#/sources")
    card = page.locator(".platform-card").first
    await card.wait_for(timeout=5000)
    icon = card.locator(".platform-icon svg")
    assert await icon.count() == 1
    # Name should show Hacker News
    name = card.locator(".platform-name")
    assert "Hacker News" in (await name.text_content() or "")


@pytest.mark.asyncio
async def test_platform_action_icons(
    page: Page, base_url: str, mock_api: MockState
) -> None:
    """Expanded platform card has icon action buttons (save + fetch)."""
    await page.goto(f"{base_url}/#/sources")
    card = page.locator(".platform-card").first
    await card.wait_for(timeout=5000)
    # Expand
    await card.locator(".platform-header").click()
    body = card.locator(".platform-body")
    await body.wait_for(state="visible", timeout=2000)
    # Should have icon action buttons with SVGs
    btns = body.locator(".btn-icon-action")
    assert await btns.count() == 2
    for i in range(2):
        svg = btns.nth(i).locator("svg")
        assert await svg.count() >= 1
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "platform-action-icons.png")
    )


@pytest.mark.asyncio
async def test_platform_chevron_rotates(
    page: Page, base_url: str, mock_api: MockState
) -> None:
    """Chevron rotates when platform card is expanded."""
    await page.goto(f"{base_url}/#/sources")
    card = page.locator(".platform-card").first
    await card.wait_for(timeout=5000)
    chevron = card.locator(".platform-chevron")
    # Before click — not rotated
    cls_before = await chevron.get_attribute("class") or ""
    assert "rotated" not in cls_before
    # Click to expand
    await card.locator(".platform-header").click()
    cls_after = await chevron.get_attribute("class") or ""
    assert "rotated" in cls_after
    # Click again to collapse
    await card.locator(".platform-header").click()
    cls_final = await chevron.get_attribute("class") or ""
    assert "rotated" not in cls_final


@pytest.mark.asyncio
async def test_platform_custom_sources_heading(
    page: Page, base_url: str, mock_api: MockState
) -> None:
    """Sources page shows 'Custom Sources' heading above the form."""
    await page.goto(f"{base_url}/#/sources")
    heading = page.locator(".section-heading", has_text="Custom Sources")
    await heading.wait_for(timeout=5000)


@pytest.mark.asyncio
async def test_platform_dark_mode(
    page: Page, base_url: str, mock_api: MockState
) -> None:
    """Dark mode: platform cards render correctly."""
    await page.emulate_media(color_scheme="dark")
    await page.goto(f"{base_url}/#/sources")
    card = page.locator(".platform-card").first
    await card.wait_for(timeout=5000)
    # Expand for full dark mode check
    await card.locator(".platform-header").click()
    body = card.locator(".platform-body")
    await body.wait_for(state="visible", timeout=2000)
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "dark-platform-expanded.png"),
        full_page=True,
    )


# ── Nav bar ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nav_icons_and_layout(page: Page, base_url: str, mock_api: MockState) -> None:
    """Nav bar has SVG icons on all links and Feed on the left."""
    await page.goto(f"{base_url}/#/feed")
    nav = page.locator(".nav-bar")
    await nav.wait_for(timeout=3000)
    # Nav links should have SVG icons
    nav_svgs = page.locator(".nav-link svg")
    assert await nav_svgs.count() >= 3  # Sources, Stats, Preferences (Feed too)
    # Left section should contain Feed
    left = page.locator(".nav-left .nav-link")
    assert await left.count() >= 1
    await nav.screenshot(path=str(SCREENSHOT_DIR / "nav-icons.png"))


@pytest.mark.asyncio
async def test_nav_active_indicator(page: Page, base_url: str, mock_api: MockState) -> None:
    """Nav bar shows active indicator on current page."""
    for route in ["feed", "stats", "preferences"]:
        await page.goto(f"{base_url}/#/{route}")
        await page.wait_for_selector(".nav-bar")
        active_link = page.locator(".nav-link.active")
        assert await active_link.count() >= 1
    await page.screenshot(path=str(SCREENSHOT_DIR / "nav-active.png"))


@pytest.mark.asyncio
async def test_nav_logo(page: Page, base_url: str, mock_api: MockState) -> None:
    """Nav bar displays the Sift logo and brand text."""
    await page.goto(f"{base_url}/#/feed")
    brand = page.locator(".nav-brand")
    await brand.wait_for(timeout=3000)
    logo = page.locator(".nav-logo")
    assert await logo.count() >= 1
    await brand.screenshot(path=str(SCREENSHOT_DIR / "nav-logo.png"))


# ── Dark mode (all pages) ─────────────────────────────────


@pytest.mark.asyncio
async def test_dark_mode_feed(page: Page, base_url: str, mock_api: MockState) -> None:
    """Dark mode: feed page renders correctly."""
    await page.emulate_media(color_scheme="dark")
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".nav-bar")
    await page.wait_for_selector(".article-card", timeout=5000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "dark-feed.png"), full_page=True)


@pytest.mark.asyncio
async def test_dark_mode_stats(page: Page, base_url: str, mock_api: MockState) -> None:
    """Dark mode: stats page renders correctly."""
    await page.emulate_media(color_scheme="dark")
    await page.goto(f"{base_url}/#/stats")
    await page.wait_for_selector(".stats-section")
    await page.screenshot(path=str(SCREENSHOT_DIR / "dark-stats.png"), full_page=True)


@pytest.mark.asyncio
async def test_dark_mode_preferences(page: Page, base_url: str, mock_api: MockState) -> None:
    """Dark mode: preferences page renders correctly."""
    await page.emulate_media(color_scheme="dark")
    await page.goto(f"{base_url}/#/preferences")
    await page.wait_for_selector(".prefs-section")
    await page.screenshot(path=str(SCREENSHOT_DIR / "dark-preferences.png"), full_page=True)


@pytest.mark.asyncio
async def test_dark_mode_sources(page: Page, base_url: str, mock_api: MockState) -> None:
    """Dark mode: sources page with icon buttons."""
    await page.emulate_media(color_scheme="dark")
    await page.goto(f"{base_url}/#/sources")
    await page.wait_for_selector(".source-form")
    await page.screenshot(path=str(SCREENSHOT_DIR / "dark-sources.png"), full_page=True)


@pytest.mark.asyncio
async def test_dark_mode_help_overlay(page: Page, base_url: str, mock_api: MockState) -> None:
    """Dark mode: help overlay renders correctly."""
    await page.emulate_media(color_scheme="dark")
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".feed-toolbar")
    await page.keyboard.press("?")
    await page.wait_for_selector(".help-overlay")
    await page.screenshot(path=str(SCREENSHOT_DIR / "dark-help-overlay.png"))


# ── Mobile viewport ───────────────────────────────────────


@pytest.mark.asyncio
async def test_mobile_feed(page: Page, base_url: str, mock_api: MockState) -> None:
    """Mobile viewport (375px) renders feed correctly."""
    await page.set_viewport_size({"width": 375, "height": 812})
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".nav-bar")
    await page.wait_for_selector(".article-card", timeout=5000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "mobile-feed.png"), full_page=True)
    await page.set_viewport_size({"width": 1280, "height": 800})


@pytest.mark.asyncio
async def test_mobile_sources(page: Page, base_url: str, mock_api: MockState) -> None:
    """Mobile viewport (375px) renders sources with icon buttons."""
    await page.set_viewport_size({"width": 375, "height": 812})
    await page.goto(f"{base_url}/#/sources")
    await page.wait_for_selector(".source-form")
    await page.screenshot(path=str(SCREENSHOT_DIR / "mobile-sources.png"), full_page=True)
    await page.set_viewport_size({"width": 1280, "height": 800})


@pytest.mark.asyncio
async def test_mobile_stats(page: Page, base_url: str, mock_api: MockState) -> None:
    """Mobile viewport (375px) renders stats correctly."""
    await page.set_viewport_size({"width": 375, "height": 812})
    await page.goto(f"{base_url}/#/stats")
    await page.wait_for_selector(".stats-section")
    await page.screenshot(path=str(SCREENSHOT_DIR / "mobile-stats.png"), full_page=True)
    await page.set_viewport_size({"width": 1280, "height": 800})


# ── Onboarding modal ─────────────────────────────────────


@pytest.mark.asyncio
async def test_onboarding_modal_shows_for_cold_start(page: Page, base_url: str, mock_api_cold_start: MockState) -> None:
    """Onboarding modal appears when profile_version == 0."""
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".feed-toolbar")
    modal = page.locator(".onboarding-dialog")
    await modal.wait_for(timeout=3000)
    # Should have title and input
    title = modal.locator(".modal-title")
    assert "Welcome" in (await title.text_content() or "")
    input_el = modal.locator(".onboarding-input")
    assert await input_el.count() == 1
    # Should have Skip and Get Started buttons
    skip = modal.locator(".modal-btn-cancel")
    assert await skip.count() == 1
    start = modal.locator(".modal-btn-confirm")
    assert await start.count() == 1
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "onboarding-modal.png")
    )
    # Dismiss to not interfere with other tests
    await skip.click()


@pytest.mark.asyncio
async def test_onboarding_add_interest_pills(page: Page, base_url: str, mock_api_cold_start: MockState) -> None:
    """Typing interests and pressing Enter adds pills in the onboarding modal."""
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".feed-toolbar")
    modal = page.locator(".onboarding-dialog")
    await modal.wait_for(timeout=3000)
    input_el = modal.locator(".onboarding-input")
    await input_el.fill("rust")
    await input_el.press("Enter")
    await input_el.fill("machine learning")
    await input_el.press("Enter")
    pills = modal.locator(".onboarding-pill")
    assert await pills.count() == 2
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "onboarding-pills.png")
    )
    # Dismiss
    skip = modal.locator(".modal-btn-cancel")
    await skip.click()


@pytest.mark.asyncio
async def test_onboarding_not_shown_when_dismissed(page: Page, base_url: str, mock_api: MockState) -> None:
    """Onboarding modal does not appear when profile_version > 0."""
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".feed-toolbar")
    await page.wait_for_timeout(1000)
    modal = page.locator(".onboarding-dialog")
    assert await modal.count() == 0


# ── Tag quality section ──────────────────────────────────


@pytest.mark.asyncio
async def test_tags_quality_section(page: Page, base_url: str, mock_api: MockState) -> None:
    """Tags page shows tag quality section with noisy tags."""
    await page.goto(f"{base_url}/#/tags")
    await page.wait_for_selector(".prefs-section", timeout=5000)
    table = page.locator(".tag-quality-table")
    await table.wait_for(timeout=5000)
    # Should have header and at least one data row
    header = table.locator(".tag-quality-header")
    assert await header.count() == 1
    rows = table.locator(".tag-quality-row:not(.tag-quality-header)")
    assert await rows.count() >= 1
    # Each row should have warning icon, votes, and bar
    name_cell = rows.first.locator(".tag-quality-name svg")
    assert await name_cell.count() >= 1
    bar = rows.first.locator(".tag-quality-bar-fill")
    assert await bar.count() == 1
    await page.screenshot(
        path=str(SCREENSHOT_DIR / "tags-quality.png"), full_page=True
    )


@pytest.mark.asyncio
async def test_tags_quality_disagreement_bars(page: Page, base_url: str, mock_api: MockState) -> None:
    """Tag quality rows show disagreement ratio bars and percentage labels."""
    await page.goto(f"{base_url}/#/tags")
    table = page.locator(".tag-quality-table")
    await table.wait_for(timeout=5000)
    rows = table.locator(".tag-quality-row:not(.tag-quality-header)")
    count = await rows.count()
    assert count >= 1
    for i in range(min(count, 3)):
        bar = rows.nth(i).locator(".tag-quality-bar-fill")
        width = await bar.evaluate("el => el.style.width")
        assert width.endswith("%"), f"Expected percentage width, got {width}"
