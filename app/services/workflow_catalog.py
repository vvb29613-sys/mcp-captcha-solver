"""Single source of truth for the agent-facing tool catalog.

Both ``healthcheck`` and ``list_available_workflows`` in the MCP server derive
their output from the lists defined here, so adding or renaming an MCP tool
requires editing exactly one place. This is what prevents the three lists from
silently drifting out of sync, which had already happened once when
``browser_close_page_on_error`` was added only to part of the surface.
"""

from __future__ import annotations


META_TOOL_NAMES: list[str] = [
    "healthcheck",
    "list_available_workflows",
]


TOOL_CATALOG: list[dict[str, str]] = [
    {
        "tool_name": "browser_open_page",
        "category": "browser",
        "description": "Open the requested page URL and return a browser session.",
        "demo_page_url": "Any URL provided by the agent",
    },
    {
        "tool_name": "browser_get_page_state",
        "category": "browser",
        "description": "Inspect the current page state so the agent can decide what to do next.",
        "demo_page_url": "Current browser page",
    },
    {
        "tool_name": "browser_find_elements",
        "category": "browser",
        "description": "Find candidate elements on the current page using xpath/css/id/name/text lookup.",
        "demo_page_url": "Current browser page",
    },
    {
        "tool_name": "browser_click",
        "category": "browser",
        "description": "Click an element on the current page using xpath/css/id/name/text lookup.",
        "demo_page_url": "Current browser page",
    },
    {
        "tool_name": "browser_extract_text",
        "category": "browser",
        "description": "Extract text from a matching element on the current page.",
        "demo_page_url": "Current browser page",
    },
    {
        "tool_name": "browser_extract_json",
        "category": "browser",
        "description": "Extract JSON from a matching element on the current page and persist it as an artifact.",
        "demo_page_url": "Current browser page",
    },
    {
        "tool_name": "browser_click_verify",
        "category": "browser",
        "description": "Press the known verification button on the current page.",
        "demo_page_url": "Current browser page",
    },
    {
        "tool_name": "browser_extract_verification_json",
        "category": "browser",
        "description": "Extract the final verification JSON currently visible on the page.",
        "demo_page_url": "Current browser page",
    },
    {
        "tool_name": "browser_close_page",
        "category": "browser",
        "description": "Close the active browser session.",
        "demo_page_url": "Current browser page",
    },
    {
        "tool_name": "browser_close_page_on_error",
        "category": "browser",
        "description": "Close the active browser session when the agent cannot continue after an error.",
        "demo_page_url": "Current browser page",
    },
    {
        "tool_name": "captcha_solve_recaptcha_v2",
        "category": "captcha",
        "description": "Solve the reCAPTCHA v2 challenge on the current page.",
        "demo_page_url": "Current browser page",
    },
]


def list_available_workflows() -> list[dict[str, str]]:
    """Return metadata for the agent-facing capability surface.

    The catalog is intentionally descriptive rather than executable. It helps
    agents or humans inspect which tool groups exist without reading the server
    implementation directly.
    """
    return list(TOOL_CATALOG)


def list_all_tool_names() -> list[str]:
    """Return every MCP tool name the server exposes, in declaration order.

    Used by ``healthcheck`` so its compact status response cannot drift out of
    sync with :data:`TOOL_CATALOG`. Meta tools that are not workflow capabilities
    (``healthcheck``, ``list_available_workflows``) are prepended here since the
    workflow catalog intentionally omits them.
    """
    return META_TOOL_NAMES + [tool["tool_name"] for tool in TOOL_CATALOG]
