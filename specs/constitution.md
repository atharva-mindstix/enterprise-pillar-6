# Constitution — Cognito + GitHub Agent Demo

These rules override convenience. Implementations that violate them are incorrect even if the demo “works.”

## Auth vs authorization (two steps)

1. **Cognito answers:** Who is using our application?
2. **GitHub OAuth answers:** Has this user authorized the agent to access their GitHub repositories?
3. Cognito JWT and GitHub OAuth credentials **SHALL remain separate tokens**. Never substitute one for the other.

## Trust boundary

1. **Never trust** `role`, `project`, `user_id`, `environment`, or `github_user_id` sent by the browser as authoritative.
2. Those values **SHALL** be read from a **verified Cognito JWT** (or from a server-side mapping keyed by verified Cognito `sub`).
3. AgentCore inbound JWT authorizer **SHALL** validate issuer, audience, client, scopes, and claims before issuing a workload token.

## Identity chain

```text
Cognito JWT → AgentCore workload token (JWT federation)
           → Agent session
           → Tool authorization (RBAC)
           → STS session tags (ABAC)
           → GitHub task + AWS resource access
```

1. Workload access for the Cognito user **SHALL** use `GetWorkloadAccessTokenForJWT`.
2. GitHub connect **SHALL** use `GetResourceOauth2Token` with `USER_FEDERATION` and the workload identity token.
3. GitHub credentials **SHALL** be managed by AgentCore Identity (not stored in the UI).

## Security enforcement

1. **RBAC is not prompt-only.** Permitted tools **SHALL** be selected from the verified role when constructing the agent. Backend / Gateway enforcement is the security boundary; system prompts are advisory only.
2. **ABAC is attribute-based.** Project/environment access **SHALL** use STS session tags + IAM policies with `aws:PrincipalTag`, not one IAM policy per project.
3. The AgentCore runtime execution role **SHALL NOT** directly access project S3 (or other project resources). It **SHALL** only be allowed to `sts:AssumeRole` (and `sts:TagSession`) into `GitHubTaskExecutionRole`.
4. STS is for **AWS resources only**. GitHub API access uses the user’s GitHub OAuth credential.

## Scope

1. **Single agent** processes each GitHub issue — no multi-agent orchestration required for this POC.
2. Demo persona is **DocumentationDeveloper** on project **AgentDemo**, repository **agent-demo**.
3. Prefer the UI creating the GitHub issue (explicit Cognito ↔ GitHub ↔ issue link). Manual GitHub issues are optional and require a maintained `GitHub user ID → Cognito sub` mapping created at Connect GitHub time.

## Spec authority

`specs/` is the source of truth. `agentcore.json` and app code implement the specs; they do not redefine them.
