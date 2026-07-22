# Development log

Running append-only changelog of code changes in this project.

## 2026-07-21 14:05 +05:30 — Project changelog rule

- Added `.cursor/rules/version-changelog.mdc` so the agent always appends change summaries here after code edits (append-only, never delete)

## 2026-07-21 14:09 +05:30 — Cognito + GitHub agent demo specs

- Added `specs/` with constitution and SDD package for Cognito auth, GitHub OAuth, RBAC tools, ABAC/STS, UI, and acceptance (no implementation)

## 2026-07-21 14:10 +05:30 — Changelog entries include time

- Updated `version-changelog.mdc` entry format to `YYYY-MM-DD HH:MM ±HH:MM`; aligned existing `version.md` headings

## 2026-07-21 14:48 +05:30 — Dev 1 / Dev 2 parallel tasklist

- Added `specs/cognito-github-agent-demo/dev-split.md` with independent Dev 1 (identity/UI/GitHub) and Dev 2 (IAM/S3/STS/agent) checklists plus integration pass

## 2026-07-21 14:56 +05:30 — Shared contract env file

- Added `.env.shared` + `.env.shared.example` for Day-0 shared contract; gitignore local env; pointed `dev-split.md` at the env file

## 2026-07-21 15:28 +05:30 — Minimal shared env

- Slimmed `.env.shared` / example to AWS + Cognito + optional `AGENTCORE_GATEWAY_ARN` + dev owners; other names stay as spec defaults

## 2026-07-21 15:40 +05:30 — Remove Cognito group RBAC from specs

- Specs now use verified custom `role` claim only (no `cognito:groups`); updated spec, design, data-model, tasks, acceptance, and dev-split

## 2026-07-21 15:46 +05:30 — Streamlit demo UI (spec R10)

- Added `ui/app.py` minimal flow: Sign in with Cognito, welcome (role/project), Connect GitHub, Create Agent Task (Cognito/GitHub still stubbed)

## 2026-07-21 15:54 +05:30 — Cognito Hosted UI login

- Wired Streamlit to Cognito Hosted UI (PKCE + code exchange + JWKS ID token verify); added `ui/cognito_auth.py`; set `COGNITO_DOMAIN` / redirect; registered `localhost:8501` callbacks on app client

## 2026-07-21 15:58 +05:30 — Custom Cognito login form

- Replaced Hosted UI with Streamlit username/password → `USER_PASSWORD_AUTH` + `SECRET_HASH`; JWKS ID token verify; stored client secret in gitignored `.env.shared`

## 2026-07-21 16:00 +05:30 — Fix cognito_login import

- Renamed `login` → `cognito_login` and cleared stale import path so Streamlit can load auth module
## 2026-07-21 15:45 +05:30 — githubWorkflow system prompt

- Added `specs/cognito-github-agent-demo/system-prompt.md` and runtime `system_prompt.md` derived from spec R5–R9
- Wired `prompt.py` + `main.py` to load the prompt and optionally inject verified session context

## 2026-07-21 16:16 +05:30 — Fix Cognito SECRET_HASH not sent

- Load `.env.shared` from `cognito_auth` with `override=True` so client secret always reaches `SECRET_HASH`
- Login page shows whether client secret is set; clearer error if Cognito still rejects missing hash

## 2026-07-21 16:40 +05:30 — Specs: Cedar RBAC; defer ABAC

- Replaced Cognito role→tools and S3/STS ABAC with Gateway + Cedar tool RBAC; ABAC deferred in constitution/spec/design/data-model/tasks/dev-split/acceptance
- Aligned system prompts, UI (email/sub only), and prompt session injection; dropped ENVIRONMENT_CLAIM from shared env example

## 2026-07-21 16:46 +05:30 — Streamlit GitHub OAuth connect

- Added `ui/github_oauth.py` + Connect GitHub OAuth callback; creates real `agent-task` issues; Cognito↔GitHub map in `.data/`
- Env: `GITHUB_CLIENT_*` in `.env.shared` / example; UI README setup steps (AgentCore federation still the later upgrade)

## 2026-07-21 16:57 +05:30 — Fix GitHub OAuth session loss

- Persist OAuth pending state (Cognito sub + id_token) under `.data/` so callback restores login after GitHub redirect

## 2026-07-21 23:43 +05:30 — D1-B AgentCore JWT + workload token

- Added `ui/agentcore_identity.py` (Cognito JWT authorizer config, `GetWorkloadAccessTokenForJWT`, invoke headers/URL)
- Streamlit login exchanges AccessToken → workload token; `check_workload_token.py` verifies bad JWT reject
- Added `githubpoc/agentcore/jwt-authorizer.json` + `scripts/apply_jwt_authorizer.py`; set `aws-targets.json`; env keys for workload/runtime

## 2026-07-22 00:01 +05:30 — Runtime JWT in agentcore.json

- Moved Cognito `CUSTOM_JWT` authorizer onto `githubWorkflow` in `agentcore.json`
- Removed `jwt-authorizer.json` + `apply_jwt_authorizer.py`; docs/env now point at `agentcore deploy`

## 2026-07-22 00:17 +05:30 — Fix Windows deploy path-with-spaces

- Root cause: AgentCore CLI joins `uv` args without quoting on Windows, breaking paths under `Prajwal Nivangune`
- Added `deploy-windows.ps1` (junction `C:\ac-githubpoc`); deployed runtime `githubpoc_githubWorkflow-QFu5je90hW` and set `AGENTCORE_RUNTIME_ARN`

## 2026-07-22 00:43 +05:30 — Wire bootcamp Gateway (IAM)

- Point `githubWorkflow` MCP client at bootcamp gateway URL with SigV4 via `mcp-proxy-for-aws`
- Added `connections.bootcamp-gateway` + `GATEWAY_BOOTCAMP_GATEWAY_URL` in `agentcore.json` / `.env.shared`

## 2026-07-22 01:22 +05:30 — D1-C GitHub via AgentCore Identity

- Connect GitHub now uses `GetResourceOauth2Token` (`USER_FEDERATION`) + `CompleteResourceTokenAuth` on provider `github-prajwal`
- Created workload `githubWorkflowUi` with `allowedResourceOauth2ReturnUrls=http://localhost:8501/` (IAM blocked Update on `githubWorkflow`)
- UI fetches vaulted GitHub token at issue-create time; Cognito↔GitHub map still in `.data/`
