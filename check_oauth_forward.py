"""Self-check: Option A header inject + UI forward header (no network)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_AGENT = _ROOT / "githubpoc" / "app" / "githubWorkflow"
_LAMBDA = _ROOT / "lambda"
_UI = _ROOT / "ui"

sys.path.insert(0, str(_AGENT))
from mcp_client.client import inject_github_auth_args  # noqa: E402
from github_token import token_from_headers  # noqa: E402

sys.path.insert(0, str(_LAMBDA))
from app import _event_for_log, resolve_github_token  # noqa: E402

sys.path.insert(0, str(_UI))
from agentcore_identity import GITHUB_ACCESS_TOKEN_HEADER, invoke_headers  # noqa: E402


def test_inject_headers() -> None:
    out = inject_github_auth_args({"owner": "o", "repo": "r"}, "gh-oauth-token")
    assert out["owner"] == "o"
    assert out["_headers"]["Authorization"] == "Bearer gh-oauth-token"


def test_oauth_beats_pat() -> None:
    os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = "pat-should-lose"
    try:
        tok = resolve_github_token(
            {"_headers": {"Authorization": "Bearer oauth-wins"}, "owner": "o"},
            None,
        )
        assert tok == "oauth-wins"
    finally:
        os.environ.pop("GITHUB_PERSONAL_ACCESS_TOKEN", None)


def test_log_redacts_headers() -> None:
    logged = _event_for_log(
        {"owner": "o", "_headers": {"Authorization": "Bearer secret"}}
    )
    assert logged["_headers"]["Authorization"] == "***"
    assert logged["owner"] == "o"


def test_ui_forward_header() -> None:
    h = invoke_headers("cognito-jwt", "sess-1", github_access_token="gh-tok")
    assert h[GITHUB_ACCESS_TOKEN_HEADER] == "gh-tok"
    assert token_from_headers(h) == "gh-tok"


if __name__ == "__main__":
    test_inject_headers()
    test_oauth_beats_pat()
    test_log_redacts_headers()
    test_ui_forward_header()
    print("ok")
