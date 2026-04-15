"""MCP server exposing browser and generic reCAPTCHA v2 capabilities.

This module is intentionally thin. It should not contain Selenium logic or
page-specific reasoning; it only maps MCP tool calls to workflow functions and
converts returned dataclasses to plain dictionaries.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.services.workflow_catalog import (
    list_all_tool_names,
    list_available_workflows as catalog_workflows,
)
from app.workflows.browser import (
    browser_click as browser_click_workflow,
    browser_close_page as browser_close_page_workflow,
    browser_close_page_on_error as browser_close_page_on_error_workflow,
    browser_extract_json as browser_extract_json_workflow,
    browser_extract_text as browser_extract_text_workflow,
    browser_find_elements as browser_find_elements_workflow,
    browser_open_page as browser_open_page_workflow,
)
from app.workflows.recaptcha_v2 import (
    browser_click_verify as browser_click_verify_workflow,
    browser_extract_verification_json as browser_extract_verification_json_workflow,
    browser_get_page_state as browser_get_page_state_workflow,
    captcha_solve_recaptcha_v2 as captcha_solve_recaptcha_v2_workflow,
)

SERVER_NAME = "mcp-captcha-demo"

mcp = FastMCP(SERVER_NAME)


@mcp.tool()
def healthcheck() -> dict[str, object]:
    """Return a minimal status payload for local MCP server checks.

    Agents can call this first to confirm that the server is alive and to see
    which tools are currently exposed without running any browser automation.
    """
    return {
        "status": "ok",
        "server": SERVER_NAME,
        "available_tools": list_all_tool_names(),
    }


@mcp.tool()
def list_available_workflows() -> list[dict[str, str]]:
    """List tool metadata exposed by this server.

    Unlike ``healthcheck``, this returns richer descriptions intended to help
    the agent choose between browser and captcha capabilities.
    """
    return catalog_workflows()


@mcp.tool()
def browser_open_page(page_url: str) -> dict[str, object | None]:
    """Open a page URL and start a browser session.

    This is the typical first call in an agent-driven flow. The resulting
    ``session_id`` is then used by all later browser and captcha tools.
    """
    return browser_open_page_workflow(page_url).to_dict()


@mcp.tool()
def browser_get_page_state(session_id: str) -> dict[str, object | None]:
    """Inspect the current browser state.

    The tool returns a compact snapshot rather than raw DOM so the agent can
    decide on the next step without scraping everything itself.
    """
    return browser_get_page_state_workflow(session_id).to_dict()


@mcp.tool()
def browser_find_elements(
    session_id: str,
    strategy: str,
    query: str,
    limit: int = 5,
) -> dict[str, object | None]:
    """Find candidate elements on the current page.

    This is a discovery tool. It helps the agent reason about likely buttons,
    fields, or result blocks before committing to a click or extraction.
    """
    return browser_find_elements_workflow(session_id, strategy, query, limit).to_dict()


@mcp.tool()
def browser_click(
    session_id: str,
    strategy: str,
    query: str,
    index: int = 0,
) -> dict[str, object | None]:
    """Click an element on the current page.

    The agent provides a selector strategy and query; the workflow resolves the
    element and performs the click in the active session.
    """
    return browser_click_workflow(session_id, strategy, query, index).to_dict()


@mcp.tool()
def browser_extract_text(
    session_id: str,
    strategy: str,
    query: str,
    index: int = 0,
) -> dict[str, object | None]:
    """Extract text from a matching element on the current page.

    This is useful for reading labels, success messages, or intermediate page
    state without hardcoding page-specific scraping logic into the MCP layer.
    """
    return browser_extract_text_workflow(session_id, strategy, query, index).to_dict()


@mcp.tool()
def browser_extract_json(
    session_id: str,
    strategy: str,
    query: str,
    index: int = 0,
) -> dict[str, object | None]:
    """Extract JSON from a matching element on the current page.

    The underlying workflow parses text content, validates that it is a JSON
    object, and stores it as an artifact when successful.
    """
    return browser_extract_json_workflow(session_id, strategy, query, index).to_dict()


@mcp.tool()
def browser_click_verify(session_id: str) -> dict[str, object | None]:
    """Click the known verify/submit button for the current demo shortcut flow.

    This is a convenience tool kept for the current demo pages. More generic
    agent behavior should prefer ``browser_find_elements`` plus ``browser_click``.
    """
    return browser_click_verify_workflow(session_id).to_dict()


@mcp.tool()
def browser_extract_verification_json(session_id: str) -> dict[str, object | None]:
    """Extract the visible verification JSON for the current demo shortcut flow.

    Like ``browser_click_verify``, this is a convenience tool for demo pages
    that expose a dedicated result block.
    """
    return browser_extract_verification_json_workflow(session_id).to_dict()


@mcp.tool()
def browser_close_page(session_id: str) -> dict[str, object | None]:
    """Close an active browser session.

    Agents should call this when a task succeeds or when they decide to stop
    using the current page.
    """
    return browser_close_page_workflow(session_id).to_dict()


@mcp.tool()
def browser_close_page_on_error(session_id: str, reason: str) -> dict[str, object | None]:
    """Close the current browser session when the agent cannot continue.

    This explicit error-cleanup tool makes agent behavior more disciplined:
    close the broken session first, then decide whether a retry is warranted.
    """
    return browser_close_page_on_error_workflow(session_id, reason).to_dict()


@mcp.tool()
def captcha_solve_recaptcha_v2(session_id: str) -> dict[str, object | None]:
    """Solve the reCAPTCHA v2 challenge on the current page.

    This tool only removes the captcha obstacle. It does not decide how the
    broader page flow should continue after the token is injected.
    """
    return captcha_solve_recaptcha_v2_workflow(session_id).to_dict()


def main() -> None:
    """Run the MCP server over the default stdio transport."""
    mcp.run()


if __name__ == "__main__":
    main()
