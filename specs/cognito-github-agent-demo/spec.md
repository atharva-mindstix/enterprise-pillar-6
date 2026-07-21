# Spec — Cognito + GitHub single-agent demo

**Status:** Proposed (not yet implemented)  
**Target:** `githubpoc` — runtime `githubWorkflow`  
**Persona:** Priya — Cognito user; documentation task on repo `agent-demo`

## Purpose

Deliver a POC UI + AgentCore workflow that demonstrates, in one path:

- user identity propagation (Cognito)
- acting on behalf of a user (GitHub OAuth via AgentCore Identity)
- agent workload identity
- **tool-level RBAC via AgentCore Gateway + Cedar policies**

## Out of scope (this POC)

- Multiple specialized agents / orchestrator
- Full product UI polish beyond demo screens
- Cognito `role` / `project` claims driving tool allowlists in application code
- **ABAC via STS session tags + S3** (deferred — see `design.md`)
- Trusting client-supplied authorization overrides

---

## Requirements

### R1 — Cognito authentication

1. The UI **SHALL** provide **Sign in with Cognito**.
2. After login, the UI **SHALL** display at least: user email (or username) and Cognito `sub` from verified claims.
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

1. Verified identity claims **SHALL** include at least:

```json
{
  "sub": "cognito-user-123",
  "email": "developer@example.com",
  "github_user_id": "987654"
}
```

2. `github_user_id` **MAY** be absent until Connect GitHub completes; then it **SHALL** come from the server-side mapping (not the browser).
3. Propagation path **SHALL** be: Cognito JWT → workload token → agent session → Gateway tool invoke → Cedar allow/deny → GitHub actions.
4. **Do not** use Cognito groups (`cognito:groups`) or a Cognito `role` claim as the RBAC mechanism for this POC. Tool RBAC is R6 (Cedar).

### R6 — Agent tool RBAC (Cedar on Gateway)

1. The agent / Gateway **SHALL** expose exactly these tools (names fixed for the demo):

| Tool | Purpose |
| --- | --- |
| `inspect_repository` | Read repository contents / structure |
| `update_documentation` | Change docs (e.g. README) |
| `modify_source_code` | Change application source |

2. Tool authorization **SHALL** be enforced by an **AgentCore Policy Engine** with **Cedar** policies attached to the Gateway (`ENFORCE` mode for the accepted demo; `LOG_ONLY` allowed during bring-up).
3. Demo policy intent (normative for acceptance):

| Tool | Cedar decision (POC documentation agent) |
| --- | --- |
| `inspect_repository` | **permit** |
| `update_documentation` | **permit** |
| `modify_source_code` | **forbid** (or not permitted) |

4. Cedar uses default-deny; `forbid` overrides `permit`. Prompt text and “don’t register the tool in Python” alone are **insufficient** as the security boundary — Gateway + Cedar **SHALL** reject unauthorized tool execution.
5. The model **MUST NOT** successfully execute `modify_source_code` for the primary demo path.

### R7 — Deferred: ABAC for AWS project resources

**Not in scope for the current POC.** Do not implement S3 prefix ABAC / STS session tags until a later phase.

Placeholder (for later agreement): project-scoped AWS access via AssumeRole + `aws:PrincipalTag/Project`, or agent-level Cedar conditions on attributes (path / repo / task type) without S3. See `design.md` → Deferred ABAC.

### R8 — Deferred: STS AssumeRole in the workflow

**Not in scope for the current POC.** GitHub remains OAuth-based; no requirement to AssumeRole for task execution in this phase.

### R9 — End-to-end agent outcome

Given a documentation task to update README:

1. Agent **SHALL** be able to invoke `inspect_repository` and `update_documentation` (Cedar permit).
2. Agent **SHALL NOT** successfully invoke `modify_source_code` (Cedar forbid / deny).
3. Agent **SHALL** update the repository documentation and create a pull request.
4. Observability: activity **SHOULD** be visible in CloudWatch / GitHub (and CloudTrail where applicable).

### R10 — UI surface (minimum)

After Cognito login the UI **SHALL** show:

```text
Welcome, <email>
sub: <sub>

[Connect GitHub]
[Create Agent Task]
```

Sign-in CTA before login: `[Sign in with Cognito]`.

Optional: show Cedar / Gateway policy summary for the demo (e.g. “docs tools allowed; source tool denied”) — not required.

---

## Non-functional

1. POC-quality: minimal UI, clear demo scripts, no product chrome.
2. Fail closed: missing/invalid JWT or missing GitHub link → deny; Cedar default-deny for tools.
3. Logging: include Cognito `sub`, issue number, tool name, Cedar allow/deny decision, and PR URL (no secrets).
