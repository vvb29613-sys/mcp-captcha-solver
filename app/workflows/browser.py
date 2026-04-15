"""Generic browser tools exposed through MCP.

These functions do not know anything about reCAPTCHA or the demo submission
button: they are composable primitives the agent can apply to any page.
Captcha-aware shortcuts and the reCAPTCHA solver live in
:mod:`app.workflows.recaptcha_v2`.
"""

from __future__ import annotations

import json

from app.browser.driver_factory import create_driver
from app.browser.page_utils import find_elements
from app.services.config import get_settings
from app.services.result_models import WorkflowResult, error_result, success_result
from app.services.session_store import BrowserSession, session_store
from app.workflows._common import (
    CHALLENGE_TYPE,
    ELEMENT_PREVIEW_LIMIT,
    WORKFLOW_NAME,
    element_preview,
    result_for_session,
    save_verification_payload,
    selector_query,
    with_session,
)


def browser_open_page(page_url: str) -> WorkflowResult:
    """Open the requested page and return a browser session for the agent.

    The page URL is intentionally required. The agent should receive the
    target page from the user task rather than rely on a hidden default
    configured in the server environment.
    """
    settings = get_settings()
    try:
        driver = create_driver(settings)
        driver.get(page_url)
        session = session_store.create(
            driver=driver,
            workflow=WORKFLOW_NAME,
            challenge_type=CHALLENGE_TYPE,
            page_url=page_url,
        )
        details = {
            "next_action": "Inspect the page and choose the next browser or captcha tool.",
            "opened_page_url": page_url,
            "task_complete": False,
            "should_retry": False,
            "should_close_session": False,
        }
        return result_for_session(
            session,
            "Browser session started.",
            status="success",
            screenshot_suffix="started",
            details=details,
        )
    except Exception as error:
        return error_result(
            workflow=WORKFLOW_NAME,
            challenge_type=CHALLENGE_TYPE,
            page_url=page_url,
            message=str(error),
        )


@with_session(error_screenshot_suffix="find-elements-error")
def browser_find_elements(
    session: BrowserSession,
    strategy: str,
    query: str,
    limit: int = ELEMENT_PREVIEW_LIMIT,
) -> WorkflowResult:
    """Find elements on the current page using a supported selector strategy.

    This is a discovery primitive for the agent. It returns lightweight element
    previews instead of raw Selenium objects so the result can safely cross the
    MCP boundary.
    """
    resolved_strategy, resolved_query = selector_query(strategy, query)
    elements = find_elements(session.driver, resolved_strategy, resolved_query)
    previews = [
        element_preview(element)
        for element in elements[: max(1, min(limit, ELEMENT_PREVIEW_LIMIT))]
    ]
    details = {
        "selector_strategy": resolved_strategy,
        "selector_query": resolved_query,
        "match_count": len(elements),
        "elements": previews,
        "task_complete": False,
        "should_retry": False,
        "should_close_session": False,
    }
    return result_for_session(
        session,
        f"Found {len(elements)} matching element(s).",
        status="success",
        screenshot_suffix="find-elements",
        details=details,
    )


@with_session(error_screenshot_suffix="click-error")
def browser_click(
    session: BrowserSession,
    strategy: str,
    query: str,
    index: int = 0,
) -> WorkflowResult:
    """Click an element on the current page.

    The agent supplies the selector and optional match index. This tool keeps
    the actual click inside Selenium while the decision about *what* to click
    stays with the agent.
    """
    resolved_strategy, resolved_query = selector_query(strategy, query)
    elements = find_elements(session.driver, resolved_strategy, resolved_query)
    if not elements:
        raise RuntimeError("No matching element found for click action.")
    if index < 0 or index >= len(elements):
        raise RuntimeError(f"Click index out of range: {index}")

    target = elements[index]
    target.click()
    details = {
        "selector_strategy": resolved_strategy,
        "selector_query": resolved_query,
        "clicked_index": index,
        "clicked_element": element_preview(target),
        "task_complete": False,
        "should_retry": False,
        "should_close_session": False,
    }
    return result_for_session(
        session,
        "Element clicked successfully.",
        status="success",
        screenshot_suffix="click",
        details=details,
    )


@with_session(error_screenshot_suffix="extract-text-error")
def browser_extract_text(
    session: BrowserSession,
    strategy: str,
    query: str,
    index: int = 0,
) -> WorkflowResult:
    """Extract text from a matching element on the current page.

    This is useful for reading labels, messages, or result text on arbitrary
    pages after the captcha obstacle has been removed.
    """
    resolved_strategy, resolved_query = selector_query(strategy, query)
    elements = find_elements(session.driver, resolved_strategy, resolved_query)
    if not elements:
        raise RuntimeError("No matching element found for text extraction.")
    if index < 0 or index >= len(elements):
        raise RuntimeError(f"Extraction index out of range: {index}")

    target = elements[index]
    extracted_text = (target.text or "").strip()
    details = {
        "selector_strategy": resolved_strategy,
        "selector_query": resolved_query,
        "selected_index": index,
        "text": extracted_text,
        "element": element_preview(target),
        "task_complete": False,
        "should_retry": False,
        "should_close_session": False,
    }
    return result_for_session(
        session,
        "Text extracted from the page.",
        status="success",
        screenshot_suffix="extract-text",
        details=details,
    )


@with_session(error_screenshot_suffix="extract-json-error")
def browser_extract_json(
    session: BrowserSession,
    strategy: str,
    query: str,
    index: int = 0,
) -> WorkflowResult:
    """Extract JSON from a matching element on the current page.

    The function composes :func:`browser_extract_text` and JSON parsing so the
    agent can ask for structured output without re-implementing parsing logic.

    The tool intentionally does not claim overall task completion: it only
    reports that a JSON object was successfully read. Whether that payload
    satisfies the agent's goal is decided by the orchestration layer.
    """
    resolved_strategy, resolved_query = selector_query(strategy, query)
    text_result = browser_extract_text(session.session_id, strategy, query, index)
    if text_result.status == "error":
        return text_result

    extracted_text = None
    if text_result.details is not None:
        extracted_text = text_result.details.get("text")
    if not extracted_text:
        raise RuntimeError("Selected element does not contain JSON text.")

    payload = json.loads(str(extracted_text))
    if not isinstance(payload, dict):
        raise RuntimeError("Extracted JSON value is not an object.")

    verification_result_path = save_verification_payload(payload, session.session_id)
    details = {
        "selector_strategy": resolved_strategy,
        "selector_query": resolved_query,
        "verification_payload_present": True,
        "task_complete": False,
        "should_retry": False,
        "should_close_session": False,
    }
    return result_for_session(
        session,
        "JSON extracted from the page.",
        status="success",
        screenshot_suffix="extract-json",
        verification_payload=payload,
        verification_result_path=verification_result_path,
        details=details,
    )


def browser_close_page(session_id: str) -> WorkflowResult:
    """Close an active browser session.

    The returned result is still normalized so agents can treat cleanup as part
    of the same result protocol used for every other tool.
    """
    try:
        session = session_store.close(session_id)
        return success_result(
            workflow=WORKFLOW_NAME,
            challenge_type=CHALLENGE_TYPE,
            page_url=session.page_url,
            message="Browser session closed.",
            session_id=session_id,
            details={
                "closed": True,
                "task_complete": False,
                "should_retry": False,
                "should_close_session": False,
            },
        )
    except Exception as error:
        return error_result(
            workflow=WORKFLOW_NAME,
            challenge_type=CHALLENGE_TYPE,
            page_url="",
            message=str(error),
            session_id=session_id,
        )


def browser_close_page_on_error(session_id: str, reason: str) -> WorkflowResult:
    """Close the current browser session when the agent cannot continue.

    The explicit ``reason`` helps preserve context in the normalized result so
    later debugging does not lose the agent's rationale for stopping.
    """
    closed = browser_close_page(session_id)
    if closed.status == "success":
        closed.message = f"Browser session closed after unrecoverable error: {reason}"
        if closed.details is None:
            closed.details = {}
        closed.details["closed_due_to_error"] = True
        closed.details["reason"] = reason
        closed.details["task_complete"] = False
        closed.details["should_retry"] = False
        closed.details["should_close_session"] = False
    return closed
