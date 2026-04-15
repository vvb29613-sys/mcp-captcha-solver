"""Selenium WebDriver creation helpers.

This module intentionally stays small and boring: it knows how to start and
stop a local browser, but it does not know anything about captcha types,
workflow steps, MCP tools, or agent behavior. Keeping that boundary clean
makes the rest of the project easier to reason about.
"""

from __future__ import annotations

import logging

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.remote.webdriver import WebDriver

from app.services.config import Settings

logger = logging.getLogger(__name__)


def create_driver(settings: Settings) -> WebDriver:
    """Create a Selenium driver for local runs.

    Why this exists:
        Workflow code should not be responsible for assembling browser options
        or deciding which Selenium driver class to instantiate. A dedicated
        factory keeps browser bootstrapping in one place.

    How it works:
        - Reads the desired browser from ``Settings``.
        - Configures a Chrome driver with a few local-friendly defaults.
        - Returns a ready-to-use Selenium ``WebDriver`` instance.

    Current scope:
        Only Chrome is supported. If the project later grows support for other
        browsers, this is the module that should branch on ``browser_name``.
    """
    browser_name = settings.browser_name.lower()
    if browser_name != "chrome":
        raise ValueError(f"Unsupported browser: {settings.browser_name}")

    options = ChromeOptions()
    if settings.browser_headless:
        options.add_argument("--headless=new")

    options.add_argument("--window-size=1440,1100")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")

    return webdriver.Chrome(options=options)


def safe_quit(driver: WebDriver | None) -> None:
    """Close a driver without masking the original workflow error.

    Why this exists:
        Cleanup usually happens in error paths. If ``driver.quit()`` raises
        while another, more important exception is already being handled, the
        cleanup failure should not replace the real error that caused the flow
        to fail.

    The function therefore treats driver shutdown as best-effort cleanup.
    """
    if driver is None:
        return

    try:
        driver.quit()
    except Exception:
        logger.debug("driver.quit() failed during best-effort cleanup", exc_info=True)
