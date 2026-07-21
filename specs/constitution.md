# Constitution — Cognito + GitHub Agent Demo

These rules override convenience. Implementations that violate them are incorrect even if the demo “works.”

## Auth vs authorization (two steps)

1. **Cognito answers:** Who is using our application?
2. **GitHub OAuth answers:** Has this user authorized the agent to access their GitHub repositories?
3. Cognito JWT and GitHub OAuth credentials **SHALL remain separate tokens**. Never substitute one for the other.

## Trust boundary

1. **Never trust** `user_id`, `github_user_id`, or authorization decisions sent by the browser as authoritative.
2. Identity **SHALL** be read from a **verified Cognito JWT** (or from a server-side mapping keyed by verified Cognito `sub`).
3. AgentCore inbound JWT authorizer **SHALL** validate issuer, audience, client, scopes, and claims before issuing a workload token.
4. **Tool authorization is not decided in the UI or by the LLM.** Cedar policies on the AgentCore Gateway **SHALL** be the security boundary for which tools may run.

## Identity chain

```text
Cognito JWT → AgentCore workload token (JWT federation)
           → Agent session
           → Gateway tool call
           → Cedar Policy Engine (RBAC allow/deny)
           → GitHub task (OAuth credential)
```

1. Workload access for the Cognito user **SHALL** use `GetWorkloadAccessTokenForJWT`.
2. GitHub connect **SHALL** use `GetResourceOauth2Token` with `USER_FEDERATION` and the workload identity token.
3. GitHub credentials **SHALL** be managed by AgentCore Identity (not stored in the UI).

## Security enforcement

1. **RBAC is Cedar on the Gateway — not prompt-only, not Cognito `role` → tool lists in app code.** Tools may be registered on the agent/gateway; Cedar **SHALL** permit or forbid invocation. System prompts are advisory only.
2. **ABAC (STS session tags + S3 / IAM principal tags) is deferred** for a later phase. Do not block the current POC on S3 ABAC.
3. STS (when added later) is for **AWS resources only**. GitHub API access uses the user’s GitHub OAuth credential.

## Scope

1. **Single agent** processes each GitHub issue — no multi-agent orchestration required for this POC.
2. Demo persona is **Priya** on repository **agent-demo** (documentation-oriented task).
3. Prefer the UI creating the GitHub issue (explicit Cognito ↔ GitHub ↔ issue link). Manual GitHub issues are optional and require a maintained `GitHub user ID → Cognito sub` mapping created at Connect GitHub time.

## Spec authority

`specs/` is the source of truth. `agentcore.json` and app code implement the specs; they do not redefine them.
