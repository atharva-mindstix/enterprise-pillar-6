"""GitHub API helpers + pending OAuth state for AgentCore Identity 3LO (D1-C).

Connect GitHub uses AgentCore GetResourceOauth2Token / CompleteResourceTokenAuth
(see agentcore_identity.py). This module keeps GitHub REST helpers and the
short-lived pending state file so Streamlit can restore Cognito after redirect.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

import requests

API = "https://api.github.com"
_DATA = Path(__file__).resolve().parents[1] / ".data"
# Cognito sub → GitHub identity (no access token on disk)
_LINKS_PATH = _DATA / "github_links.json"
# customState → Cognito session (survives Streamlit session loss on redirect)
_PENDING_PATH = _DATA / "oauth_pending.json"


def new_oauth_state() -> str:
    return secrets.token_urlsafe(24)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def save_pending_oauth(
    state: str,
    *,
    cognito_sub: str,
    id_token: str,
    access_token: str,
    email: str,
    session_uri: str | None = None,
) -> None:
    # ponytail: short-lived tokens on disk so AgentCore 3LO redirect can restore
    # Cognito + CompleteResourceTokenAuth if Streamlit session resets.
    pending = _read_json(_PENDING_PATH)
    pending[state] = {
        "cognito_sub": cognito_sub,
        "id_token": id_token,
        "access_token": access_token,
        "email": email,
        "session_uri": session_uri,
    }
    _write_json(_PENDING_PATH, pending)


def pop_pending_oauth(state: str) -> dict[str, Any] | None:
    pending = _read_json(_PENDING_PATH)
    row = pending.pop(state, None)
    _write_json(_PENDING_PATH, pending)
    return row


def peek_pending_oauth(state: str) -> dict[str, Any] | None:
    return _read_json(_PENDING_PATH).get(state)


def save_link(cognito_sub: str, github_user: dict[str, Any]) -> None:
    links = _read_json(_LINKS_PATH)
    links[cognito_sub] = {
        "cognito_sub": cognito_sub,
        "github_user_id": github_user["github_user_id"],
        "github_login": github_user["github_login"],
    }
    _write_json(_LINKS_PATH, links)


def load_link(cognito_sub: str) -> dict[str, Any] | None:
    return _read_json(_LINKS_PATH).get(cognito_sub)


def fetch_github_user(access_token: str) -> dict[str, Any]:
    resp = requests.get(
        f"{API}/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    resp.raise_for_status()
    u = resp.json()
    return {
        "github_user_id": str(u["id"]),
        "github_login": u["login"],
        "name": u.get("name") or u["login"],
    }


def resolve_repo(repo: str, github_login: str) -> tuple[str, str]:
    """Return (owner, name). Bare name uses the connected GitHub login."""
    repo = repo.strip().removesuffix(".git")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return owner.strip(), name.strip()
    return github_login, repo


def create_agent_issue(
    access_token: str,
    *,
    owner: str,
    repo: str,
    title: str,
    body: str,
    label: str = "agent-task",
) -> dict[str, Any]:
    # Ensure label exists (ignore 422 if already there)
    requests.post(
        f"{API}/repos/{owner}/{repo}/labels",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"name": label, "color": "0E8A16", "description": "AgentCore demo task"},
        timeout=30,
    )
    resp = requests.post(
        f"{API}/repos/{owner}/{repo}/issues",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"title": title, "body": body, "labels": [label]},
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"GitHub create issue failed ({resp.status_code}): {resp.text}")
    issue = resp.json()
    return {
        "number": issue["number"],
        "html_url": issue["html_url"],
        "title": issue["title"],
        "repo": f"{owner}/{repo}",
        "label": label,
    }


def github_oauth_app_hint() -> str:
    """Callback the GitHub OAuth App must allow (AgentCore Identity, not Streamlit)."""
    return os.getenv(
        "AGENTCORE_GITHUB_CALLBACK_URL",
        "https://bedrock-agentcore.us-west-2.amazonaws.com/identities/oauth2/callback/"
        "632c2a61-cbc6-4102-9b1e-17d47f886676",
    ).strip()
