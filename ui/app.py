"""
Demo UI for Cognito + GitHub Agent POC (spec R10).

Custom login → Cognito → Connect GitHub (AgentCore Identity USER_FEDERATION)
→ Create Agent Task (GitHub issue) → invoke githubWorkflow runtime.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.shared", override=True)

import streamlit as st

from agentcore_identity import (
    agent_task_payload,
    complete_github_oauth_session,
    get_github_access_token,
    get_workload_access_token_for_jwt,
    github_provider_name,
    invoke_runtime_with_jwt,
    jwt_authorizer_config,
    oauth2_return_url,
    start_github_oauth,
    workload_name,
)
from cognito_auth import cognito_login, user_from_claims, verify_id_token
from github_oauth import (
    claim_oauth_callback,
    create_agent_issue,
    fetch_github_user,
    github_oauth_app_hint,
    load_link,
    new_oauth_state,
    peek_pending_oauth,
    pop_pending_oauth,
    resolve_repo,
    save_link,
    save_pending_oauth,
)


def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("user", None)
    ss.setdefault("id_token", None)
    ss.setdefault("access_token", None)
    ss.setdefault("workload_token", None)
    ss.setdefault("workload_error", None)
    ss.setdefault("github_connected", False)
    ss.setdefault("github_user", None)
    # D1-C6: do not keep GitHub token; fetch from AgentCore vault when needed
    ss.setdefault("github_oauth_state", None)
    ss.setdefault("github_auth_url", None)
    ss.setdefault("github_session_uri", None)
    ss.setdefault("last_issue", None)
    ss.setdefault("last_agent_result", None)
    ss.setdefault("auth_error", None)
    ss.setdefault("github_error", None)
    ss.setdefault("_oauth_callback_claimed", None)


def _qp_one(name: str) -> str | None:
    raw = st.query_params.get(name)
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else None
    if not raw:
        return None
    return unquote(str(raw))


def _restore_cognito_from_pending(pending: dict) -> bool:
    """Restore Cognito session from pending; do not remint workload here."""
    if st.session_state.user:
        # Prefer pending JWTs (exact bind artifact for CompleteResourceTokenAuth)
        if pending.get("access_token"):
            st.session_state.access_token = pending["access_token"]
        if pending.get("id_token"):
            st.session_state.id_token = pending["id_token"]
        return True
    try:
        claims = verify_id_token(pending["id_token"])
        st.session_state.user = user_from_claims(claims)
        st.session_state.id_token = pending["id_token"]
        st.session_state.access_token = pending.get("access_token")
        return True
    except Exception as exc:  # noqa: BLE001
        st.session_state.github_error = (
            f"Could not restore Cognito session after GitHub redirect: {exc}. "
            "Sign in again, then Connect GitHub."
        )
        return False


def _handle_agentcore_github_callback() -> None:
    """Complete AgentCore 3LO if redirected with ?session_id= (D1-C4)."""
    session_id = _qp_one("session_id")
    if not session_id:
        return

    if st.session_state.get("_oauth_callback_claimed") == session_id:
        st.query_params.clear()
        return

    state = _qp_one("state") or st.session_state.github_oauth_state
    st.query_params.clear()

    pending = peek_pending_oauth(state) if state else None
    if not pending and st.session_state.github_oauth_state:
        pending = peek_pending_oauth(st.session_state.github_oauth_state)
        if pending:
            state = st.session_state.github_oauth_state

    if not pending:
        if not st.session_state.user or not st.session_state.id_token:
            st.session_state.github_error = (
                "GitHub OAuth return missing pending state — sign in and Connect GitHub again."
            )
            return
        # Last resort: live session IdToken (must be same JWT that started OAuth)
        bind_token = st.session_state.id_token
        cognito_sub = st.session_state.user["sub"]
    else:
        if not _restore_cognito_from_pending(pending):
            return
        if st.session_state.user["sub"] != pending["cognito_sub"]:
            st.session_state.github_error = (
                "GitHub OAuth was started for a different Cognito user."
            )
            return
        # Exact JWT that minted workload before GetResourceOauth2Token (IdToken)
        bind_token = (
            pending.get("bind_user_token")
            or pending.get("id_token")
            or st.session_state.id_token
        )
        cognito_sub = pending["cognito_sub"]

    if not bind_token:
        st.session_state.github_error = (
            "Missing Cognito IdToken for CompleteResourceTokenAuth — sign in again."
        )
        return

    # Same-run Streamlit double-fire only; disk claim after success so a failed
    # Complete can be retried with the same session_id once.
    if st.session_state.get("_oauth_callback_claimed") == session_id:
        return
    st.session_state._oauth_callback_claimed = session_id

    pending_uri = (pending or {}).get("session_uri") if pending else None
    session_uri = session_id
    if pending_uri and pending_uri != session_id:
        # Prefer callback session_id (AgentCore redirect); keep pending for diagnostics
        pass

    try:
        try:
            complete_github_oauth_session(
                session_uri=session_uri,
                user_token=bind_token,
            )
        except Exception as complete_exc:
            # If callback URI fails validation, retry once with start-time sessionUri
            if (
                pending_uri
                and pending_uri != session_uri
                and "ValidationException" in str(complete_exc)
            ):
                complete_github_oauth_session(
                    session_uri=pending_uri,
                    user_token=bind_token,
                )
                session_uri = pending_uri
            else:
                raise RuntimeError(
                    f"CompleteResourceTokenAuth: {complete_exc} "
                    f"[callback_session={session_id!r} pending_session={pending_uri!r}]"
                ) from complete_exc

        try:
            st.session_state.workload_token = get_workload_access_token_for_jwt(
                bind_token
            )
        except Exception as remint_exc:
            raise RuntimeError(
                f"Remint workload after bind: {remint_exc}"
            ) from remint_exc

        try:
            gh_token = get_github_access_token(
                st.session_state.workload_token,
                session_uri=session_uri,
            )
        except Exception as gh_exc:
            raise RuntimeError(f"GetResourceOauth2Token (fetch): {gh_exc}") from gh_exc

        gh_user = fetch_github_user(gh_token)
        save_link(cognito_sub, gh_user)
        if state:
            pop_pending_oauth(state)
        claim_oauth_callback(session_id)
        st.session_state.github_user = gh_user
        st.session_state.github_connected = True
        st.session_state.github_oauth_state = None
        st.session_state.github_auth_url = None
        st.session_state.github_session_uri = None
        st.session_state.github_error = None
    except Exception as exc:  # noqa: BLE001
        # Allow one more Complete attempt on next load of same session_id
        if st.session_state.get("_oauth_callback_claimed") == session_id:
            st.session_state._oauth_callback_claimed = None
        st.session_state.github_error = (
            f"{exc} — sign out, sign in once, Connect GitHub again "
            "(do not re-login mid-flow; pending OAuth session is single-use)."
        )
        st.session_state.github_connected = False


def _begin_github_connect(user: dict) -> None:
    if not st.session_state.access_token or not st.session_state.id_token:
        raise RuntimeError("Missing Cognito tokens — sign out and sign in again.")

    # CompleteResourceTokenAuth validates an OIDC userToken (aud). Bind the IdToken
    # for mint + GetResourceOauth2Token + Complete — exact same string end-to-end.
    access = st.session_state.access_token
    bind_token = st.session_state.id_token
    workload = get_workload_access_token_for_jwt(bind_token)
    st.session_state.workload_token = workload

    state = new_oauth_state()
    st.session_state.github_oauth_state = state
    st.session_state._oauth_callback_claimed = None
    st.session_state.github_error = None
    resp = start_github_oauth(workload, custom_state=state)
    session_uri = resp.get("sessionUri")
    st.session_state.github_session_uri = session_uri
    save_pending_oauth(
        state,
        cognito_sub=user["sub"],
        id_token=bind_token,
        access_token=access,
        bind_user_token=bind_token,
        email=user["email"],
        session_uri=session_uri,
    )

    if resp.get("accessToken"):
        gh_user = fetch_github_user(resp["accessToken"])
        save_link(user["sub"], gh_user)
        st.session_state.github_user = gh_user
        st.session_state.github_connected = True
        st.session_state.github_auth_url = None
        st.session_state.github_error = None
        return

    auth_url = resp.get("authorizationUrl")
    if not auth_url:
        raise RuntimeError(f"GetResourceOauth2Token returned no authorizationUrl: {resp}")
    st.session_state.github_auth_url = auth_url
    st.session_state.github_connected = False


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
            access_token = tokens.get("AccessToken")
            claims = verify_id_token(id_token)
            st.session_state.user = user_from_claims(claims)
            st.session_state.id_token = id_token
            st.session_state.access_token = access_token
            st.session_state.auth_error = None
            st.session_state.workload_token = None
            st.session_state.workload_error = None
            if access_token:
                try:
                    st.session_state.workload_token = get_workload_access_token_for_jwt(
                        access_token
                    )
                except Exception as wexc:  # noqa: BLE001
                    st.session_state.workload_error = str(wexc)
            link = load_link(st.session_state.user["sub"])
            if link:
                st.session_state.github_user = link
            st.rerun()
        except Exception as exc:  # noqa: BLE001 — show on form
            st.session_state.auth_error = str(exc)
            st.session_state.user = None
            st.session_state.id_token = None
            st.session_state.access_token = None
            st.session_state.workload_token = None
            st.session_state.workload_error = None
            st.rerun()


def home_page(user: dict) -> None:
    st.title("Agent Demo")
    st.subheader(f"Welcome, {user['email']}")
    st.markdown(f"**sub:** `{user['sub']}`")
    st.caption("Tool RBAC is Cedar on the AgentCore Gateway (not Cognito role claims).")

    if st.session_state.workload_token:
        wt = st.session_state.workload_token
        st.success(
            f"AgentCore workload token ready (`…{wt[-8:]}`) · "
            f"WI `{workload_name()}` · provider `{github_provider_name()}`"
        )
    elif st.session_state.workload_error:
        st.warning(f"Workload token: {st.session_state.workload_error}")
    else:
        st.caption("No AgentCore workload token yet (needs Cognito AccessToken).")

    with st.expander("Verified ID token claims"):
        st.json(user.get("claims") or {})
    with st.expander("Runtime JWT authorizer (D1-B)"):
        st.json(jwt_authorizer_config())
        st.caption(
            "Invoke deployed runtime with header "
            "`Authorization: Bearer <Cognito AccessToken>` "
            "+ `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id`. "
            "See ui/README.md."
        )

    if st.session_state.github_error:
        st.error(st.session_state.github_error)

    gh_col, out_col = st.columns(2)
    with gh_col:
        if st.session_state.github_connected and st.session_state.github_user:
            gu = st.session_state.github_user
            st.success(f"GitHub connected as **{gu.get('github_login', '?')}**")
            st.caption(
                f"github_user_id `{gu.get('github_user_id')}` · "
                "token vaulted in AgentCore Identity (not stored in UI)"
            )
            if st.button("Disconnect GitHub"):
                st.session_state.github_connected = False
                st.session_state.github_user = None
                st.session_state.github_error = None
                st.session_state.github_auth_url = None
                st.rerun()
        else:
            st.caption(
                "Connect GitHub via AgentCore Identity "
                f"(`GetResourceOauth2Token` / `{github_provider_name()}`). "
                f"Return URL: `{oauth2_return_url()}`"
            )
            st.caption(
                "GitHub OAuth App **Authorization callback URL** must be exactly:\n"
                f"`{github_oauth_app_hint()}`\n"
                "(Not `http://localhost:8501/` — that is only AgentCore’s return URL.)"
            )
            if st.session_state.github_auth_url:
                st.link_button(
                    "Authorize on GitHub",
                    st.session_state.github_auth_url,
                    type="primary",
                )
                st.caption("After approve, AgentCore returns here with session_id.")
                if st.button("Start over"):
                    st.session_state.github_auth_url = None
                    st.session_state.github_oauth_state = None
                    st.rerun()
            else:
                try:
                    if st.button("Connect GitHub", type="primary"):
                        _begin_github_connect(user)
                        st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.warning(str(exc))

    with out_col:
        if st.button("Sign out"):
            st.session_state.user = None
            st.session_state.id_token = None
            st.session_state.access_token = None
            st.session_state.workload_token = None
            st.session_state.workload_error = None
            st.session_state.github_connected = False
            st.session_state.github_user = None
            st.session_state.github_oauth_state = None
            st.session_state.github_auth_url = None
            st.session_state.github_session_uri = None
            st.session_state._oauth_callback_claimed = None
            st.session_state.last_issue = None
            st.session_state.last_agent_result = None
            st.session_state.auth_error = None
            st.session_state.github_error = None
            st.rerun()

    st.divider()
    st.subheader("Create Agent Task")
    if not st.session_state.github_connected or not st.session_state.workload_token:
        st.info("Connect GitHub before creating a task (AgentCore vaulted token).")
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
        if not st.session_state.access_token or not st.session_state.id_token:
            st.error("Missing Cognito tokens — sign out and sign in again.")
            return
        title = task.strip().splitlines()[0][:80]
        body = (
            f"{task.strip()}\n\n"
            f"---\n"
            f"Requested by Cognito user: {user['sub']}\n"
            f"Task type: {task_type}\n"
        )
        try:
            # D1-C6: pull token from vault at use time; do not keep in session
            gh_token = get_github_access_token(st.session_state.workload_token)
            owner, name = resolve_repo(repo, gu["github_login"])
            issue = create_agent_issue(
                gh_token,
                owner=owner,
                repo=name,
                title=title,
                body=body,
            )
            issue["cognito_sub"] = user["sub"]
            issue["task"] = task.strip()
            issue["task_type"] = task_type
            st.session_state.last_issue = issue
            st.session_state.last_agent_result = None
            st.success(
                f"Created issue **#{issue['number']}** on `{issue['repo']}` — "
                f"[open on GitHub]({issue['html_url']})"
            )
            st.json(issue)

            payload = agent_task_payload(
                task=task.strip(),
                task_type=task_type,
                repo=issue["repo"],
                issue_number=issue["number"],
                sub=user["sub"],
                email=user["email"],
            )
            # Session id must be long enough for AgentCore Runtime
            session_id = f"{user['sub']}-issue-{issue['number']}"
            # Runtime CUSTOM_JWT allowedAudience = app client id → Cognito IdToken aud
            if not st.session_state.id_token:
                raise RuntimeError("Missing Cognito IdToken — sign out and sign in again.")
            with st.spinner("Invoking agent on this issue…"):
                # Forward vaulted GitHub OAuth (UI workload) via Runtime custom header
                # so agent tools can act as this user (Runtime WI vault is separate).
                resp = invoke_runtime_with_jwt(
                    st.session_state.id_token,
                    payload,
                    session_id=session_id,
                    github_access_token=gh_token,
                )
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Agent invoke failed ({resp.status_code}): {resp.text}"
                )
            try:
                agent_body = resp.json()
            except Exception:  # noqa: BLE001
                agent_body = {"raw": resp.text}
            st.session_state.last_agent_result = agent_body
            result_text = (
                agent_body.get("result")
                if isinstance(agent_body, dict)
                else None
            )
            st.success("Agent finished")
            if result_text:
                st.markdown(result_text)
            else:
                st.json(agent_body)
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))

    if st.session_state.last_issue and not submitted:
        st.caption("Last created issue")
        st.json(st.session_state.last_issue)
    if st.session_state.last_agent_result and not submitted:
        st.caption("Last agent result")
        st.json(st.session_state.last_agent_result)


def main() -> None:
    st.set_page_config(page_title="Agent Demo", page_icon="🔐", layout="centered")
    _init_state()
    _handle_agentcore_github_callback()
    if st.session_state.user is None:
        sign_in_page()
    else:
        home_page(st.session_state.user)


if __name__ == "__main__":
    main()
