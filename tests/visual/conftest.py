"""Playwright visual test fixtures.

These tests require both backend and frontend dev servers running:
  make dev  (starts backend on :8000 and frontend on :5173)

Run with: uv run pytest tests/visual/ --headed (for visible browser)
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from playwright.async_api import Page, async_playwright


@pytest.fixture(scope="session")
def base_url() -> str:
    return "http://localhost:5173"


@pytest_asyncio.fixture
async def page(base_url: str) -> AsyncIterator[Page]:
    """Provide a Playwright page with 1280x800 viewport."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await ctx.new_page()
        yield page
        await browser.close()
