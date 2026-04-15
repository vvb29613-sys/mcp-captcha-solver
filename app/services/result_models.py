"""Structured result models returned by workflows and MCP tools.

The whole project relies on a normalized result shape so that:
- workflows can communicate success/error states consistently,
- MCP tools can forward results without custom translation logic,
- agents can reason about outcomes without scraping human-oriented text.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from typing import Literal


RunStatus = Literal["success", "error"]


@dataclass(slots=True)
class WorkflowResult:
    """Normalized result returned by workflows and MCP tools.

    Design intent:
        ``WorkflowResult`` is the contract between the execution layer
        (Selenium/workflows) and the orchestration layer (MCP tools/agents).
        The model therefore carries both user-facing summary data and optional
        machine-friendly details such as session lifecycle hints or extracted
        verification payloads.
    """

    status: RunStatus
    workflow: str
    challenge_type: str
    page_url: str
    message: str
    session_id: str | None = None
    screenshot_path: str | None = None
    verification_payload: dict[str, Any] | None = None
    verification_result_path: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation.

        MCP tools expose plain dictionaries, so workflows convert dataclasses
        at the boundary rather than leaking Python-specific objects upward.
        """
        return asdict(self)


def success_result(
    workflow: str,
    challenge_type: str,
    page_url: str,
    message: str,
    session_id: str | None = None,
    screenshot_path: str | None = None,
    verification_payload: dict[str, Any] | None = None,
    verification_result_path: str | None = None,
    details: dict[str, Any] | None = None,
) -> WorkflowResult:
    """Build a successful workflow result.

    This helper keeps success result creation visually compact and guarantees
    that all success paths use the same normalized shape.
    """
    return WorkflowResult(
        status="success",
        workflow=workflow,
        challenge_type=challenge_type,
        page_url=page_url,
        message=message,
        session_id=session_id,
        screenshot_path=screenshot_path,
        verification_payload=verification_payload,
        verification_result_path=verification_result_path,
        details=details,
    )


def error_result(
    workflow: str,
    challenge_type: str,
    page_url: str,
    message: str,
    session_id: str | None = None,
    screenshot_path: str | None = None,
    verification_payload: dict[str, Any] | None = None,
    verification_result_path: str | None = None,
    details: dict[str, Any] | None = None,
) -> WorkflowResult:
    """Build an error workflow result.

    Error results intentionally have the same shape as success results so
    callers can inspect one contract regardless of outcome.
    """
    return WorkflowResult(
        status="error",
        workflow=workflow,
        challenge_type=challenge_type,
        page_url=page_url,
        message=message,
        session_id=session_id,
        screenshot_path=screenshot_path,
        verification_payload=verification_payload,
        verification_result_path=verification_result_path,
        details=details,
    )
