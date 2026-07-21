# Spec — Cognito + GitHub single-agent demo

**Status:** Proposed (not yet implemented)  
**Target:** `githubpoc` — runtime `githubWorkflow`  
**Persona:** Priya — Cognito group `DocumentationDeveloper`, project `AgentDemo`

## Purpose

Deliver a POC UI + AgentCore workflow that demonstrates, in one path:

- user identity propagation (Cognito)
- acting on behalf of a user (GitHub OAuth via AgentCore Identity)
- agent workload identity
- tool-level RBAC
- AWS ABAC via STS session tags
- temporary elevated AWS access (AssumeRole)

## Out of scope

- Multiple specialized agents / orchestrator
- Full product UI polish beyond demo screens
- Permanent AWS credentials for project data
- Trusting client-supplied role/project claims

---

## Requirements

### R1 — Cognito authentication

1. The UI **SHALL** provide **Sign in with Cognito**.
2. After login, the UI **SHALL** display at least: user email (or username), role, and project derived from verified claims (or server mapping).
3. The UI **SHALL** send the Cognito access token (or ID token as configured by inbound authorizer) to AgentCore Runtime.
4. AgentCore **SHALL** validate JWT issuer, audience, client, scopes, and claims via inbound JWT authorizer.
5. On success, the system **SHALL** obtain a workload access token via `GetWorkloadAccessTokenForJWT` representing the agent workload and Cognito user.

### R2 — GitHub authorization (separate step)

1. After Cognito login, the UI **SHALL** provide **Connect GitHub**.
2. Connect GitHub **SHALL** call `GetResourceOauth2Token` with:
   - GitHub credential provider
   - `USER_FEDERATION`
   - workload identity token
3. If authorization is required, AgentCore **SHALL** return an `authorizationUrl`; the UI **SHALL** redirect the user to GitHub to approve.
4. After approval, AgentCore **SHALL** securely manage the GitHub OAuth credential; the UI **MUST NOT** store the GitHub access token as long-lived client state.
5. Cognito and GitHub tokens **SHALL** remain separate (see constitution).

### R3 — Task creation via UI (preferred path)

1. The UI **SHALL** provide **Create Agent Task** with fields:
   - Repository (default demo: `agent-demo`)
   - Task description
   - Task type (e.g. Documentation)
2. The backend **SHALL** create a GitHub issue using the user’s GitHub OAuth credential, including:
   - Label: `agent-task`
   - Metadata linking Cognito user (e.g. `Requested by Cognito user: <sub>`)
3. The system **SHALL** establish an explicit link among: Cognito `sub`, GitHub user, GitHub issue, agent session, and resulting PR.

### R4 — Optional manual issues

1. Issues **MAY** be created manually in GitHub.
2. If so, the system **SHALL** maintain `GitHub user ID → Cognito sub` mapping created when the user connects GitHub.
3. Without that mapping, manual issues **MUST NOT** be treated as authenticated user-context tasks.

### R5 — User-context propagation

1. Verified claims **SHALL** include at least:

```json
{
  "sub": "cognito-user-123",
  "email": "developer@example.com",
  "role": "DocumentationDeveloper",
  "project": "AgentDemo",
  "environment": "dev",
  "github_user_id": "987654"
}
```

2. `role` **SHALL** come from Cognito groups (`cognito:groups`) and/or custom claims (e.g. pre-token-generation Lambda). Mapping from group → tool set is defined in R6.
3. Propagation path **SHALL** be: Cognito JWT → workload token → agent session → tool auth → STS tags → GitHub/AWS actions.

### R6 — Agent-level RBAC (three tools)

1. The agent **SHALL** expose exactly these tools (names fixed for the demo):

| Tool | Purpose |
| --- | --- |
| `inspect_repository` | Read repository contents / structure |
| `update_documentation` | Change docs (e.g. README) |
| `modify_source_code` | Change application source |

2. Cognito group → allowed tools:

| Cognito group | Allowed tools |
| --- | --- |
| `Viewer` | `inspect_repository` |
| `DocumentationDeveloper` | `inspect_repository`, `update_documentation` |
| `Developer` | all three |

3. Tool set **SHALL** be constructed from verified role at agent build/invoke time (not from the model’s choice).
4. Denied tools **MUST NOT** be available to the model for that session.
5. Backend enforcement **SHALL** also reject unauthorized tool execution if invoked (Gateway policy and/or in-tool guard). Prompt text alone is insufficient.

### R7 — ABAC for project AWS resources

1. Project data **SHALL** live under S3 prefix layout:

```text
s3://agent-project-resources/
  AgentDemo/
    coding-standards.md
    repository-config.json
    task-results/
  ProjectB/
    coding-standards.md
    repository-config.json
    task-results/
```

2. On task start, the agent **SHALL** AssumeRole into `GitHubTaskExecutionRole` with session tags at least:

| Tag | Example |
| --- | --- |
| `Project` | `AgentDemo` |
| `Environment` | `dev` |
| `UserId` | Cognito `sub` |
| `Role` | `DocumentationDeveloper` |

3. IAM on the task role **SHALL** allow S3 Get/Put only on:

```text
arn:aws:s3:::agent-project-resources/${aws:PrincipalTag/Project}/*
```

4. Same role + policy for all projects; only session tags change (ABAC demonstration).

### R8 — STS AssumeRole in the single-agent workflow

1. Runtime role `GitHubAgentRuntimeRole` **SHALL** have permission to assume `GitHubTaskExecutionRole` and tag the session; it **SHALL NOT** have direct project S3 access.
2. Trust policy on `GitHubTaskExecutionRole` **SHALL** allow `sts:AssumeRole` and `sts:TagSession` from the runtime role.
3. Role session name **SHOULD** include issue id and user id (e.g. `issue-24-user-123`) for CloudTrail clarity.
4. Temporary credentials **SHALL** be used only for AWS resource access during the task; GitHub remains OAuth-based.

### R9 — End-to-end agent outcome

Given a DocumentationDeveloper task to update README:

1. Agent **SHALL** be able to `inspect_repository` and `update_documentation`.
2. Agent **SHALL** read `AgentDemo/coding-standards.md` via tagged STS credentials.
3. Agent **SHALL NOT** successfully read `ProjectB/coding-standards.md`.
4. Agent **SHALL** update the repository documentation and create a pull request.
5. Observability: activity **SHOULD** be visible in CloudTrail / CloudWatch / GitHub as applicable.

### R10 — UI surface (minimum)

After Cognito login the UI **SHALL** show:

```text
Welcome, <email>
Role: <role>
Project: <project>

[Connect GitHub]
[Create Agent Task]
```

Sign-in CTA before login: `[Sign in with Cognito]`.

---

## Non-functional

1. POC-quality: minimal UI, clear demo scripts, no product chrome.
2. Fail closed: missing/invalid JWT, missing GitHub link, or unknown role → deny, do not default to Developer.
3. Logging: include Cognito `sub`, issue number, assumed role session name, and allowed tool set (no secrets).
