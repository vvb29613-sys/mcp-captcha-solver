"""reCAPTCHA v2 solver and demo-page shortcuts.

:func:`captcha_solve_recaptcha_v2` is the reusable primitive: it extracts the
sitekey from the page, asks the solver provider for a response token, and
injects that token back into the hidden ``g-recaptcha-response`` field.

The remaining tools — :func:`browser_get_page_state`,
:func:`browser_click_verify`, :func:`browser_extract_verification_json` — are
demo-page shortcuts that know the concrete submit button and verification
payload locations used by the test pages this repository ships against.
Generic pages should prefer the browser primitives from
:mod:`app.workflows.browser`.
"""

from __future__ import annotations

import json
from time import sleep

from selenium.webdriver.remote.webdriver import WebDriver

from app.browser.page_utils import (
    get_optional_text,
    is_xpath_present,
    wait_clickable,
    wait_visible,
)
from app.services.config import get_settings
from app.services.result_models import WorkflowResult
from app.services.session_store import BrowserSession
from app.services.solver_client import RecaptchaV2Request, TwoCaptchaSolver
from app.workflows._common import (
    result_for_session,
    save_verification_payload,
    with_session,
)

SITEKEY_XPATH = "//div[@data-sitekey]"
SUBMIT_BUTTON_XPATH = "//button[@data-action='demo_action']"
SUCCESS_MESSAGE_XPATH = "//p[contains(@class,'successMessage')]"
VERIFICATION_JSON_XPATH = "//pre"
RESPONSE_FIELD_ID = "g-recaptcha-response"
VERIFY_POLL_ATTEMPTS = 6
VERIFY_POLL_DELAY_SECONDS = 0.25


def _get_sitekey(driver: WebDriver) -> str:
    """Extract the reCAPTCHA sitekey from the current page.

    The sitekey is the public challenge identifier required by the solver
    service. Without it the workflow cannot request a response token. The
    selector targets any element that carries a ``data-sitekey`` attribute,
    which reflects what we actually need to read and is more robust than a
    strict class match.
    """
    sitekey_element = wait_visible(driver, SITEKEY_XPATH)
    sitekey = sitekey_element.get_attribute("data-sitekey")
    if not sitekey:
        raise RuntimeError("reCAPTCHA sitekey was not found on the page.")
    return sitekey


def _inject_token(driver: WebDriver, token: str) -> None:
    """Inject a solved reCAPTCHA token back into the page.

    Finds the hidden ``g-recaptcha-response`` field, writes the token into
    both ``value`` and ``innerHTML``, and dispatches a ``change`` event so the
    page scripts can react. This helper intentionally focuses only on token
    injection: it does not decide whether the agent should click a submit
    button afterwards.
    """
    driver.execute_script(
        """
        const responseField = document.getElementById(arguments[0]);
        if (!responseField) {
            throw new Error("reCAPTCHA response field was not found.");
        }

        responseField.value = arguments[1];
        responseField.innerHTML = arguments[1];
        responseField.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        RESPONSE_FIELD_ID,
        token,
    )


def _submit_demo_form(driver: WebDriver) -> None:
    """Click the known verification button on the current demo page.

    This helper exists only for demo-style pages where the continuation button
    is known in advance. More generic flows should use ``browser_click`` with
    a selector chosen by the agent.
    """
    wait_clickable(driver, SUBMIT_BUTTON_XPATH).click()


def _read_success_message(driver: WebDriver) -> str | None:
    """Return the current success message, if the page already shows one."""
    return get_optional_text(driver, SUCCESS_MESSAGE_XPATH)


def _read_verification_payload(driver: WebDriver) -> dict[str, object] | None:
    """Parse the currently visible verification JSON block.

    The helper is intentionally tolerant: missing blocks, invalid JSON, or JSON
    values that are not objects all resolve to ``None`` rather than raising.
    That makes it suitable for page polling during transitions.
    """
    raw_json = get_optional_text(driver, VERIFICATION_JSON_XPATH)
    if not raw_json:
        return None

    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    return payload


def _wait_for_verification_state(
    driver: WebDriver,
    attempts: int = VERIFY_POLL_ATTEMPTS,
    delay_seconds: float = VERIFY_POLL_DELAY_SECONDS,
) -> tuple[str | None, dict[str, object] | None]:
    """Poll the page for either a success banner or a verification payload.

    Browser transitions after captcha solving or submit clicks are often
    slightly delayed. Polling in one place keeps browser tools consistent and
    avoids duplicating timing logic.
    """
    last_success_message = _read_success_message(driver)
    last_payload = _read_verification_payload(driver)
    if last_success_message or last_payload:
        return last_success_message, last_payload

    for _ in range(attempts):
        sleep(delay_seconds)
        last_success_message = _read_success_message(driver)
        last_payload = _read_verification_payload(driver)
        if last_success_message or last_payload:
            break

    return last_success_message, last_payload


@with_session(error_screenshot_suffix="page-state-error")
def browser_get_page_state(session: BrowserSession) -> WorkflowResult:
    """Return a high-level view of the current page state.

    The tool summarizes a few useful signals (challenge presence, verify
    button, success message, payload visibility) and tailors the list of
    recommended next actions to what is actually on the page:

    - payload already visible → extract and close;
    - challenge present → solve the captcha first;
    - verify button present → click verify;
    - otherwise → the generic browser primitives.
    """
    verification_payload = _read_verification_payload(session.driver)
    success_message = _read_success_message(session.driver)
    challenge_present = is_xpath_present(session.driver, SITEKEY_XPATH)
    check_button_present = is_xpath_present(session.driver, SUBMIT_BUTTON_XPATH)

    if verification_payload is not None:
        recommended_next_actions = [
            "browser_extract_verification_json",
            "browser_close_page",
        ]
    else:
        recommended_next_actions = []
        if challenge_present:
            recommended_next_actions.append("captcha_solve_recaptcha_v2")
        if check_button_present:
            recommended_next_actions.append("browser_click_verify")
        recommended_next_actions.extend(
            [
                "browser_find_elements",
                "browser_click",
                "browser_extract_text",
                "browser_extract_json",
            ]
        )

    details = {
        "page_title": session.driver.title,
        "challenge_present": challenge_present,
        "check_button_present": check_button_present,
        "success_message_visible": bool(success_message),
        "verification_payload_present": verification_payload is not None,
        "recommended_next_actions": recommended_next_actions,
        "task_complete": verification_payload is not None,
        "should_retry": False,
        "should_close_session": False,
    }
    return result_for_session(
        session,
        "Current page state collected.",
        status="success",
        screenshot_suffix="page-state",
        verification_payload=verification_payload,
        details=details,
    )


@with_session(error_screenshot_suffix="verify-error", close_on_error=True)
def browser_click_verify(session: BrowserSession) -> WorkflowResult:
    """Click the known verify button and wait for page state to change.

    This is a convenience tool for demo-style pages whose submit action is
    already known. For more generic pages the preferred pattern is:
    ``browser_find_elements`` -> ``browser_click`` -> ``browser_extract_*``.
    """
    _submit_demo_form(session.driver)
    success_message, verification_payload = _wait_for_verification_state(session.driver)
    details = {
        "check_clicked": True,
        "success_message_visible": bool(success_message),
        "verification_payload_present": verification_payload is not None,
        "next_action": "Extract the verification JSON from the page.",
        "task_complete": verification_payload is not None,
        "should_retry": verification_payload is None,
        "should_close_session": False,
    }
    return result_for_session(
        session,
        success_message or "Verification button clicked successfully.",
        status="success",
        screenshot_suffix="verify-clicked",
        verification_payload=verification_payload,
        details=details,
    )


@with_session(error_screenshot_suffix="verification-json-error", close_on_error=True)
def browser_extract_verification_json(session: BrowserSession) -> WorkflowResult:
    """Extract and persist the verification JSON currently shown on the page.

    The success-path screenshot is treated as a key artifact and captured
    regardless of the ``CAPTURE_STEP_SCREENSHOTS`` flag.
    """
    _, verification_payload = _wait_for_verification_state(session.driver)
    if verification_payload is None:
        raise RuntimeError("Verification JSON is not visible on the page yet.")
    verification_result_path = save_verification_payload(
        verification_payload,
        session.session_id,
    )
    details = {
        "verification_payload_present": True,
        "success_message_visible": bool(_read_success_message(session.driver)),
        "task_complete": True,
        "should_retry": False,
        "should_close_session": False,
    }
    return result_for_session(
        session,
        "Verification JSON extracted from the page.",
        status="success",
        screenshot_suffix="verification-json",
        always_capture_screenshot=True,
        verification_payload=verification_payload,
        verification_result_path=verification_result_path,
        details=details,
    )


@with_session(error_screenshot_suffix="solve-error", close_on_error=True)
def captcha_solve_recaptcha_v2(session: BrowserSession) -> WorkflowResult:
    """Solve the reCAPTCHA v2 challenge currently blocking the page.

    Workflow boundary:
        This function only removes the captcha obstacle by extracting the
        sitekey, calling the solver provider, and injecting the token. It does
        not decide how the page should continue afterwards.
    """
    settings = get_settings()
    if not settings.two_captcha_api_key:
        raise RuntimeError("Set APIKEY_2CAPTCHA before running this workflow.")

    sitekey = _get_sitekey(session.driver)
    solver = TwoCaptchaSolver(settings.two_captcha_api_key)
    token = solver.solve_recaptcha_v2(
        RecaptchaV2Request(
            page_url=session.driver.current_url,
            sitekey=sitekey,
        )
    )
    _inject_token(session.driver, token)
    details = {
        "captcha_token_injected": True,
        "next_action": "Continue the task with browser tools on the current page.",
        "task_complete": False,
        "should_retry": False,
        "should_close_session": False,
    }
    return result_for_session(
        session,
        "reCAPTCHA token solved and injected into the page.",
        status="success",
        screenshot_suffix="solved",
        details=details,
    )
