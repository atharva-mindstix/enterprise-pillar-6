# Data model — claims, tokens, storage

## Tokens (remain separate)

| Token | Issuer / manager | Used for |
| --- | --- | --- |
| Cognito access / ID JWT | Cognito User Pool | Prove app user identity to AgentCore |
| AgentCore workload token | AgentCore Identity (`GetWorkloadAccessTokenForJWT`) | Represent agent workload + Cognito user; call Identity APIs |
| GitHub OAuth credential | AgentCore Identity (`GetResourceOauth2Token`, USER_FEDERATION) | GitHub API on behalf of user |

> STS temporary credentials / S3 ABAC: **deferred** (not part of current POC data model).

## Cognito claims (verified)

Minimum claim set after verification:

| Claim | Source | Notes |
| --- | --- | --- |
| `sub` | Cognito | Primary user id |
| `email` | Cognito | Display in UI |
| `github_user_id` | Set after Connect GitHub / mapping | Optional until GitHub linked |

**Not used for tool RBAC in this POC:** Cognito `role`, `project`, `environment`, or `cognito:groups`. Tool allow/deny is Cedar on the Gateway (see below).

## Server-side mapping (Connect GitHub)

Stored when user completes GitHub OAuth (implementation choice: DynamoDB / SSM / AgentCore memory — pick one in tasks; keep minimal):

| Field | Description |
| --- | --- |
| `cognito_sub` | Cognito `sub` |
| `github_user_id` | GitHub numeric user id |
| `github_login` | GitHub username |
| `linked_at` | ISO timestamp |

Required for optional manual-issue path (R4).

## GitHub issue contract (UI-created)

| Field | Value |
| --- | --- |
| Title | From task description (or truncated) |
| Body | Task text + Cognito sub (+ optional task type) |
| Label | `agent-task` |
| Repo | Demo default `agent-demo` |

Body **SHALL** include a machine-readable line, e.g.:

```text
Requested by Cognito user: <sub>
```

## Agent session context

In-memory / request-scoped context after auth (not browser-trusted):

| Field | Type | Example |
| --- | --- | --- |
| `cognito_sub` | string | `cognito-user-123` |
| `email` | string | `developer@example.com` |
| `github_user_id` | string | `987654` |
| `issue_number` | int | `24` |
| `repository` | string | `agent-demo` |
| `task_type` | string | `Documentation` |

Tool permission is **not** a client-supplied list; it is the Cedar evaluation result at invoke time.

## Cedar / Gateway RBAC (POC)

| Tool | Expected Cedar result |
| --- | --- |
| `inspect_repository` | permit |
| `update_documentation` | permit |
| `modify_source_code` | forbid / deny |

Policies live in AgentCore Policy Engine; Gateway runs in `ENFORCE` for acceptance.

## Tool ↔ action matrix

| Tool | Allowed side effects |
| --- | --- |
| `inspect_repository` | Read GitHub repo files / tree |
| `update_documentation` | Edit docs paths only (e.g. `README*`, `docs/**`) — also enforce in tool |
| `modify_source_code` | Edit non-doc source paths — **blocked by Cedar** in primary demo |

## Traceability chain

```text
Cognito sub ↔ GitHub user id ↔ Issue #N ↔ Agent session ↔ Cedar decision ↔ PR URL
```

All of the above **SHOULD** appear in logs for a successful demo run (no secrets).
