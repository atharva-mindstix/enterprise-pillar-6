# Dev 1 / Dev 2 tasklist (parallel)

Two developers, **independent tracks** until a short integration pass. Shared contracts below are the only early agreement required.

**Specs to follow:** `constitution.md`, `spec.md`, `design.md`, `data-model.md`, `acceptance.md`

---

## Shared kickoff (both — 30 min, then split)

Do this together once, then work separately:


| #   | Task                                                        | Owner  |
| --- | ----------------------------------------------------------- | ------ |
| K1  | Lock specs (`constitution` + `spec.md`)                     | Both   |
| K2  | Agree AWS account + region                                  | Both   |
| K3  | Agree names (write in table below)                          | Both   |
| K4  | Create empty GitHub repo `agent-demo` (or confirm existing) | Either |




### Shared contract (fill `.env.shared`)

Minimal env only. Everything else (S3/role/tool/repo names) stays as fixed defaults in the specs.

```text
specs/cognito-github-agent-demo/.env.shared.example  →  .env.shared   (repo root)
```

| Required | Env key |
| --- | --- |
| AWS account | `AWS_ACCOUNT_ID` |
| Region | `AWS_REGION` |
| Cognito pool name | `COGNITO_USER_POOL_NAME` |
| Cognito pool id | `COGNITO_USER_POOL_ID` |
| Cognito app client | `COGNITO_APP_CLIENT_ID` |
| Environment claim | `ENVIRONMENT_CLAIM` |
| Dev owners | `DEV1_NAME`, `DEV2_NAME` |

| Optional | Env key |
| --- | --- |
| Gateway ARN (when created) | `AGENTCORE_GATEWAY_ARN` |

JWT issuer (not stored): `https://cognito-idp.${AWS_REGION}.amazonaws.com/${COGNITO_USER_POOL_ID}`

**Ownership boundary (do not cross without ping):**


| Dev 1 owns                                                                | Dev 2 owns                                                                     |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Cognito, JWT → AgentCore, GitHub OAuth connect, demo UI, create-issue API | IAM/S3/STS, agent tools + RBAC, agent task loop, `agentcore.json` agent wiring |


---



## Dev 1 — Identity, GitHub connect, UI

**Theme:** Who is the user, and how do they authorize GitHub + create a task?

### D1-A — Cognito (independent)

- [ ] D1-A1 Create Cognito User Pool + app client + Hosted UI (or Amplify/SDK config)
- [ ] D1-A2 Create groups: `Viewer`, `DocumentationDeveloper`, `Developer`
- [ ] D1-A3 Create user **Priya** in `DocumentationDeveloper`
- [ ] D1-A4 Set `project=AgentDemo`, `environment=dev` (custom attributes / pre-token Lambda / group→claim — pick one, document in PR)
- [ ] D1-A5 Export: issuer URL, audience/client id, JWKS — hand to Dev 2 for runtime JWT config
- [ ] D1-A6 Verify: can sign in and decode JWT with expected claims/groups



### D1-B — AgentCore JWT + workload token (mostly independent; needs Dev 2 runtime present or local stub)

- [ ] D1-B1 Configure inbound JWT authorizer on AgentCore Runtime (issuer, audience, client, scopes)
- [ ] D1-B2 Wire `GetWorkloadAccessTokenForJWT` for authenticated invokes
- [ ] D1-B3 Verify: bad JWT rejected; good JWT → workload token
- [ ] D1-B4 Document invoke headers / token shape for the UI



### D1-C — GitHub OAuth via AgentCore Identity (independent of IAM/S3)

- [ ] D1-C1 Register GitHub OAuth App (callback URL for AgentCore / demo UI)
- [ ] D1-C2 Configure AgentCore GitHub credential provider
- [ ] D1-C3 Implement Connect GitHub → `GetResourceOauth2Token` (`USER_FEDERATION` + workload token)
- [ ] D1-C4 Handle `authorizationUrl` redirect + return to UI
- [ ] D1-C5 Persist Cognito `sub` ↔ GitHub user id mapping (`data-model.md`)
- [ ] D1-C6 Verify: server can use GitHub credential; UI does **not** store long-lived GitHub token



### D1-D — Demo UI (independent; mock backend OK until APIs ready)

- [ ] D1-D1 Screen: **Sign in with Cognito**
- [ ] D1-D2 After login: Welcome, email, Role, Project (from verified claims / backend, not free-typed)
- [ ] D1-D3 **Connect GitHub** + connected/not status
- [ ] D1-D4 **Create Agent Task** form: Repository, Task, Task type
- [ ] D1-D5 Backend endpoint: create GitHub issue with label `agent-task` + Cognito sub in body
- [ ] D1-D6 UI shows created issue number / link



### Dev 1 done when

- [ ] A1, A2, A3 from `acceptance.md` pass (login, Connect GitHub, create issue)
- [ ] JWT + workload token path works without Dev 2’s tools (empty/stub agent OK)



### Dev 1 handoff artifacts

- Cognito issuer / client id / sample JWT (sanitized)
- GitHub OAuth app + AgentCore provider names
- Mapping store location + schema
- UI URL + how to create an issue as Priya

---



## Dev 2 — AWS ABAC/STS, agent RBAC, task loop

**Theme:** What can the agent do, and against which project AWS resources?

### D2-A — S3 + IAM ABAC (fully independent)

- [ ] D2-A1 Create bucket (agreed name) with prefixes `AgentDemo/` and `ProjectB/`
- [ ] D2-A2 Seed `AgentDemo/coding-standards.md` and `ProjectB/coding-standards.md` (+ `repository-config.json` stubs OK)
- [ ] D2-A3 Create `GitHubTaskExecutionRole` with S3 Get/Put on  
  ```
  `arn:aws:s3:::BUCKET/${aws:PrincipalTag/Project}/*`
  ```
- [ ] D2-A4 Trust policy: allow `GitHubAgentRuntimeRole` `sts:AssumeRole` + `sts:TagSession`
- [ ] D2-A5 Runtime role: **AssumeRole only** — no direct project S3
- [ ] D2-A6 CLI/script verify: tagged `Project=AgentDemo` can read AgentDemo, **cannot** read ProjectB



### D2-B — Agent tools + RBAC (independent of UI; use fixture claims)

- [ ] D2-B1 Implement `inspect_repository` (GitHub token via env/fixture until Dev 1 wiring)
- [ ] D2-B2 Implement `update_documentation` (docs paths only)
- [ ] D2-B3 Implement `modify_source_code`
- [ ] D2-B4 Role → tools map at agent construction (`Viewer` / `DocumentationDeveloper` / `Developer`)
- [ ] D2-B5 Backend deny if unauthorized tool invoked (not prompt-only)
- [ ] D2-B6 Unit/self-check: DocumentationDeveloper never gets `modify_source_code`



### D2-C — STS inside agent (depends on D2-A only)

- [ ] D2-C1 On task start: AssumeRole with tags `Project`, `Environment`, `UserId`, `Role`
- [ ] D2-C2 Role session name like `issue-N-user-<sub>`
- [ ] D2-C3 Read coding standards with temp creds; log cross-project deny attempt
- [ ] D2-C4 Write `AgentDemo/task-results/issue-N/` after run



### D2-D — Task loop + AgentCore wiring (can stub Cognito claims until integrate)

- [ ] D2-D1 Load verified claims (or fixture) → filter tools → AssumeRole → run tools → open PR
- [ ] D2-D2 Log chain: sub, github user, issue, session, PR URL
- [ ] D2-D3 Update `agentcore/agentcore.json` for agent/credentials/gateway/policies as needed (schema-first)
- [ ] D2-D4 `agentcore validate`; document deploy/dev commands



### Dev 2 done when

- [ ] A4–A8 from `acceptance.md` pass with **fixture** Cognito claims + PAT/fixture GitHub if needed
- [ ] ABAC allow/deny demo works without the UI



### Dev 2 handoff artifacts

- Role ARNs, bucket name, seed object keys
- How to invoke agent locally with fixture payload (role, project, issue #)
- Tool allow/deny evidence for DocumentationDeveloper

---



## Integration (both — after tracks meet)

Only after Dev 1 A1–A3 and Dev 2 A4–A8 (fixture) are green:


| #   | Task                                                                        | Who            |
| --- | --------------------------------------------------------------------------- | -------------- |
| I1  | Point UI JWT at live runtime authorizer; drop fixtures                      | Both           |
| I2  | Agent uses real workload token + GitHub federation (no PAT fixture)         | Both           |
| I3  | Create Task from UI → real issue → agent run → PR                           | Both           |
| I4  | Full `acceptance.md` A1–A9 as Priya                                         | Both           |
| I5  | Capture evidence (screens + issue # + PR URL + CloudTrail/CloudWatch notes) | Either         |
| I6  | Append `version.md` entry for the implementation batch                      | Whoever merges |


---



## Parallel calendar (suggested)

```text
Day 0     Both: kickoff + shared contract table
Day 1–2   Dev1: D1-A, D1-D (UI mock)     |  Dev2: D2-A, D2-B
Day 2–3   Dev1: D1-B, D1-C               |  Dev2: D2-C, D2-D
Day 4     Both: Integration I1–I6 + acceptance
```

---



## Do not block each other on


| Temptation                   | Instead                                        |
| ---------------------------- | ---------------------------------------------- |
| Dev 2 waits for real Cognito | Use fixture claims matching `data-model.md`    |
| Dev 1 waits for real tools   | Stub agent / “accepted” invoke that returns OK |
| Dev 2 waits for UI           | CLI/`agentcore invoke` with fixture payload    |
| Dev 1 waits for S3/STS       | Out of scope for Dev 1 until integration       |


---



## Explicitly out of scope (either)

- Multi-agent orchestration
- One IAM policy per project (kills ABAC demo)
- Prompt-only RBAC
- Trusting `role` / `project` from the browser body

