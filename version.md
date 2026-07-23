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

## 2026-07-22 12:50 +05:30 — Switch outbound Identity to pilllar-6-github

- Point `AGENTCORE_GITHUB_PROVIDER` / callback defaults at `pilllar-6-github` (new AgentCore callback UUID)
- Updated `.env.shared`, example env, UI README, and githubpoc README

## 2026-07-22 13:01 +05:30 — Clarify GitHub redirect_uri + better ClientError messages

- Document that GitHub OAuth App callback must be the AgentCore URL (not localhost); UI caption updated
- Fix `ValidationException: None` when AWS Error.Message is null (fall back to full exception text)

## 2026-07-22 13:41 +05:30 — Fix CompleteResourceTokenAuth session binding

- Claim OAuth callback once (Streamlit double-run) and clear query params before Complete
- Use pending Cognito AccessToken + session_uri for CompleteResourceTokenAuth (exact token that started 3LO)
- Pop pending only after success; remint workload after bind

## 2026-07-22 13:48 +05:30 — Fix Cognito PreTokenGeneration Lambda

- Root cause: pool trigger `pillar6-lambda-function-agentcore` handler `lambda_function.lambda_handler` but zip had no `lambda_function` module
- Deployed passthrough `lambda/lambda_function.py` via `update-function-code` so Cognito login works again
## 2026-07-22 13:35 +05:30 — Gateway Lambda tools (single function)

- Added `lambda/` package: `app.py` handler routes `inspect_repository`, `update_documentation`, and `modify_source_code`
- `github_client.py` calls GitHub REST API; `tool_definitions.json` is the Gateway target schema reference

## 2026-07-22 13:42 +05:30 — Consolidate Lambda into single file


- Merged `tools.py`, `github_client.py`, and `paths.py` into `lambda/app.py`; removed split modules

## 2026-07-22 15:01 +05:30 — Harden CompleteResourceTokenAuth bind

- Remint workload immediately before GetResourceOauth2Token; store bind_user_token in pending
- Complete tries bind AccessToken, then IdToken, then userId/sub; use callback session_id
- Disk claim file prevents double Complete across Streamlit session resets

## 2026-07-22 15:18 +05:30 — Complete with IdToken only (no multi-retry)

- AccessToken Complete returned ValidationException and burned the OAuth session; fallbacks then got Invalid or expired session
- Bind mint + Complete + remint on the same Cognito IdToken (OIDC aud); single Complete attempt

## 2026-07-22 15:51 +05:30 — Live Priya test + clearer Complete errors

- Confirmed Cognito login + IdToken mint + GetResourceOauth2Token work; Complete pre-GitHub returns AccessDenied (expected)
- CompleteResourceTokenAuth does not appear in CloudTrail Event history; errors now tagged per step + RequestId
- Disk claim only after success; ValidationException retries pending sessionUri if it differs from callback

## 2026-07-22 16:49 +05:30 — Complete diagnostics A/B/C harness

- Added `ui/diag_complete_tests.py` (Test A userId, Test B isolated AccessToken, Test C provider)
- Test C: `pilllar-6-github` READY; callback matches env; discovery issuer is `token.actions.githubusercontent.com` (suspicious)
- Test A blocked by IAM on `GetWorkloadAccessTokenForUserId`; Test B phase-1 started (needs GitHub authorize + `--session-id`)

## 2026-07-22 17:01 +05:30 — Fix OAuth JSON UTF-8 BOM crash

- `github_oauth._read_json` now uses `utf-8-sig` so Windows-BOM `.data/*.json` files parse
- Stripped BOM from `.data/oauth_claimed.json` (was failing Connect GitHub callback claim)

## 2026-07-22 21:54 +05:30 — Create Task invokes agent

- After GitHub issue create, UI calls `invoke_runtime_with_jwt` with issue/session payload
- Added `agent_task_payload` + longer invoke timeout; `ui/check_task_invoke.py` self-check

## 2026-07-22 22:24 +05:30 — Invoke with Cognito IdToken

- Runtime JWT aud check failed on AccessToken; Create Task invoke now uses IdToken
- Updated invoke helper docs / ui README Bearer note

## 2026-07-23 11:55 +05:30 — Lambda create_pull_request tool

- Added `create_pull_request` to `lambda/app.py` (GitHub pulls API + Fixes #N body helper)
- Extended `lambda/tool_definitions.json` and agent/system prompts so the agent opens a PR after docs commits
- Added `lambda/check_create_pr.py` self-check for body/validation helpers
