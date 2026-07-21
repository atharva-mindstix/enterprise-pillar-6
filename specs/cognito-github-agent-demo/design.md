# Design — Cognito + GitHub single-agent demo

## Architecture (target)

```text
User logs in with Cognito
        ↓
Cognito JWT reaches AgentCore Runtime
        ↓
User connects GitHub through OAuth (AgentCore Identity)
        ↓
User submits coding task (UI creates GitHub issue)
        ↓
Single agent processes issue
        ↓
Agent invokes tools via AgentCore Gateway
        ↓
Cedar Policy Engine allow/deny (RBAC)
        ↓
Agent updates repository and creates PR (GitHub OAuth)
```

**Deferred (later phase):** STS AssumeRole + S3 ABAC for project-scoped AWS resources.

## Component map

| Component | Responsibility |
| --- | --- |
| **Demo UI** | Cognito login; Connect GitHub; Create Agent Task; show email/`sub` |
| **Cognito User Pool** | Users + identity JWT (`sub`, `email`, …) — **not** used for tool RBAC |
| **AgentCore Runtime** (`githubWorkflow`) | JWT inbound auth; agent invoke |
| **AgentCore Identity** | `GetWorkloadAccessTokenForJWT`; GitHub OAuth provider; `GetResourceOauth2Token` |
| **AgentCore Gateway** | Exposes the three demo tools as MCP/gateway targets |
| **Policy Engine (Cedar)** | Permit/forbid tool invocations (`ENFORCE` for acceptance) |
| **Agent app** (`app/githubWorkflow`) | Task loop; call tools; GitHub PR |
| **GitHub** | Issues (`agent-task`), branches, PRs via user OAuth |

## Authentication & GitHub connect flow

```text
1. User signs in through Cognito
2. UI receives Cognito access/ID token
3. UI sends token to AgentCore Runtime
4. AgentCore validates issuer, audience, client, scopes, claims
5. GetWorkloadAccessTokenForJWT → workload token (agent + Cognito user)
6. User clicks Connect GitHub
7. GetResourceOauth2Token(GitHub provider, USER_FEDERATION, workload token)
8. If needed → authorizationUrl → redirect to GitHub
9. User approves
10. AgentCore stores/manages GitHub OAuth credential
```

References:

- [Inbound JWT authorizer](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/inbound-jwt-authorizer.html)
- [GitHub IdP in AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-idp-github.html)
- [GitHub OAuth apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps)

## Task / issue flow (preferred)

```text
UI form (repo, task, type)
  → Backend creates GitHub issue with label agent-task
  → Issue body/comments include Cognito sub
  → Agent session bound to issue + verified identity
  → Tool calls go through Gateway
  → Cedar permit/forbid
  → Mutate repo via GitHub OAuth tools
  → Open PR
```

## User-context propagation

```text
Cognito JWT
    ↓
AgentCore workload token
    ↓
Agent session
    ↓
Gateway tool call
    ↓
Cedar Policy Engine (RBAC)
    ↓
GitHub task (OAuth)
```

Claims source for identity: Cognito access/ID token (`sub`, `email`; `github_user_id` after Connect GitHub mapping).

**Do not** accept “allow source tools” overrides from the browser or issue body.

## RBAC design (Cedar)

All three tools are registered on the Gateway. Authorization is Cedar on the Policy Engine attached to that Gateway.

Illustrative Cedar (syntax may need alignment to the Gateway’s generated schema at deploy time):

```cedar
// Documentation agent: allow inspect + docs; deny source
permit (
  principal,
  action == Action::"inspect_repository",
  resource
);

permit (
  principal,
  action == Action::"update_documentation",
  resource
);

forbid (
  principal,
  action == Action::"modify_source_code",
  resource
);
```

Bring-up: attach Policy Engine in `LOG_ONLY`, verify decisions in logs, then switch Gateway `policyEngineConfiguration.mode` to `ENFORCE`.

Declare engines/policies in `agentcore.json` (`policyEngines` + gateway `policyEngineConfiguration`) — schema-first; see AgentCore Policy guide.

Demo expectations:

| Prompt | Expected |
| --- | --- |
| Update README installation steps | Cedar allows `inspect_repository` + `update_documentation` |
| Modify authentication Python code | Cedar denies `modify_source_code` (not prompt-only) |

### Why not Cognito `role` → tools?

That pattern duplicates authorization in app code and fights AgentCore’s Gateway Policy Engine. For this POC, **one documentation-oriented agent** + Cedar is enough to show real RBAC. Finer per-user roles can be added later (JWT attributes / groups as Cedar principals) without changing the three tool names.

## Deferred ABAC (ideas — not required now)

Pick one later; do not block Cognito / GitHub / Cedar work:

| Option | Idea | Pros |
| --- | --- | --- |
| **A. STS + S3** (original) | AssumeRole with `Project` tag; IAM `${aws:PrincipalTag/Project}/*` | Classic AWS ABAC story |
| **B. Cedar attributes (no S3)** | Conditions on repo, path prefix, or task type (e.g. docs paths only) | Stays agent/gateway-native; no bucket |
| **C. Hybrid** | Cedar for tools; STS+S3 only when AWS project files are needed | Clear split |

Recommendation for “after Cedar works”: start with **B** if you only need agent-level boundaries; add **A** when you want a CloudTrail/IAM ABAC demo.

## Mapping to existing repo

| Area | Current | Target |
| --- | --- | --- |
| `agentcore/agentcore.json` | Runtime only; empty credentials/gateways/policies | Cognito JWT auth, GitHub OAuth provider, Gateway + Policy Engine + Cedar |
| `app/githubWorkflow` | Stub tools | Real tools + task loop; rely on Gateway/Cedar for deny |
| UI | Cognito login shell | Connect GitHub + Create Task (live) |
| IAM / S3 | — | Deferred |

## Design decisions (locked for this POC)

1. **Single agent** — no multi-agent split.
2. **UI creates issues** — preferred over manual-only mapping.
3. **Three tools only** — names fixed in `spec.md` R6.
4. **Cedar on Gateway** is the RBAC boundary (not Cognito role maps).
5. **ABAC / STS / S3 deferred**.
6. **Fail closed** on missing GitHub federation; Cedar default-deny for tools.
