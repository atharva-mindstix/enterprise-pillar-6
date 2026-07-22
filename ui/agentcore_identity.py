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


def _client_error(exc: ClientError) -> RuntimeError:
    err = exc.response.get("Error") or {}
    code = err.get("Code") or "ClientError"
    msg = err.get("Message") or exc.response.get("message")
    meta = exc.response.get("ResponseMetadata") or {}
    req = meta.get("RequestId") or meta.get("RequestID")
    # ValidationException often has Message=null; surface Error + request id
    detail = msg if msg not in (None, "") else repr(err)
    if req:
        detail = f"{detail} (RequestId={req})"
    return RuntimeError(f"{code}: {detail}")


def get_workload_access_token_for_jwt(user_token: str) -> str:
    """
    Exchange Cognito JWT for AgentCore workload token (D1-B2).

    For USER_FEDERATION session binding, prefer the Cognito IdToken (has aud).
    AccessToken also works for mint; CompleteResourceTokenAuth is pickier.
    """
    if not user_token or not user_token.strip():
        raise ValueError("user_token is required")
    try:
        resp = _dp().get_workload_access_token_for_jwt(
            workloadName=workload_name(),
            userToken=user_token.strip(),
        )
    except ClientError as exc:
        raise _client_error(exc) from exc

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
        raise _client_error(exc) from exc


def complete_github_oauth_session(
    *,
    session_uri: str,
    user_token: str,
) -> None:
    """
    Bind 3LO session (D1-C4).

    user_token must be the *exact* Cognito JWT passed to GetWorkloadAccessTokenForJWT
    before GetResourceOauth2Token. Session is single-use — do not retry with other JWTs.
    """
    session_uri = urllib.parse.unquote(session_uri.strip())
    user_token = user_token.strip()
    if not session_uri or not user_token:
        raise ValueError("session_uri and user_token are required")
    try:
        _dp().complete_resource_token_auth(
            sessionUri=session_uri,
            userIdentifier={"userToken": user_token},
        )
    except ClientError as exc:
        raise _client_error(exc) from exc


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
        raise _client_error(exc) from exc
    token = resp.get("accessToken")
    if not token:
        raise RuntimeError(
            "GitHub token not ready yet "
            f"(sessionStatus={resp.get('sessionStatus')!r}). "
            "Finish Authorize in the browser, then retry."
        )
    return token


def invoke_headers(cognito_jwt: str, session_id: str) -> dict[str, str]:
    """Headers for JWT Bearer invoke of AgentCore Runtime (D1-B4).

    Use Cognito IdToken when authorizer allowedAudience is the app client id
    (AccessToken has no matching aud → Claim 'aud' value mismatch).
    """
    return {
        "Authorization": f"Bearer {cognito_jwt}",
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
    cognito_jwt: str,
    payload: dict[str, Any],
    *,
    session_id: str = "d1b-verify-session",
    agent_runtime_arn: str | None = None,
    timeout: float = 300,
) -> requests.Response:
    """POST /invocations with Cognito Bearer JWT (prefer IdToken for aud check)."""
    return requests.post(
        invoke_url(agent_runtime_arn),
        headers=invoke_headers(cognito_jwt, session_id),
        json=payload,
        timeout=timeout,
    )


def agent_task_payload(
    *,
    task: str,
    task_type: str,
    repo: str,
    issue_number: int,
    sub: str,
    email: str,
) -> dict[str, Any]:
    """Body for githubWorkflow invoke after Create Agent Task."""
    return {
        "prompt": (
            f"Complete GitHub issue #{issue_number} on {repo}.\n"
            f"Task type: {task_type}\n"
            f"Task:\n{task}\n\n"
            "Use repository tools as needed. For documentation tasks, update the "
            "README (or docs) to satisfy the task and open a pull request. "
            "Do not modify application source code."
        ),
        "session": {
            "sub": sub,
            "email": email,
            "repository": repo,
            "issue_number": issue_number,
            "task_type": task_type,
        },
    }
