"""Playwright visual test fixtures.

These tests mock all API responses at the browser level, so only the Vite
frontend dev server is needed (no backend):
  cd frontend && npm run dev   (starts on :5173)

Run with: uv run pytest tests/visual/ --headed (for visible browser)
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from playwright.async_api import Page, async_playwright

from tests.visual.mock_data import MockState, install_mock_routes


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


@pytest_asyncio.fixture
async def mock_api(page: Page) -> MockState:
    """Install mock API routes (profile_version=1, normal state)."""
    return await install_mock_routes(page)


@pytest_asyncio.fixture
async def mock_api_cold_start(page: Page) -> MockState:
    """Install mock API routes with cold-start preferences (profile_version=0)."""
    return await install_mock_routes(page, cold_start=True)
