"""Resolve GitHub OAuth for Gateway tool forward (Option A).

Prefer UI-forwarded token (UI workload vault) over Runtime Identity fetch,
because Connect GitHub stores tokens under githubWorkflowUi — not the
Runtime service-linked workload.
"""

from __future__ import annotations

import logging
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreContext

from github_oauth import fetch_github_access_token

logger = logging.getLogger(__name__)

GITHUB_TOKEN_HEADER_SUFFIX = "github-access-token"


def token_from_headers(headers: dict[str, str] | None) -> str | None:
    if not headers:
        return None
    for key, value in headers.items():
        if GITHUB_TOKEN_HEADER_SUFFIX in key.lower() and value:
            return str(value).strip()
    return None


async def resolve_github_token_async(payload: dict[str, Any], context: Any) -> str | None:
    """Return GitHub OAuth access token for this invoke, or None."""
    ctx_headers = BedrockAgentCoreContext.get_request_headers() or {}
    req_headers = getattr(context, "request_headers", None) or {}
    token = token_from_headers({**ctx_headers, **req_headers})
    if token:
        logger.info("GitHub OAuth from Runtime custom header (UI forward)")
        return token

    session = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    raw = payload.get("github_access_token") or session.get("github_access_token")
    if raw:
        logger.info("GitHub OAuth from invoke payload")
        return str(raw).strip()

    try:
        token = await fetch_github_access_token()
        logger.info("GitHub OAuth from Runtime Identity USER_FEDERATION")
        return token
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "GitHub OAuth unavailable (Connect GitHub in UI + forward header): %s",
            exc,
        )
        return None
