# Data model — claims, tokens, tags, storage

## Tokens (remain separate)

| Token | Issuer / manager | Used for |
| --- | --- | --- |
| Cognito access / ID JWT | Cognito User Pool | Prove app user identity to AgentCore |
| AgentCore workload token | AgentCore Identity (`GetWorkloadAccessTokenForJWT`) | Represent agent workload + Cognito user; call Identity APIs |
| GitHub OAuth credential | AgentCore Identity (`GetResourceOauth2Token`, USER_FEDERATION) | GitHub API on behalf of user |
| AWS temporary credentials | STS AssumeRole | S3 (and any AWS) project access only |

## Cognito claims (verified)

Minimum claim set after verification:

| Claim | Source | Notes |
| --- | --- | --- |
| `sub` | Cognito | Primary user id |
| `email` | Cognito | Display in UI |
| `cognito:groups` | Cognito groups | Map to RBAC role |
| `role` | Derived from groups or custom claim | Canonical demo values below |
| `project` | Custom claim or server mapping | e.g. `AgentDemo` |
| `environment` | Custom claim or server mapping | e.g. `dev` |
| `github_user_id` | Set after Connect GitHub / mapping | Optional until GitHub linked |

### Canonical roles (Cognito groups)

| Group name | RBAC role string |
| --- | --- |
| `Viewer` | `Viewer` |
| `DocumentationDeveloper` | `DocumentationDeveloper` |
| `Developer` | `Developer` |

If a user is in multiple groups, POC rule: **highest privilege wins** (`Developer` > `DocumentationDeveloper` > `Viewer`). Document any change in `spec.md` before coding.

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
| Body | Task text + Cognito sub + role + project + environment |
| Label | `agent-task` |
| Repo | Demo default `agent-demo` |

Body **SHALL** include a machine-readable line, e.g.:

```text
Requested by Cognito user: <sub>
Project: AgentDemo
Role: DocumentationDeveloper
```

## Agent session context

In-memory / request-scoped context after auth (not browser-trusted):

| Field | Type | Example |
| --- | --- | --- |
| `cognito_sub` | string | `cognito-user-123` |
| `email` | string | `developer@example.com` |
| `role` | enum | `DocumentationDeveloper` |
| `project` | string | `AgentDemo` |
| `environment` | string | `dev` |
| `github_user_id` | string | `987654` |
| `issue_number` | int | `24` |
| `repository` | string | `agent-demo` |
| `allowed_tools` | string[] | `inspect_repository`, `update_documentation` |
| `sts_session_name` | string | `issue-24-user-123` |

## STS session tags

| Key | Value source |
| --- | --- |
| `Project` | verified `project` |
| `Environment` | verified `environment` |
| `UserId` | Cognito `sub` |
| `Role` | verified role |

IAM evaluates `aws:PrincipalTag/Project` (and optionally others) against resource paths.

## S3 layout

Bucket: `agent-project-resources` (name may include account/env suffix in deploy; prefix convention is normative).

```text
s3://agent-project-resources/
  AgentDemo/
    coding-standards.md
    repository-config.json
    task-results/
      issue-24/
        ...
  ProjectB/
    coding-standards.md
    repository-config.json
    task-results/
```

Object key pattern for ABAC:

```text
${Project}/...
```

Resource ARN pattern:

```text
arn:aws:s3:::agent-project-resources/${aws:PrincipalTag/Project}/*
```

## Tool ↔ action matrix

| Tool | Allowed side effects |
| --- | --- |
| `inspect_repository` | Read GitHub repo files / tree |
| `update_documentation` | Edit docs paths only (e.g. `README*`, `docs/**`) — enforce in tool |
| `modify_source_code` | Edit non-doc source paths |

DocumentationDeveloper without `modify_source_code` must fail closed on source paths even if prompt asks.

## Traceability chain

```text
Cognito sub ↔ GitHub user id ↔ Issue #N ↔ Agent session ↔ STS RoleSessionName ↔ PR URL
```

All five **SHOULD** appear in logs for a successful demo run (no secrets).
