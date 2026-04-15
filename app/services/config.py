"""Project configuration loaded from environment variables.

All environment access is centralized here so the rest of the codebase can
depend on a small typed settings object instead of calling ``os.getenv`` in
many places.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_under_project_root(value: str) -> str:
    """Expand a relative artifact path against the project root.

    Artifact paths in ``.env`` are written in their natural relative form
    (``artifacts/screenshots``). The MCP server may be launched from any
    working directory, so the path is anchored to the project root here.
    Absolute paths are returned unchanged.
    """
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return str(candidate)


@dataclass(slots=True)
class Settings:
    """Runtime settings for local execution.

    The project is still intentionally local-first. These fields describe the
    browser runtime, artifact output locations, and solver credentials.
    """

    browser_name: str = "chrome"
    browser_headless: bool = False
    screenshot_dir: str = "artifacts/screenshots"
    result_dir: str = "artifacts/results"
    capture_step_screenshots: bool = False
    two_captcha_api_key: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings from environment variables with sensible defaults.

    Why this exists:
        Most modules should not know or care which environment variable names
        back a setting. They just need a typed ``Settings`` object.

    How it works:
        - Reads known variables from ``os.environ`` exactly once per process.
        - Applies local-friendly defaults for omitted values.
        - Resolves artifact directories relative to the project root so the
          server behaves the same regardless of the caller's working dir.
    """
    return Settings(
        browser_name=os.getenv("BROWSER_NAME", "chrome"),
        browser_headless=os.getenv("BROWSER_HEADLESS", "").lower() in {"1", "true", "yes"},
        screenshot_dir=_resolve_under_project_root(
            os.getenv("SCREENSHOT_DIR", "artifacts/screenshots")
        ),
        result_dir=_resolve_under_project_root(
            os.getenv("RESULT_DIR", "artifacts/results")
        ),
        capture_step_screenshots=os.getenv("CAPTURE_STEP_SCREENSHOTS", "").lower()
        in {"1", "true", "yes"},
        two_captcha_api_key=os.getenv("APIKEY_2CAPTCHA"),
    )
