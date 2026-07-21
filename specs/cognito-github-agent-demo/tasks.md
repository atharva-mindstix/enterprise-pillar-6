# Tasks — implementation checklist

Work top-to-bottom. Check boxes only when the acceptance scenarios that depend on the task can pass. **Do not implement until specs are agreed**; this file is the queue.

**Two developers?** Use [`dev-split.md`](./dev-split.md) for parallel Dev 1 / Dev 2 ownership. This file remains the full ordered backlog.

## Phase 0 — Spec lock

- [ ] Confirm constitution + `spec.md` with stakeholders
- [ ] Confirm Cognito pool/groups and custom claim strategy (groups vs pre-token Lambda)
- [ ] Confirm AWS account, region, demo repo `agent-demo`, bucket name

## Phase 1 — Identity (Cognito + AgentCore JWT)

- [ ] Create/configure Cognito User Pool + app client + Hosted UI (or SDK)
- [ ] Create groups: `Viewer`, `DocumentationDeveloper`, `Developer`
- [ ] Create demo user Priya in `DocumentationDeveloper`; set project/environment claims
- [ ] Configure AgentCore Runtime inbound JWT authorizer (issuer, audience, client, scopes)
- [ ] Wire `GetWorkloadAccessTokenForJWT` path for authenticated invokes
- [ ] Verify: invalid JWT rejected; valid JWT yields workload token

## Phase 2 — GitHub OAuth via AgentCore Identity

- [ ] Register GitHub OAuth App; configure AgentCore GitHub credential provider
- [ ] Implement Connect GitHub → `GetResourceOauth2Token` (`USER_FEDERATION`)
- [ ] Handle `authorizationUrl` redirect and callback
- [ ] Persist Cognito↔GitHub mapping (`data-model.md`)
- [ ] Verify: GitHub credential usable server-side without UI storing long-lived token

## Phase 3 — Demo UI (minimum)

- [ ] Sign in with Cognito
- [ ] Post-login: Welcome, email, Role, Project
- [ ] Connect GitHub button + status (connected / not)
- [ ] Create Agent Task form: Repository, Task, Task type
- [ ] Call backend to create labeled GitHub issue with Cognito sub in body

## Phase 4 — IAM / S3 (ABAC + STS)

- [ ] Create S3 bucket `agent-project-resources` with `AgentDemo/` and `ProjectB/` seed files
- [ ] Create `GitHubTaskExecutionRole` + S3 policy using `${aws:PrincipalTag/Project}`
- [ ] Trust policy: allow runtime role `sts:AssumeRole` + `sts:TagSession`
- [ ] Runtime role `GitHubAgentRuntimeRole`: AssumeRole only (no direct project S3)
- [ ] Seed `AgentDemo/coding-standards.md` and `ProjectB/coding-standards.md`
- [ ] Verify: tagged session can read AgentDemo only

## Phase 5 — Agent RBAC tools

- [ ] Implement `inspect_repository`
- [ ] Implement `update_documentation` (docs paths only)
- [ ] Implement `modify_source_code`
- [ ] Map Cognito group/role → tool list at agent construction
- [ ] In-tool or Gateway deny for unauthorized tools
- [ ] Verify DocumentationDeveloper cannot call `modify_source_code`

## Phase 6 — Single-agent task loop

- [ ] On task start: load verified claims → filter tools → AssumeRole with tags
- [ ] Read project coding standards from authorized S3 prefix
- [ ] Attempt cross-project read (expect deny) for demo logging
- [ ] Apply repo changes via GitHub OAuth; open PR
- [ ] Write results under `AgentDemo/task-results/issue-N/`
- [ ] Log traceability chain (sub, github user, issue, session, PR)

## Phase 7 — AgentCore project wiring

- [ ] Update `agentcore/agentcore.json` (credentials, auth, gateway/policies as needed)
- [ ] Keep schema-first: no hand-edit of generated CDK as source of truth
- [ ] `agentcore validate` + deploy path documented

## Phase 8 — Acceptance

- [ ] Run full script in `acceptance.md` as Priya / DocumentationDeveloper / AgentDemo
- [ ] Capture evidence: Cognito login, GitHub connect, issue #, tool allow/deny, S3 allow/deny, PR URL, CloudTrail/CloudWatch notes
- [ ] Append `version.md` entry when implementation lands (not for this specs-only change set if only specs added — follow project changelog rule)

## Explicitly not in this checklist

- Multi-agent orchestration
- Per-project IAM roles/policies (defeats ABAC demo)
- Prompt-only RBAC
