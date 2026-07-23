"""Option B: fetch vaulted GitHub OAuth via AgentCore Identity (USER_FEDERATION)."""

from __future__ import annotations

import os

from bedrock_agentcore.identity.auth import requires_access_token

_DEFAULT_RETURN_URL = "http://localhost:8501/"


def oauth2_return_url() -> str:
    return os.getenv(
        "AGENTCORE_OAUTH2_RETURN_URL",
        os.getenv("GITHUB_REDIRECT_URI", _DEFAULT_RETURN_URL),
    ).strip() or _DEFAULT_RETURN_URL


def _fail_closed_on_auth_url(auth_url: str) -> None:
    """Agent cannot complete browser 3LO; user must Connect GitHub in the UI first."""
    raise RuntimeError(
        "GitHub OAuth not ready for this agent session "
        "(Identity returned an authorizationUrl). "
        "Connect GitHub in the UI for this Cognito user, then retry. "
        f"url_prefix={auth_url[:64]!r}"
    )


@requires_access_token(
    provider_name=os.getenv("AGENTCORE_GITHUB_PROVIDER", "pilllar-6-github"),
    scopes=[
        s
        for s in os.getenv("GITHUB_OAUTH_SCOPES", "read:user repo")
        .replace(",", " ")
        .split()
        if s
    ],
    auth_flow="USER_FEDERATION",
    # Identity requires ResourceOauth2ReturnUrl for USER_FEDERATION (even vault hits).
    # Must be listed on the Runtime workload's allowedResourceOauth2ReturnUrls.
    callback_url=os.getenv(
        "AGENTCORE_OAUTH2_RETURN_URL",
        os.getenv("GITHUB_REDIRECT_URI", _DEFAULT_RETURN_URL),
    )
    or _DEFAULT_RETURN_URL,
    on_auth_url=_fail_closed_on_auth_url,
    force_authentication=False,
)
async def fetch_github_access_token(*, access_token: str) -> str:
    """Return vaulted GitHub user access token for the current Runtime workload user."""
    return access_token
