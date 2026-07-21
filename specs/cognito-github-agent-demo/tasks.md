# Tasks — implementation checklist

Work top-to-bottom. Check boxes only when the acceptance scenarios that depend on the task can pass. **Do not implement until specs are agreed**; this file is the queue.

**Two developers?** Use [`dev-split.md`](./dev-split.md) for parallel Dev 1 / Dev 2 ownership. This file remains the full ordered backlog.

## Phase 0 — Spec lock

- [ ] Confirm constitution + `spec.md` with stakeholders (Cedar RBAC; ABAC deferred)
- [ ] Confirm AWS account, region, demo repo `agent-demo`

## Phase 1 — Identity (Cognito + AgentCore JWT)

- [ ] Create/configure Cognito User Pool + app client
- [ ] Create demo user Priya (identity only — no Cognito role→tools map)
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
- [ ] Post-login: Welcome, email, `sub`
- [ ] Connect GitHub button + status (connected / not)
- [ ] Create Agent Task form: Repository, Task, Task type
- [ ] Call backend to create labeled GitHub issue with Cognito sub in body

## Phase 4 — Gateway tools + Cedar RBAC

- [ ] Implement `inspect_repository`
- [ ] Implement `update_documentation` (docs paths only)
- [ ] Implement `modify_source_code` (exists so Cedar deny can be demonstrated)
- [ ] Register tools on AgentCore Gateway
- [ ] Create Policy Engine + Cedar policies (permit inspect + docs; forbid source)
- [ ] Attach Policy Engine to Gateway (`LOG_ONLY` then `ENFORCE`)
- [ ] Verify: docs tools succeed; `modify_source_code` denied by Cedar

## Phase 5 — Single-agent task loop

- [ ] On task start: load verified identity → run tools via Gateway → open PR
- [ ] Apply repo changes via GitHub OAuth; open PR
- [ ] Log traceability chain (sub, github user, issue, Cedar decisions, PR)

## Phase 6 — AgentCore project wiring

- [ ] Update `agentcore/agentcore.json` (credentials, auth, gateway, policyEngines)
- [ ] Keep schema-first: no hand-edit of generated CDK as source of truth
- [ ] `agentcore validate` + deploy path documented

## Phase 7 — Acceptance

- [ ] Run full script in `acceptance.md` as Priya
- [ ] Capture evidence: Cognito login, GitHub connect, issue #, Cedar allow/deny, PR URL, log notes
- [ ] Append `version.md` entry when implementation lands

## Deferred (later — not blocking)

- [ ] ABAC: STS AssumeRole + session tags + S3 project prefixes **or** Cedar attribute conditions (path/repo/task type) — see `design.md`

## Explicitly not in this checklist

- Multi-agent orchestration
- Cognito `role` claim → Python tool allowlists
- Prompt-only RBAC
- Implementing S3/STS ABAC before Cedar RBAC is done
