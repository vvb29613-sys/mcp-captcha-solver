"""In-memory store for browser sessions managed through MCP tools.

The agent interacts with the project through multiple coarse-grained tools.
Those tools need to operate on the same live browser between calls, which is
why this module owns session registration and lifecycle cleanup.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from selenium.webdriver.remote.webdriver import WebDriver

from app.browser.driver_factory import safe_quit


@dataclass(slots=True)
class BrowserSession:
    """Live browser session metadata.

    A session record ties together:
    - a generated ``session_id`` used by agents and MCP tools,
    - the actual Selenium driver instance,
    - workflow metadata that helps normalize results and debugging output.
    """

    session_id: str
    driver: WebDriver
    workflow: str
    challenge_type: str
    page_url: str


class SessionStore:
    """In-memory session registry for local runs.

    Why this exists:
        MCP tools are stateless function calls from the agent's perspective,
        but browser automation is inherently stateful. The store bridges those
        two worlds by mapping ``session_id`` values to live Selenium drivers.

    Concurrency scope:
        The registry itself (``create`` / ``get`` / ``close``) is guarded by a
        lock and is safe to call from multiple threads. The ``WebDriver``
        instances it hands out are **not** thread-safe: concurrent calls
        against the same ``session_id`` must be serialized by the caller. The
        stdio MCP transport sends requests sequentially in practice, so this
        is only a concern if the server is adapted to parallel transports.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}
        self._lock = Lock()

    def create(
        self,
        driver: WebDriver,
        workflow: str,
        challenge_type: str,
        page_url: str,
    ) -> BrowserSession:
        """Register a new browser session and return its metadata.

        Called immediately after a new driver is created and a page is opened.
        The returned ``BrowserSession`` is what tool implementations keep using
        until the agent closes the session or an unrecoverable error does it.
        """
        session = BrowserSession(
            session_id=uuid4().hex,
            driver=driver,
            workflow=workflow,
            challenge_type=challenge_type,
            page_url=page_url,
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> BrowserSession:
        """Return an active session or raise an informative error.

        Tools should fail loudly and clearly when an agent references a stale
        or unknown ``session_id``. A missing session usually means the browser
        was already closed or the agent retried incorrectly.
        """
        with self._lock:
            session = self._sessions.get(session_id)

        if session is None:
            raise KeyError(f"Unknown browser session: {session_id}")
        return session

    def close(self, session_id: str) -> BrowserSession:
        """Close and remove an active browser session.

        Session removal and browser shutdown happen together so callers never
        have to remember two separate cleanup steps.
        """
        with self._lock:
            session = self._sessions.pop(session_id, None)

        if session is None:
            raise KeyError(f"Unknown browser session: {session_id}")

        safe_quit(session.driver)
        return session


session_store = SessionStore()
