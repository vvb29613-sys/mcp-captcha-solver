"""Adapters for captcha-solving providers used by workflows.

Provider-specific API calls stay here so workflow code can talk in terms of
captcha requests and response tokens instead of SDK-specific objects.
"""

from __future__ import annotations

from dataclasses import dataclass

from twocaptcha import TwoCaptcha


@dataclass(slots=True)
class RecaptchaV2Request:
    """Parameters required to solve a reCAPTCHA v2 challenge.

    The request intentionally contains only the minimum data needed by the
    provider: the page URL and the public sitekey extracted from the page.
    """

    page_url: str
    sitekey: str


class TwoCaptchaSolver:
    """Thin adapter around the 2Captcha client.

    Why this exists:
        Direct use of the vendor SDK inside workflow code would couple browser
        logic to one provider implementation. This adapter keeps that boundary
        narrow and makes later substitution easier.
    """

    def __init__(self, api_key: str) -> None:
        self._client = TwoCaptcha(api_key)

    def solve_recaptcha_v2(self, request: RecaptchaV2Request) -> str:
        """Return the response token for a reCAPTCHA v2 challenge.

        The workflow later injects the returned token back into the page. This
        method does not perform any Selenium work; it only talks to the solver.
        """
        result = self._client.recaptcha(
            sitekey=request.sitekey,
            url=request.page_url,
        )
        return str(result["code"])
