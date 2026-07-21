"""GitHub OAuth (authorization code) for the demo UI.

ponytail: Direct GitHub OAuth App for UI testing. Upgrade path: AgentCore
Identity GetResourceOauth2Token (USER_FEDERATION) once a GithubOauth2
credential provider + workload token exist.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API = "https://api.github.com"
# Cognito sub → GitHub identity (no access token on disk)
_LINKS_PATH = Path(__file__).resolve().parents[1] / ".data" / "github_links.json"


def _cfg() -> dict[str, str]:
    client_id = os.getenv("GITHUB_CLIENT_ID", "").strip()
    client_secret = os.getenv("GITHUB_CLIENT_SECRET", "").strip()
    redirect = os.getenv(
        "GITHUB_REDIRECT_URI",
        os.getenv("COGNITO_REDIRECT_URI", "http://localhost:8501/"),
    ).strip()
    scopes = os.getenv("GITHUB_OAUTH_SCOPES", "read:user repo").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in .env.shared "
            "(GitHub → Settings → Developer settings → OAuth Apps)."
        )
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect,
        "scopes": scopes,
    }


def new_oauth_state() -> str:
    return secrets.token_urlsafe(24)


def authorize_url(state: str) -> str:
    c = _cfg()
    q = urlencode(
        {
            "client_id": c["client_id"],
            "redirect_uri": c["redirect_uri"],
            "scope": c["scopes"],
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{q}"


def exchange_code(code: str) -> str:
    c = _cfg()
    resp = requests.post(
        TOKEN_URL,
        headers={"Accept": "application/json"},
        data={
            "client_id": c["client_id"],
            "client_secret": c["client_secret"],
            "code": code,
            "redirect_uri": c["redirect_uri"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"GitHub token exchange failed: {data}")
    return token


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


def save_link(cognito_sub: str, github_user: dict[str, Any]) -> None:
    _LINKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    links: dict[str, Any] = {}
    if _LINKS_PATH.exists():
        links = json.loads(_LINKS_PATH.read_text(encoding="utf-8"))
    links[cognito_sub] = {
        "cognito_sub": cognito_sub,
        "github_user_id": github_user["github_user_id"],
        "github_login": github_user["github_login"],
    }
    _LINKS_PATH.write_text(json.dumps(links, indent=2) + "\n", encoding="utf-8")


def load_link(cognito_sub: str) -> dict[str, Any] | None:
    if not _LINKS_PATH.exists():
        return None
    links = json.loads(_LINKS_PATH.read_text(encoding="utf-8"))
    return links.get(cognito_sub)


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
