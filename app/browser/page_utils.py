"""Small Selenium helpers shared across workflows.

These helpers intentionally operate at the Selenium utility level:
waiting for elements, resolving selector strategies, reading text, and writing
screenshots. They do not encode workflow decisions such as "solve captcha" or
"submit verification"; those belong in workflow code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver, WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEFAULT_TIMEOUT: Final[int] = 15


def _by_from_strategy(strategy: str) -> str:
    """Map a simplified selector strategy to Selenium's ``By`` constant.

    The agent-facing browser tools accept a compact strategy vocabulary
    (``xpath``, ``css``, ``id``, ``name``). This helper translates that public
    API into the lower-level Selenium selector enum.
    """
    normalized = strategy.lower().strip()
    if normalized == "xpath":
        return By.XPATH
    if normalized == "css":
        return By.CSS_SELECTOR
    if normalized == "id":
        return By.ID
    if normalized == "name":
        return By.NAME
    raise ValueError(f"Unsupported selector strategy: {strategy}")


def wait_clickable(
    driver: WebDriver,
    xpath: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> WebElement:
    """Wait until an XPath-located element becomes clickable.

    Workflows use this helper for actions that must interact with the page
    rather than merely inspect it. Using a dedicated wait keeps click logic
    consistent across tools and reduces timing-related flakiness.
    """
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )


def wait_visible(
    driver: WebDriver,
    xpath: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> WebElement:
    """Wait until an XPath-located element becomes visible.

    Visibility is used as a stronger signal than mere presence when a workflow
    needs text or attributes from an element that should already be rendered to
    the user.
    """
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.XPATH, xpath))
    )


def is_xpath_present(driver: WebDriver, xpath: str) -> bool:
    """Return whether an XPath-located element exists on the page.

    This helper is intentionally lightweight and non-throwing so workflows can
    use it for capability checks and page-state snapshots.
    """
    return bool(driver.find_elements(By.XPATH, xpath))


def find_elements(
    driver: WebDriver,
    strategy: str,
    query: str,
) -> list[WebElement]:
    """Find elements using one of the supported selector strategies.

    This function is the common backend for agent-facing tools such as
    ``browser_find_elements`` and ``browser_click``. The workflow layer decides
    what to do with the returned elements; this helper only resolves them.
    """
    by = _by_from_strategy(strategy)
    return driver.find_elements(by, query)


def get_optional_text(driver: WebDriver, xpath: str) -> str | None:
    """Return stripped text for the first matching XPath element, if present.

    The helper deliberately returns ``None`` instead of raising when nothing is
    found. That makes it suitable for "is the success message visible yet?"
    style checks where absence is an expected state rather than an error.
    """
    elements = driver.find_elements(By.XPATH, xpath)
    if not elements:
        return None

    text = elements[0].text.strip()
    return text or None


def get_current_url(driver: WebDriver) -> str:
    """Return the current browser URL or an empty string if unavailable.

    Some cleanup/error paths run while the driver is unstable or already
    closing. Returning an empty string keeps result serialization robust.
    """
    try:
        return driver.current_url
    except Exception:
        return ""


def take_screenshot(
    driver: WebDriver,
    screenshot_dir: str,
    name: str,
) -> str | None:
    """Save a screenshot and return its filesystem path.

    Screenshots are treated as artifacts, not core business data. The caller
    decides whether a missing screenshot is fatal; this helper only performs
    the file write and reports success via the returned path.
    """
    output_dir = Path(screenshot_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = output_dir / f"{name}.png"

    saved = driver.save_screenshot(str(screenshot_path))
    if not saved:
        return None

    return str(screenshot_path)
