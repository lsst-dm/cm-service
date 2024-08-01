import re
import time
import pytest
from playwright.async_api import expect, async_playwright

from safir.testing.uvicorn import UvicornProcess


@pytest.mark.asyncio()
async def test_has_title(uvicorn: UvicornProcess, engine) -> None:
    async with async_playwright() as playwright:
        my_browser = await playwright.chromium.launch(headless=False)
        my_page = await my_browser.new_page()
        await my_page.goto(f"{uvicorn.url}/web_app/campaigns/")
        await expect(my_page).to_have_title(re.compile("Campaigns"))
        time.sleep(10)
        await my_browser.close()
