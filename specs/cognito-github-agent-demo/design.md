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
RBAC selects permitted tools
        ↓
STS AssumeRole with user/project attributes
        ↓
ABAC controls AWS project resources
        ↓
Agent updates repository and creates PR
```

## Component map

| Component | Responsibility |
| --- | --- |
| **Demo UI** | Cognito Hosted UI / SDK login; Connect GitHub; Create Agent Task form; display role/project |
| **Cognito User Pool** | Users, groups (`Viewer`, `DocumentationDeveloper`, `Developer`), optional custom claims |
| **AgentCore Runtime** (`githubWorkflow`) | JWT inbound auth; agent invoke; tool execution |
| **AgentCore Identity** | `GetWorkloadAccessTokenForJWT`; GitHub OAuth provider; `GetResourceOauth2Token` |
| **Agent app** (`app/githubWorkflow`) | Build agent with role-filtered tools; AssumeRole; run task; GitHub PR |
| **IAM** | `GitHubAgentRuntimeRole` → assume `GitHubTaskExecutionRole` + TagSession |
| **S3** | `agent-project-resources` with per-project prefixes |
| **GitHub** | Issues (`agent-task`), branches, PRs via user OAuth |

## Authentication & GitHub connect flow

```text
1. User signs in through Cognito
2. UI receives Cognito access token
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
  → Agent session bound to issue + verified claims
  → Tools filtered by role
  → STS AssumeRole + session tags
  → Read coding-standards from S3 project prefix
  → Mutate repo via GitHub OAuth tools
  → Open PR
  → Write task-results to S3 project prefix
```

## User-context propagation

```text
Cognito JWT
    ↓
AgentCore workload token
    ↓
Agent session
    ↓
Tool authorization (RBAC)
    ↓
STS session tags (ABAC)
    ↓
GitHub task + AWS resource access
```

Claims source: Cognito access/ID token (`sub`, `email`, `cognito:groups`, custom `project` / `environment` / `github_user_id` as configured). Prefer [Cognito groups](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-user-groups.html) and optional pre-token-generation Lambda for custom claims.

**Do not** accept role/project overrides from request body without matching verified JWT.

## RBAC design

Construct tools at graph build time:

```python
# illustrative — not implementation
if role == "DocumentationDeveloper":
    tools = [inspect_repository, update_documentation]
elif role == "Developer":
    tools = [inspect_repository, update_documentation, modify_source_code]
elif role == "Viewer":
    tools = [inspect_repository]
else:
    deny
```

Also enforce inside tool handlers or AgentCore Gateway policies so a forged tool call still fails.

Demo expectations:

| Prompt | Expected |
| --- | --- |
| Update README installation steps | `inspect_repository` + `update_documentation` allowed; `modify_source_code` unavailable |
| Modify authentication Python code | Denied for DocumentationDeveloper |

## ABAC + STS design

Runtime role: `GitHubAgentRuntimeRole` (no direct project S3).

Task role: `GitHubTaskExecutionRole` with policy using [IAM policy variables / principal tags](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_variables.html):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::agent-project-resources/${aws:PrincipalTag/Project}/*"
    }
  ]
}
```

AssumeRole pattern ([session tags](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_session-tags.html)):

```python
sts.assume_role(
    RoleArn="arn:aws:iam::ACCOUNT:role/GitHubTaskExecutionRole",
    RoleSessionName="issue-24-user-123",
    Tags=[
        {"Key": "Project", "Value": "AgentDemo"},
        {"Key": "Environment", "Value": "dev"},
        {"Key": "UserId", "Value": "cognito-user-123"},
        {"Key": "Role", "Value": "DocumentationDeveloper"},
    ],
)
```

ABAC demo:

| Action | Result |
| --- | --- |
| Read `AgentDemo/coding-standards.md` | Allowed when `Project=AgentDemo` |
| Read `ProjectB/coding-standards.md` | Denied (same role/policy) |

See [ABAC introduction](https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction_attribute-based-access-control.html).

## What STS demonstrates vs GitHub OAuth

```text
Agent runtime identity
        ↓ assumes
Task execution identity
        ↓ constrained by
Temporary credentials + session tags
```

- Agent has its own workload identity.
- Agent does not permanently hold project permissions.
- AWS access exists only for task duration.
- User/project context attaches to the role session (CloudTrail).
- GitHub access still uses GitHub OAuth; STS is AWS-only.

## Mapping to existing repo

| Area | Current | Target |
| --- | --- | --- |
| `agentcore/agentcore.json` | Runtime only; empty credentials/gateways | Add Cognito JWT auth config, GitHub OAuth credential provider, optional Gateway/policies |
| `app/githubWorkflow/main.py` | Stub tools + always-on tool list | Claim extraction, role→tools, STS, real tools |
| UI | None | Minimal Cognito + Connect GitHub + Create Task |
| IAM / S3 | Not in specs yet | CDK or documented IaC for roles, bucket, seed files |

## Design decisions (locked for POC)

1. **Single agent** — no multi-agent split.
2. **UI creates issues** — preferred over manual-only mapping.
3. **Three tools only** — names fixed in `spec.md` R6.
4. **DocumentationDeveloper** is the primary demo login.
5. **Fail closed** on unknown role / missing GitHub federation.
