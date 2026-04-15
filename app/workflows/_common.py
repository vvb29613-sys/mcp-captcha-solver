"""Shared helpers used by the workflow modules.

The ``app.workflows`` package is split into two agent-facing modules:

- :mod:`app.workflows.browser` — generic page-agnostic primitives,
- :mod:`app.workflows.recaptcha_v2` — reCAPTCHA v2 solver and demo shortcuts.

Both modules share the same result envelope, artifact-naming convention, and
session-error decorator. Keeping them here avoids either module depending on
the other just for plumbing and is the ``_common.py`` that was extracted when
the original ``demo_recaptcha_v2.py`` was split.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

from selenium.webdriver.remote.webelement import WebElement

from app.browser.page_utils import get_current_url, take_screenshot
from app.services.config import get_settings
from app.services.result_models import (
    RunStatus,
    WorkflowResult,
    error_result,
    success_result,
)
from app.services.session_store import BrowserSession, session_store

WORKFLOW_NAME = "browser_recaptcha_tools"
CHALLENGE_TYPE = "recaptcha_v2"
ELEMENT_PREVIEW_LIMIT = 5


def build_artifact_name(suffix: str, session_id: str | None = None) -> str:
    """Build a filesystem-friendly artifact name.

    Artifacts such as screenshots and extracted JSON payloads are produced in
    many tools. Centralizing naming keeps them easy to correlate by workflow,
    session, and timestamp.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if session_id:
        return f"{WORKFLOW_NAME}-{session_id}-{suffix}-{timestamp}"
    return f"{WORKFLOW_NAME}-{suffix}-{timestamp}"


def selector_query(strategy: str, value: str) -> tuple[str, str]:
    """Normalize selector input and support simple text lookup.

    The public browser tools let the agent use ``text`` as a convenience
    strategy. Internally Selenium still needs XPath/CSS/ID/NAME, so this helper
    rewrites ``text`` into an XPath ``contains`` query and leaves other
    strategies unchanged.
    """
    normalized = strategy.lower().strip()
    if normalized == "text":
        escaped = value.replace('"', '\\"')
        return "xpath", f"//*[contains(normalize-space(.), \"{escaped}\")]"
    return normalized, value


def element_preview(element: WebElement) -> dict[str, str | None]:
    """Return a compact, agent-friendly description of an element.

    The goal is not to serialize the entire DOM node, only enough identifying
    information for an agent or developer to understand what was found.
    """
    tag_name = getattr(element, "tag_name", None)
    text = (element.text or "").strip() or None
    return {
        "tag": tag_name,
        "text": text,
        "id": element.get_attribute("id"),
        "name": element.get_attribute("name"),
        "type": element.get_attribute("type"),
        "class": element.get_attribute("class"),
    }


def session_screenshot(
    session: BrowserSession,
    suffix: str,
    *,
    always_capture: bool = False,
) -> str | None:
    """Capture a screenshot for the active session.

    Screenshots are best-effort artifacts. The caller decides whether a
    screenshot is worth taking for this particular step (errors, key
    verification artifacts) by passing ``always_capture=True``; otherwise the
    global ``CAPTURE_STEP_SCREENSHOTS`` flag governs step-tracking screenshots.
    """
    settings = get_settings()
    if not (always_capture or settings.capture_step_screenshots):
        return None
    try:
        return take_screenshot(
            session.driver,
            settings.screenshot_dir,
            build_artifact_name(suffix, session.session_id),
        )
    except Exception:
        logger.debug(
            "screenshot capture failed for session %s (suffix=%s)",
            session.session_id,
            suffix,
            exc_info=True,
        )
        return None


def save_verification_payload(payload: dict[str, object], session_id: str) -> str:
    """Persist a JSON payload under the project's result directory.

    Useful for debugging, article screenshots, or agent outputs that should
    reference a concrete artifact path instead of embedding every payload
    inline in the MCP response.
    """
    settings = get_settings()
    output_dir = Path(settings.result_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{build_artifact_name('verification', session_id)}.json"
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(output_path)


def result_for_session(
    session: BrowserSession,
    message: str,
    *,
    status: RunStatus,
    screenshot_suffix: str,
    always_capture_screenshot: bool = False,
    verification_payload: dict[str, object] | None = None,
    verification_result_path: str | None = None,
    details: dict[str, object] | None = None,
) -> WorkflowResult:
    """Build a normalized result tied to an active browser session.

    Most workflow functions need to return the same envelope: current URL,
    session id, optional screenshot, optional payload, and a normalized
    success/error status. Centralizing that logic keeps the tool
    implementations focused on the page action itself.
    """
    screenshot_path = session_screenshot(
        session, screenshot_suffix, always_capture=always_capture_screenshot
    )
    result_factory = success_result if status == "success" else error_result
    return result_factory(
        workflow=WORKFLOW_NAME,
        challenge_type=CHALLENGE_TYPE,
        page_url=get_current_url(session.driver),
        message=message,
        session_id=session.session_id,
        screenshot_path=screenshot_path,
        verification_payload=verification_payload,
        verification_result_path=verification_result_path,
        details=details,
    )


def with_session(
    *,
    error_screenshot_suffix: str,
    close_on_error: bool = False,
) -> Callable[[Callable[..., WorkflowResult]], Callable[..., WorkflowResult]]:
    """Wrap a session-bound workflow step with consistent error handling.

    Almost every public workflow function used to repeat the same skeleton:
    look up the session, run the step, capture a screenshot on failure,
    optionally close the session, and return a normalized error envelope. The
    decorator centralizes that envelope so individual tools only contain their
    page-specific logic.

    - Decorate a function whose first positional argument is a live
      :class:`BrowserSession`; the wrapper exposes the public signature that
      takes ``session_id: str`` and resolves it into a session.
    - ``close_on_error=True`` should be used for unrecoverable failures where
      the agent must not retry on the same session (captcha solve, final
      verification steps).
    """

    def decorator(
        func: Callable[..., WorkflowResult],
    ) -> Callable[..., WorkflowResult]:
        @wraps(func)
        def wrapper(session_id: str, *args: Any, **kwargs: Any) -> WorkflowResult:
            try:
                session = session_store.get(session_id)
            except Exception as lookup_error:
                return error_result(
                    workflow=WORKFLOW_NAME,
                    challenge_type=CHALLENGE_TYPE,
                    page_url="",
                    message=str(lookup_error),
                    session_id=session_id,
                    details={
                        "task_complete": False,
                        "should_retry": False,
                        "should_close_session": False,
                    },
                )
            try:
                return func(session, *args, **kwargs)
            except Exception as step_error:
                screenshot_path = session_screenshot(
                    session, error_screenshot_suffix, always_capture=True
                )
                page_url = get_current_url(session.driver)
                details: dict[str, object] = {
                    "task_complete": False,
                    "should_retry": not close_on_error,
                    "should_close_session": close_on_error,
                }
                if close_on_error:
                    try:
                        session_store.close(session_id)
                        details["session_closed"] = True
                    except Exception:
                        logger.debug(
                            "session_store.close failed for %s during error cleanup",
                            session_id,
                            exc_info=True,
                        )
                return error_result(
                    workflow=WORKFLOW_NAME,
                    challenge_type=CHALLENGE_TYPE,
                    page_url=page_url,
                    message=str(step_error),
                    session_id=session_id,
                    screenshot_path=screenshot_path,
                    details=details,
                )

        return wrapper

    return decorator
