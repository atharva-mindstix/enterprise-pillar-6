"""
Demo UI for Cognito + GitHub Agent POC (spec R10).

Custom login → Cognito → Connect GitHub (OAuth) → Create Agent Task (GitHub issue).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.shared", override=True)

import streamlit as st

from cognito_auth import cognito_login, user_from_claims, verify_id_token
from github_oauth import (
    authorize_url,
    create_agent_issue,
    exchange_code,
    fetch_github_user,
    load_link,
    new_oauth_state,
    resolve_repo,
    save_link,
)


def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("user", None)
    ss.setdefault("id_token", None)
    ss.setdefault("access_token", None)
    ss.setdefault("github_connected", False)
    ss.setdefault("github_user", None)
    ss.setdefault("github_token", None)  # server session only — not written to disk
    ss.setdefault("github_oauth_state", None)
    ss.setdefault("last_issue", None)
    ss.setdefault("auth_error", None)
    ss.setdefault("github_error", None)


def _handle_github_callback() -> None:
    """Complete OAuth if GitHub redirected back with ?code=&state=."""
    code = st.query_params.get("code")
    state = st.query_params.get("state")
    if not code or not state:
        return
    expected = st.session_state.github_oauth_state
    user = st.session_state.user
    # Clear URL params either way so refresh doesn't re-exchange
    st.query_params.clear()
    if not user:
        st.session_state.github_error = "Sign in with Cognito before completing GitHub OAuth."
        return
    if not expected or state != expected:
        st.session_state.github_error = "GitHub OAuth state mismatch — try Connect GitHub again."
        return
    try:
        token = exchange_code(code)
        gh_user = fetch_github_user(token)
        save_link(user["sub"], gh_user)
        st.session_state.github_token = token
        st.session_state.github_user = gh_user
        st.session_state.github_connected = True
        st.session_state.github_oauth_state = None
        st.session_state.github_error = None
    except Exception as exc:  # noqa: BLE001
        st.session_state.github_error = str(exc)
        st.session_state.github_connected = False
        st.session_state.github_token = None
        st.session_state.github_user = None


def sign_in_page() -> None:
    st.title("Agent Demo")
    st.caption("Sign in · Cognito verifies credentials and issues JWT")
    secret_ok = bool(os.getenv("COGNITO_APP_CLIENT_SECRET", "").strip())
    st.write(
        f"Pool `{os.getenv('COGNITO_USER_POOL_ID', '—')}` · "
        f"Client `{os.getenv('COGNITO_APP_CLIENT_ID', '—')}` · "
        f"Region `{os.getenv('AWS_REGION', '—')}` · "
        f"client secret `{'set' if secret_ok else 'MISSING'}`"
    )

    if st.session_state.auth_error:
        st.error(st.session_state.auth_error)
    if st.session_state.github_error:
        st.error(st.session_state.github_error)

    with st.form("cognito_login"):
        username = st.text_input("Username or email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")

    if submitted:
        if not username.strip() or not password:
            st.session_state.auth_error = "Username and password are required."
            st.rerun()
        try:
            tokens = cognito_login(username.strip(), password)
            id_token = tokens["IdToken"]
            claims = verify_id_token(id_token)
            st.session_state.user = user_from_claims(claims)
            st.session_state.id_token = id_token
            st.session_state.access_token = tokens.get("AccessToken")
            st.session_state.auth_error = None
            # Restore prior GitHub link (token still needs reconnect this session)
            link = load_link(st.session_state.user["sub"])
            if link:
                st.session_state.github_user = link
            st.rerun()
        except Exception as exc:  # noqa: BLE001 — show on form
            st.session_state.auth_error = str(exc)
            st.session_state.user = None
            st.session_state.id_token = None
            st.session_state.access_token = None
            st.rerun()


def home_page(user: dict) -> None:
    st.title("Agent Demo")
    st.subheader(f"Welcome, {user['email']}")
    st.markdown(f"**sub:** `{user['sub']}`")
    st.caption("Tool RBAC is Cedar on the AgentCore Gateway (not Cognito role claims).")

    with st.expander("Verified ID token claims"):
        st.json(user.get("claims") or {})

    if st.session_state.github_error:
        st.error(st.session_state.github_error)

    gh_col, out_col = st.columns(2)
    with gh_col:
        if st.session_state.github_connected and st.session_state.github_user:
            gu = st.session_state.github_user
            st.success(f"GitHub connected as **{gu.get('github_login', '?')}**")
            st.caption(f"github_user_id `{gu.get('github_user_id')}`")
            if st.button("Disconnect GitHub"):
                st.session_state.github_connected = False
                st.session_state.github_token = None
                st.session_state.github_user = None
                st.session_state.github_error = None
                st.rerun()
        else:
            st.caption(
                "Connect GitHub via OAuth. "
                "Token stays in server session only (not written to disk)."
            )
            try:
                if not st.session_state.github_oauth_state:
                    st.session_state.github_oauth_state = new_oauth_state()
                url = authorize_url(st.session_state.github_oauth_state)
                st.link_button("Connect GitHub", url, type="primary")
            except Exception as exc:  # noqa: BLE001
                st.warning(str(exc))

    with out_col:
        if st.button("Sign out"):
            st.session_state.user = None
            st.session_state.id_token = None
            st.session_state.access_token = None
            st.session_state.github_connected = False
            st.session_state.github_token = None
            st.session_state.github_user = None
            st.session_state.github_oauth_state = None
            st.session_state.last_issue = None
            st.session_state.auth_error = None
            st.session_state.github_error = None
            st.rerun()

    st.divider()
    st.subheader("Create Agent Task")
    if not st.session_state.github_connected or not st.session_state.github_token:
        st.info("Connect GitHub before creating a task (OAuth token required this session).")
        return

    gu = st.session_state.github_user or {}
    default_repo = f"{gu.get('github_login', 'OWNER')}/agent-demo"

    with st.form("create_task"):
        repo = st.text_input("Repository (owner/name)", value=default_repo)
        task = st.text_area(
            "Task",
            value="Update README with local deployment instructions.",
        )
        task_type = st.selectbox(
            "Task type",
            ["Documentation", "Source", "Other"],
            index=0,
        )
        submitted = st.form_submit_button("Create Agent Task", type="primary")

    if submitted:
        if not repo.strip() or not task.strip():
            st.error("Repository and Task are required.")
            return
        title = task.strip().splitlines()[0][:80]
        body = (
            f"{task.strip()}\n\n"
            f"---\n"
            f"Requested by Cognito user: {user['sub']}\n"
            f"Task type: {task_type}\n"
        )
        try:
            owner, name = resolve_repo(repo, gu["github_login"])
            issue = create_agent_issue(
                st.session_state.github_token,
                owner=owner,
                repo=name,
                title=title,
                body=body,
            )
            issue["cognito_sub"] = user["sub"]
            issue["task"] = task.strip()
            issue["task_type"] = task_type
            st.session_state.last_issue = issue
            st.success(
                f"Created issue **#{issue['number']}** on `{issue['repo']}` — "
                f"[open on GitHub]({issue['html_url']})"
            )
            st.json(issue)
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))

    if st.session_state.last_issue and not submitted:
        st.caption("Last created issue")
        st.json(st.session_state.last_issue)


def main() -> None:
    st.set_page_config(page_title="Agent Demo", page_icon="🔐", layout="centered")
    _init_state()
    _handle_github_callback()
    if st.session_state.user is None:
        sign_in_page()
    else:
        home_page(st.session_state.user)


if __name__ == "__main__":
    main()
