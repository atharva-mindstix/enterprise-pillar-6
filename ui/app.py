"""
Demo UI for Cognito + GitHub Agent POC (spec R10).

Custom login form → Cognito USER_PASSWORD_AUTH → verify ID token via JWKS.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.shared", override=True)

import streamlit as st

from cognito_auth import cognito_login, user_from_claims, verify_id_token


def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("user", None)
    ss.setdefault("id_token", None)
    ss.setdefault("access_token", None)
    ss.setdefault("github_connected", False)
    ss.setdefault("last_issue", None)
    ss.setdefault("auth_error", None)


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
    role = user.get("role") or "(not in token — set custom claim `role`)"
    st.markdown(
        f"**Role:** `{role}`  \n"
        f"**Project:** `{user['project']}`  \n"
        f"**Environment:** `{user['environment']}`  \n"
        f"**sub:** `{user['sub']}`"
    )
    if not user.get("role"):
        st.warning(
            "JWT has no `role` / `custom:role` claim. "
            "Add it on the Cognito user (custom attribute or pre-token Lambda)."
        )

    with st.expander("Verified ID token claims"):
        st.json(user.get("claims") or {})

    gh_col, out_col = st.columns(2)
    with gh_col:
        if st.session_state.github_connected:
            st.success("GitHub connected")
            if st.button("Disconnect GitHub"):
                st.session_state.github_connected = False
                st.rerun()
        else:
            if st.button("Connect GitHub", type="primary"):
                # ponytail: AgentCore GetResourceOauth2Token next
                st.session_state.github_connected = True
                st.rerun()

    with out_col:
        if st.button("Sign out"):
            st.session_state.user = None
            st.session_state.id_token = None
            st.session_state.access_token = None
            st.session_state.github_connected = False
            st.session_state.last_issue = None
            st.session_state.auth_error = None
            st.rerun()

    st.divider()
    st.subheader("Create Agent Task")
    if not user.get("role"):
        st.error("Cannot create task without a verified role claim (fail closed).")
        return
    if not st.session_state.github_connected:
        st.info("Connect GitHub before creating a task.")
        return

    with st.form("create_task"):
        repo = st.text_input("Repository", value="agent-demo")
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
        # ponytail: POST backend to create GitHub issue with label agent-task
        issue = {
            "number": (st.session_state.last_issue or {}).get("number", 0) + 1,
            "repo": repo.strip(),
            "task": task.strip(),
            "task_type": task_type,
            "cognito_sub": user["sub"],
            "role": user["role"],
            "project": user["project"],
            "label": "agent-task",
        }
        st.session_state.last_issue = issue
        st.success(
            f"Created issue **#{issue['number']}** on `{issue['repo']}` "
            f"(label `{issue['label']}`) for Cognito user `{issue['cognito_sub']}`."
        )
        st.json(issue)

    if st.session_state.last_issue and not submitted:
        st.caption("Last created issue (local stub)")
        st.json(st.session_state.last_issue)


def main() -> None:
    st.set_page_config(page_title="Agent Demo", page_icon="🔐", layout="centered")
    _init_state()
    if st.session_state.user is None:
        sign_in_page()
    else:
        home_page(st.session_state.user)


if __name__ == "__main__":
    main()
