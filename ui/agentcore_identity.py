"""AgentCore Identity: Cognito JWT → workload token + GitHub USER_FEDERATION (D1-B/C).

Inbound JWT authorizer on the Runtime validates Cognito tokens at the door.
GetWorkloadAccessTokenForJWT exchanges a Cognito access token for a workload
token. Connect GitHub uses GetResourceOauth2Token (USER_FEDERATION) +
CompleteResourceTokenAuth on the Streamlit return URL.

UI/pre-deploy workload: AGENTCORE_WORKLOAD_NAME (default githubWorkflowUi) must
list the Streamlit URL in allowedResourceOauth2ReturnUrls.
"""

from __future__ import annotations

import os
import urllib.parse
from pathlib import Path
from typing import Any

import boto3
import requests
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env.shared", override=True)


def _region() -> str:
    return os.environ["AWS_REGION"]


def _dp():
    return boto3.client("bedrock-agentcore", region_name=_region())


def cognito_discovery_url() -> str:
    region = _region()
    pool = os.environ["COGNITO_USER_POOL_ID"]
    return (
        f"https://cognito-idp.{region}.amazonaws.com/{pool}"
        "/.well-known/openid-configuration"
    )


def jwt_authorizer_config() -> dict[str, Any]:
    """Same shape as githubpoc/agentcore/agentcore.json runtime JWT (D1-B1)."""
    return {
        "customJwtAuthorizer": {
            "discoveryUrl": cognito_discovery_url(),
            "allowedAudience": [os.environ["COGNITO_APP_CLIENT_ID"]],
        }
    }


def workload_name() -> str:
    # githubWorkflowUi has localhost return URL for 3LO session binding (D1-C)
    return os.getenv("AGENTCORE_WORKLOAD_NAME", "githubWorkflowUi").strip()


def github_provider_name() -> str:
    return os.getenv("AGENTCORE_GITHUB_PROVIDER", "pilllar-6-github").strip()


def oauth2_return_url() -> str:
    return os.getenv(
        "AGENTCORE_OAUTH2_RETURN_URL",
        os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8501/"),
    ).strip()


def github_scopes() -> list[str]:
    raw = os.getenv("GITHUB_OAUTH_SCOPES", "read:user repo").strip()
    return [s for s in raw.replace(",", " ").split() if s]


def runtime_arn() -> str | None:
    arn = os.getenv("AGENTCORE_RUNTIME_ARN", "").strip()
    return arn or None


def get_workload_access_token_for_jwt(user_token: str) -> str:
    """
    Exchange Cognito access token for AgentCore workload token (D1-B2).

    Prefer the Cognito AccessToken (has client_id). Raises on invalid JWT.
    """
    if not user_token or not user_token.strip():
        raise ValueError("user_token is required")
    try:
        resp = _dp().get_workload_access_token_for_jwt(
            workloadName=workload_name(),
            userToken=user_token.strip(),
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        msg = exc.response.get("Error", {}).get("Message", str(exc))
        raise RuntimeError(f"{code}: {msg}") from exc

    token = resp.get("workloadAccessToken")
    if not token:
        raise RuntimeError("GetWorkloadAccessTokenForJWT returned no token")
    return token


def start_github_oauth(
    workload_token: str,
    *,
    custom_state: str,
    force: bool = True,
) -> dict[str, Any]:
    """Begin USER_FEDERATION for GitHub; returns authorizationUrl and/or accessToken."""
    try:
        return _dp().get_resource_oauth2_token(
            workloadIdentityToken=workload_token,
            resourceCredentialProviderName=github_provider_name(),
            scopes=github_scopes(),
            oauth2Flow="USER_FEDERATION",
            resourceOauth2ReturnUrl=oauth2_return_url(),
            customState=custom_state,
            forceAuthentication=force,
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        msg = exc.response.get("Error", {}).get("Message", str(exc))
        raise RuntimeError(f"{code}: {msg}") from exc


def complete_github_oauth_session(
    *,
    session_uri: str,
    cognito_access_token: str,
) -> None:
    """Bind 3LO session to the Cognito user who started Connect GitHub (D1-C4)."""
    try:
        _dp().complete_resource_token_auth(
            sessionUri=session_uri,
            userIdentifier={"userToken": cognito_access_token},
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        msg = exc.response.get("Error", {}).get("Message", str(exc))
        raise RuntimeError(f"{code}: {msg}") from exc


def get_github_access_token(
    workload_token: str,
    *,
    session_uri: str | None = None,
) -> str:
    """Fetch vaulted GitHub token (after CompleteResourceTokenAuth or cache hit)."""
    kwargs: dict[str, Any] = {
        "workloadIdentityToken": workload_token,
        "resourceCredentialProviderName": github_provider_name(),
        "scopes": github_scopes(),
        "oauth2Flow": "USER_FEDERATION",
        "resourceOauth2ReturnUrl": oauth2_return_url(),
    }
    if session_uri:
        kwargs["sessionUri"] = session_uri
    try:
        resp = _dp().get_resource_oauth2_token(**kwargs)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        msg = exc.response.get("Error", {}).get("Message", str(exc))
        raise RuntimeError(f"{code}: {msg}") from exc
    token = resp.get("accessToken")
    if not token:
        raise RuntimeError(
            "GitHub token not ready yet "
            f"(sessionStatus={resp.get('sessionStatus')!r}). "
            "Finish Authorize in the browser, then retry."
        )
    return token


def invoke_headers(cognito_access_token: str, session_id: str) -> dict[str, str]:
    """Headers for JWT Bearer invoke of AgentCore Runtime (D1-B4)."""
    return {
        "Authorization": f"Bearer {cognito_access_token}",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
    }


def invoke_url(agent_runtime_arn: str | None = None, qualifier: str = "DEFAULT") -> str:
    arn = agent_runtime_arn or runtime_arn()
    if not arn:
        raise RuntimeError(
            "Set AGENTCORE_RUNTIME_ARN in .env.shared to invoke a deployed runtime."
        )
    escaped = urllib.parse.quote(arn, safe="")
    return (
        f"https://bedrock-agentcore.{_region()}.amazonaws.com"
        f"/runtimes/{escaped}/invocations?qualifier={qualifier}"
    )


def invoke_runtime_with_jwt(
    cognito_access_token: str,
    payload: dict[str, Any],
    *,
    session_id: str = "d1b-verify-session",
    agent_runtime_arn: str | None = None,
) -> requests.Response:
    """POST /invocations with Cognito Bearer JWT (Runtime JWT authorizer path)."""
    return requests.post(
        invoke_url(agent_runtime_arn),
        headers=invoke_headers(cognito_access_token, session_id),
        json=payload,
        timeout=60,
    )
