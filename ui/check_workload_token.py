"""Self-check D1-B: bad Cognito JWT rejected; good JWT → workload token.

Usage:
  python check_workload_token.py
  # optional good-path (uses Cognito login):
  set COGNITO_TEST_USERNAME=...
  set COGNITO_TEST_PASSWORD=...
  python check_workload_token.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.shared", override=True)

from agentcore_identity import (  # noqa: E402
    get_workload_access_token_for_jwt,
    github_provider_name,
    invoke_headers,
    jwt_authorizer_config,
    oauth2_return_url,
    workload_name,
)
from cognito_auth import cognito_login  # noqa: E402


def main() -> int:
    cfg = jwt_authorizer_config()
    assert "customJwtAuthorizer" in cfg
    assert cfg["customJwtAuthorizer"]["discoveryUrl"].endswith(
        "/.well-known/openid-configuration"
    )
    assert cfg["customJwtAuthorizer"]["allowedAudience"]
    print("jwt authorizer config ok")
    print(f"workloadName={workload_name()}")
    print(f"githubProvider={github_provider_name()}")
    print(f"oauth2ReturnUrl={oauth2_return_url()}")
    assert github_provider_name() == "github-prajwal" or os.getenv(
        "AGENTCORE_GITHUB_PROVIDER"
    )
    assert oauth2_return_url().startswith("http")

    headers = invoke_headers("dummy-token", "sess-1")
    assert headers["Authorization"] == "Bearer dummy-token"
    assert "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id" in headers
    print("invoke headers shape ok")

    # Bad JWT must fail
    try:
        get_workload_access_token_for_jwt("not-a-valid-jwt")
        print("FAIL: bad JWT was accepted")
        return 1
    except RuntimeError as exc:
        msg = str(exc).lower()
        assert "invalid" in msg or "validation" in msg or "unauthorized" in msg, exc
        print(f"bad JWT rejected: {exc}")

    user = os.getenv("COGNITO_TEST_USERNAME", "").strip()
    password = os.getenv("COGNITO_TEST_PASSWORD", "").strip()
    if not user or not password:
        print(
            "skip good JWT (set COGNITO_TEST_USERNAME + COGNITO_TEST_PASSWORD to verify)"
        )
        print("ok (partial)")
        return 0

    tokens = cognito_login(user, password)
    access = tokens["AccessToken"]
    workload = get_workload_access_token_for_jwt(access)
    assert workload and len(workload) > 20
    print(f"good JWT → workload token len={len(workload)}")
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
