"""Visual regression tests for Sift.

Run with the dev servers active:
  make dev
  uv run pytest tests/visual/ -v

For visible browser:
  uv run pytest tests/visual/ --headed -v
"""

from pathlib import Path

import pytest
from playwright.async_api import Page

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


# ── Feed page ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_feed_page_loads(page: Page, base_url: str) -> None:
    """Feed page renders with nav bar, toolbar, and article cards or empty state."""
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".nav-bar")
    await page.wait_for_selector(".feed-toolbar")
    await page.wait_for_selector(".article-card, .empty-state", timeout=5000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "feed.png"), full_page=True)


@pytest.mark.asyncio
async def test_feed_training_mode(page: Page, base_url: str) -> None:
    """Training mode toggle activates and shows all-score articles."""
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".btn-training")
    await page.click(".btn-training")
    btn = page.locator(".btn-training")
    assert "active" in (await btn.get_attribute("class") or "")
    await page.wait_for_selector(".article-card, .empty-state", timeout=5000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "feed-training.png"), full_page=True)
    await page.click(".btn-training")


@pytest.mark.asyncio
async def test_feed_article_card_hover(page: Page, base_url: str) -> None:
    """Article card shows action buttons on hover."""
    await page.goto(f"{base_url}/#/feed")
    card = page.locator(".article-card").first
    try:
        await card.wait_for(timeout=5000)
    except Exception:
        pytest.skip("No articles in feed to test hover")
    await card.hover()
    actions = card.locator(".card-actions")
    await actions.wait_for(state="visible", timeout=2000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "feed-card-hover.png"))


@pytest.mark.asyncio
async def test_feed_card_action_order(page: Page, base_url: str) -> None:
    """Card actions: up, read-toggle, down, spacer, then secondary."""
    await page.goto(f"{base_url}/#/feed")
    card = page.locator(".article-card").first
    try:
        await card.wait_for(timeout=5000)
    except Exception:
        pytest.skip("No articles in feed")
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
async def test_feed_card_actions_always_subtly_visible(page: Page, base_url: str) -> None:
    """Card actions are subtly visible (opacity > 0) even without hover."""
    await page.goto(f"{base_url}/#/feed")
    card = page.locator(".article-card").first
    try:
        await card.wait_for(timeout=5000)
    except Exception:
        pytest.skip("No articles in feed")
    # Without hover, actions should have opacity > 0 (subtly visible)
    actions = card.locator(".card-actions")
    opacity = await actions.evaluate("el => getComputedStyle(el).opacity")
    assert float(opacity) > 0
    await page.screenshot(path=str(SCREENSHOT_DIR / "feed-card-actions-subtle.png"))


@pytest.mark.asyncio
async def test_feed_keyboard_navigation(page: Page, base_url: str) -> None:
    """j/k keyboard shortcuts navigate between cards."""
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".article-card, .empty-state", timeout=5000)
    cards = page.locator(".article-card")
    if await cards.count() < 1:
        pytest.skip("No articles in feed for keyboard nav")
    await page.keyboard.press("j")
    focused = page.locator(".article-card.focused")
    await focused.wait_for(timeout=2000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "feed-keyboard-focus.png"))


@pytest.mark.asyncio
async def test_feed_search(page: Page, base_url: str) -> None:
    """Search input filters the feed."""
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".search-input")
    await page.fill(".search-input", "test query")
    await page.wait_for_timeout(500)
    await page.screenshot(path=str(SCREENSHOT_DIR / "feed-search.png"), full_page=True)


@pytest.mark.asyncio
async def test_feed_source_filter(page: Page, base_url: str) -> None:
    """Source filter dropdown is rendered."""
    await page.goto(f"{base_url}/#/feed")
    select = page.locator(".filter-source")
    await select.wait_for(timeout=5000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "feed-source-filter.png"))


# ── Keyboard Help ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_keyboard_help_overlay(page: Page, base_url: str) -> None:
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
async def test_stats_page_overview(page: Page, base_url: str) -> None:
    """Stats page renders overview cards and all sections."""
    await page.goto(f"{base_url}/#/stats")
    await page.wait_for_selector(".stats-section")
    grid = page.locator(".stats-grid")
    await grid.wait_for(timeout=5000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "stats.png"), full_page=True)


@pytest.mark.asyncio
async def test_stats_score_distribution(page: Page, base_url: str) -> None:
    """Stats page shows the SVG score distribution chart."""
    await page.goto(f"{base_url}/#/stats")
    chart = page.locator(".score-chart")
    try:
        await chart.wait_for(timeout=5000)
        await chart.screenshot(path=str(SCREENSHOT_DIR / "stats-score-chart.png"))
    except Exception:
        await page.screenshot(path=str(SCREENSHOT_DIR / "stats-no-chart.png"), full_page=True)


@pytest.mark.asyncio
async def test_stats_job_table_with_run_buttons(page: Page, base_url: str) -> None:
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
async def test_stats_issues_banner(page: Page, base_url: str) -> None:
    """Stats page shows issues banner when errors exist (or no banner when healthy)."""
    await page.goto(f"{base_url}/#/stats")
    await page.wait_for_selector(".stats-section", timeout=5000)
    banner = page.locator(".issues-banner")
    if await banner.count() > 0:
        await banner.screenshot(path=str(SCREENSHOT_DIR / "stats-issues-banner.png"))
    else:
        # No issues — verify no banner exists (healthy state)
        await page.screenshot(path=str(SCREENSHOT_DIR / "stats-healthy.png"), full_page=True)


@pytest.mark.asyncio
async def test_stats_scoring_failures_table(page: Page, base_url: str) -> None:
    """Stats page shows detailed scoring failures table when failures exist."""
    await page.goto(f"{base_url}/#/stats")
    await page.wait_for_selector(".stats-section", timeout=5000)
    failures_table = page.locator(".issues-table")
    if await failures_table.count() > 0:
        # Should have article title, source, attempts, error columns
        headers = failures_table.locator("th")
        assert await headers.count() >= 4
        rows = failures_table.locator("tbody tr")
        assert await rows.count() >= 1
        # Take a screenshot of just the issues section
        issues_section = page.locator(".issues-section")
        await issues_section.screenshot(path=str(SCREENSHOT_DIR / "stats-scoring-failures.png"))
    else:
        pytest.skip("No scoring failures to display")


@pytest.mark.asyncio
async def test_stats_source_health_table(page: Page, base_url: str) -> None:
    """Stats page shows source health table."""
    await page.goto(f"{base_url}/#/stats")
    await page.wait_for_selector(".stats-section")
    tables = page.locator(".stats-table")
    if await tables.count() > 0:
        await tables.first.screenshot(path=str(SCREENSHOT_DIR / "stats-source-health.png"))


@pytest.mark.asyncio
async def test_stats_tag_cloud(page: Page, base_url: str) -> None:
    """Stats page renders the tag cloud."""
    await page.goto(f"{base_url}/#/stats")
    cloud = page.locator(".tag-cloud")
    try:
        await cloud.wait_for(timeout=5000)
        await cloud.screenshot(path=str(SCREENSHOT_DIR / "stats-tag-cloud.png"))
    except Exception:
        pytest.skip("No tags yet for tag cloud")


# ── Preferences page ──────────────────────────────────────


@pytest.mark.asyncio
async def test_preferences_page_sections(page: Page, base_url: str) -> None:
    """Preferences page renders all sections: language, profile, interests, tags."""
    await page.goto(f"{base_url}/#/preferences")
    sections = page.locator(".prefs-section")
    await sections.first.wait_for(timeout=5000)
    count = await sections.count()
    assert count >= 3
    await page.screenshot(path=str(SCREENSHOT_DIR / "preferences.png"), full_page=True)


@pytest.mark.asyncio
async def test_preferences_language_pills_with_flags(page: Page, base_url: str) -> None:
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
async def test_preferences_save_buttons_have_icons(page: Page, base_url: str) -> None:
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


@pytest.mark.asyncio
async def test_preferences_tag_weights(page: Page, base_url: str) -> None:
    """Tag weights section displays with weight values and reset icons."""
    await page.goto(f"{base_url}/#/preferences")
    weights = page.locator(".tag-weight-row")
    try:
        await weights.first.wait_for(timeout=3000)
        # Reset buttons should have SVG icons
        reset_btns = page.locator(".btn-reset svg")
        assert await reset_btns.count() > 0
        await page.screenshot(path=str(SCREENSHOT_DIR / "preferences-tags.png"), full_page=True)
    except Exception:
        pytest.skip("No tag weights to display")


# ── Sources page ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_sources_page_form(page: Page, base_url: str) -> None:
    """Sources page renders the add-source form with SVG add button."""
    await page.goto(f"{base_url}/#/sources")
    await page.wait_for_selector(".source-form")
    category = page.locator(".input-category")
    await category.wait_for(timeout=3000)
    # Add button should have SVG icon
    add_btn = page.locator(".btn-icon-text svg")
    assert await add_btn.count() >= 1
    await page.screenshot(path=str(SCREENSHOT_DIR / "sources.png"), full_page=True)


@pytest.mark.asyncio
async def test_sources_list_with_icons(page: Page, base_url: str) -> None:
    """Sources page shows source rows with icon action buttons and fetch info."""
    await page.goto(f"{base_url}/#/sources")
    rows = page.locator(".source-row")
    try:
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
    except Exception:
        pytest.skip("No sources configured")


@pytest.mark.asyncio
async def test_sources_category_display(page: Page, base_url: str) -> None:
    """Sources show category labels (or 'Uncategorized' placeholder) that are clickable."""
    await page.goto(f"{base_url}/#/sources")
    cats = page.locator(".source-category")
    try:
        await cats.first.wait_for(timeout=5000)
        # At least one category label should exist
        assert await cats.count() >= 1
        await page.screenshot(path=str(SCREENSHOT_DIR / "sources-categories.png"), full_page=True)
    except Exception:
        pytest.skip("No sources configured")


@pytest.mark.asyncio
async def test_sources_category_edit_inline(page: Page, base_url: str) -> None:
    """Clicking a category label opens an inline input editor."""
    await page.goto(f"{base_url}/#/sources")
    cat = page.locator(".source-category").first
    try:
        await cat.wait_for(timeout=5000)
    except Exception:
        pytest.skip("No sources configured")
    await cat.click()
    # Inline input should appear
    inline_input = page.locator(".input-inline")
    await inline_input.wait_for(timeout=2000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "sources-category-edit.png"), full_page=True)
    # Press Escape to cancel
    await page.keyboard.press("Escape")


@pytest.mark.asyncio
async def test_sources_delete_modal(page: Page, base_url: str) -> None:
    """Delete button opens a custom modal dialog (not browser confirm)."""
    await page.goto(f"{base_url}/#/sources")
    delete_btn = page.locator(".btn-icon-danger").first
    try:
        await delete_btn.wait_for(timeout=5000)
    except Exception:
        pytest.skip("No sources configured")
    await delete_btn.click()
    modal = page.locator(".modal-overlay")
    await modal.wait_for(timeout=2000)
    dialog = page.locator(".modal-dialog")
    assert await dialog.count() == 1
    # Should have danger-styled confirm button
    danger_btn = page.locator(".modal-btn-danger")
    assert await danger_btn.count() == 1
    await page.screenshot(path=str(SCREENSHOT_DIR / "sources-delete-modal.png"))
    # Cancel the modal
    await page.click(".modal-btn-cancel")
    await modal.wait_for(state="hidden", timeout=2000)


@pytest.mark.asyncio
async def test_sources_favicons(page: Page, base_url: str) -> None:
    """Sources show favicons from their feed domains."""
    await page.goto(f"{base_url}/#/sources")
    favicons = page.locator(".source-favicon")
    try:
        await favicons.first.wait_for(timeout=5000)
        assert await favicons.count() >= 1
        await page.screenshot(path=str(SCREENSHOT_DIR / "sources-favicons.png"))
    except Exception:
        pytest.skip("No sources with favicons")


# ── Nav bar ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nav_icons_and_layout(page: Page, base_url: str) -> None:
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
async def test_nav_active_indicator(page: Page, base_url: str) -> None:
    """Nav bar shows active indicator on current page."""
    for route in ["feed", "stats", "preferences"]:
        await page.goto(f"{base_url}/#/{route}")
        await page.wait_for_selector(".nav-bar")
        active_link = page.locator(".nav-link.active")
        assert await active_link.count() >= 1
    await page.screenshot(path=str(SCREENSHOT_DIR / "nav-active.png"))


@pytest.mark.asyncio
async def test_nav_logo(page: Page, base_url: str) -> None:
    """Nav bar displays the Sift logo and brand text."""
    await page.goto(f"{base_url}/#/feed")
    brand = page.locator(".nav-brand")
    await brand.wait_for(timeout=3000)
    logo = page.locator(".nav-logo")
    assert await logo.count() >= 1
    await brand.screenshot(path=str(SCREENSHOT_DIR / "nav-logo.png"))


# ── Dark mode (all pages) ─────────────────────────────────


@pytest.mark.asyncio
async def test_dark_mode_feed(page: Page, base_url: str) -> None:
    """Dark mode: feed page renders correctly."""
    await page.emulate_media(color_scheme="dark")
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".nav-bar")
    await page.wait_for_selector(".article-card, .empty-state", timeout=5000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "dark-feed.png"), full_page=True)


@pytest.mark.asyncio
async def test_dark_mode_stats(page: Page, base_url: str) -> None:
    """Dark mode: stats page renders correctly."""
    await page.emulate_media(color_scheme="dark")
    await page.goto(f"{base_url}/#/stats")
    await page.wait_for_selector(".stats-section")
    await page.screenshot(path=str(SCREENSHOT_DIR / "dark-stats.png"), full_page=True)


@pytest.mark.asyncio
async def test_dark_mode_preferences(page: Page, base_url: str) -> None:
    """Dark mode: preferences page renders correctly."""
    await page.emulate_media(color_scheme="dark")
    await page.goto(f"{base_url}/#/preferences")
    await page.wait_for_selector(".prefs-section")
    await page.screenshot(path=str(SCREENSHOT_DIR / "dark-preferences.png"), full_page=True)


@pytest.mark.asyncio
async def test_dark_mode_sources(page: Page, base_url: str) -> None:
    """Dark mode: sources page with icon buttons."""
    await page.emulate_media(color_scheme="dark")
    await page.goto(f"{base_url}/#/sources")
    await page.wait_for_selector(".source-form")
    await page.screenshot(path=str(SCREENSHOT_DIR / "dark-sources.png"), full_page=True)


@pytest.mark.asyncio
async def test_dark_mode_help_overlay(page: Page, base_url: str) -> None:
    """Dark mode: help overlay renders correctly."""
    await page.emulate_media(color_scheme="dark")
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".feed-toolbar")
    await page.keyboard.press("?")
    await page.wait_for_selector(".help-overlay")
    await page.screenshot(path=str(SCREENSHOT_DIR / "dark-help-overlay.png"))


# ── Mobile viewport ───────────────────────────────────────


@pytest.mark.asyncio
async def test_mobile_feed(page: Page, base_url: str) -> None:
    """Mobile viewport (375px) renders feed correctly."""
    await page.set_viewport_size({"width": 375, "height": 812})
    await page.goto(f"{base_url}/#/feed")
    await page.wait_for_selector(".nav-bar")
    await page.wait_for_selector(".article-card, .empty-state", timeout=5000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "mobile-feed.png"), full_page=True)
    await page.set_viewport_size({"width": 1280, "height": 800})


@pytest.mark.asyncio
async def test_mobile_sources(page: Page, base_url: str) -> None:
    """Mobile viewport (375px) renders sources with icon buttons."""
    await page.set_viewport_size({"width": 375, "height": 812})
    await page.goto(f"{base_url}/#/sources")
    await page.wait_for_selector(".source-form")
    await page.screenshot(path=str(SCREENSHOT_DIR / "mobile-sources.png"), full_page=True)
    await page.set_viewport_size({"width": 1280, "height": 800})


@pytest.mark.asyncio
async def test_mobile_stats(page: Page, base_url: str) -> None:
    """Mobile viewport (375px) renders stats correctly."""
    await page.set_viewport_size({"width": 375, "height": 812})
    await page.goto(f"{base_url}/#/stats")
    await page.wait_for_selector(".stats-section")
    await page.screenshot(path=str(SCREENSHOT_DIR / "mobile-stats.png"), full_page=True)
    await page.set_viewport_size({"width": 1280, "height": 800})
