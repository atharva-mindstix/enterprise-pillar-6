# Dev 1 / Dev 2 tasklist (parallel)

Two developers, **independent tracks** until a short integration pass. Shared contracts below are the only early agreement required.

**Specs to follow:** `constitution.md`, `spec.md`, `design.md`, `data-model.md`, `acceptance.md`

**POC focus:** Cognito + GitHub + **Cedar tool RBAC**. ABAC/S3/STS is deferred.

---

## Shared kickoff (both — 30 min, then split)

Do this together once, then work separately:


| #   | Task                                                        | Owner  |
| --- | ----------------------------------------------------------- | ------ |
| K1  | Lock specs (`constitution` + `spec.md`) — Cedar RBAC, ABAC later | Both   |
| K2  | Agree AWS account + region                                  | Both   |
| K3  | Agree names (write in table below)                          | Both   |
| K4  | Create empty GitHub repo `agent-demo` (or confirm existing) | Either |



### Shared contract (fill `.env.shared`)

Minimal env only. Everything else stays as fixed defaults in the specs.

```text
specs/cognito-github-agent-demo/.env.shared.example  →  .env.shared   (repo root)
```

| Required | Env key |
| --- | --- |
| AWS account | `AWS_ACCOUNT_ID` |
| Region | `AWS_REGION` |
| Cognito pool / client / domain | `COGNITO_USER_POOL_*`, `COGNITO_APP_CLIENT_ID`, `COGNITO_DOMAIN` |
| Redirect URI (Streamlit) | `COGNITO_REDIRECT_URI` (default `http://localhost:8501/`) |
| Dev owners | `DEV1_NAME`, `DEV2_NAME` |

| Optional | Env key |
| --- | --- |
| Gateway ARN (when created) | `AGENTCORE_GATEWAY_ARN` |
| Client secret (if app client has one) | `COGNITO_APP_CLIENT_SECRET` |

JWT issuer (not stored): `https://cognito-idp.${AWS_REGION}.amazonaws.com/${COGNITO_USER_POOL_ID}`

**Ownership boundary (do not cross without ping):**


| Dev 1 owns                                                                | Dev 2 owns                                                                     |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Cognito, JWT → AgentCore, GitHub OAuth connect, demo UI, create-issue API | Gateway tools, Cedar Policy Engine, agent task loop, `agentcore.json` wiring |


---



## Dev 1 — Identity, GitHub connect, UI

**Theme:** Who is the user, and how do they authorize GitHub + create a task?

### D1-A — Cognito (independent)

- [ ] D1-A1 Create Cognito User Pool + app client — skip if pool already in `.env.shared`
- [ ] D1-A2 Create user **Priya** (identity only)
- [ ] D1-A3 Export: issuer URL, audience/client id, JWKS — hand to Dev 2 for runtime JWT config
- [ ] D1-A4 Verify: can sign in and decode JWT (`sub`, `email`)


### D1-B — AgentCore JWT + workload token (mostly independent; needs Dev 2 runtime present or local stub)

- [ ] D1-B1 Configure inbound JWT authorizer on AgentCore Runtime (issuer, audience, client, scopes)
- [ ] D1-B2 Wire `GetWorkloadAccessTokenForJWT` for authenticated invokes
- [ ] D1-B3 Verify: bad JWT rejected; good JWT → workload token
- [ ] D1-B4 Document invoke headers / token shape for the UI



### D1-C — GitHub OAuth via AgentCore Identity (independent of Cedar)

- [ ] D1-C1 Register GitHub OAuth App (callback URL for AgentCore / demo UI)
- [ ] D1-C2 Configure AgentCore GitHub credential provider
- [ ] D1-C3 Implement Connect GitHub → `GetResourceOauth2Token` (`USER_FEDERATION` + workload token)
- [ ] D1-C4 Handle `authorizationUrl` redirect + return to UI
- [ ] D1-C5 Persist Cognito `sub` ↔ GitHub user id mapping (`data-model.md`)
- [ ] D1-C6 Verify: server can use GitHub credential; UI does **not** store long-lived GitHub token



### D1-D — Demo UI (independent; mock backend OK until APIs ready)

- [ ] D1-D1 Screen: **Sign in with Cognito**
- [ ] D1-D2 After login: Welcome, email, `sub`
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



## Dev 2 — Gateway tools, Cedar RBAC, task loop

**Theme:** What tools exist, and which does Cedar allow?

### D2-A — Tools + Gateway (independent of UI)

- [ ] D2-A1 Implement `inspect_repository`
- [ ] D2-A2 Implement `update_documentation` (docs paths only)
- [ ] D2-A3 Implement `modify_source_code` (for deny demo)
- [ ] D2-A4 Register tools on AgentCore Gateway
- [ ] D2-A5 Document tool names for Cedar schema / policy generation



### D2-B — Cedar Policy Engine (depends on Gateway tools)

- [ ] D2-B1 Create Policy Engine in `agentcore.json`
- [ ] D2-B2 Cedar: permit `inspect_repository` + `update_documentation`; forbid `modify_source_code`
- [ ] D2-B3 Attach engine to Gateway (`LOG_ONLY` first, then `ENFORCE`)
- [ ] D2-B4 Self-check: docs tools succeed; source tool denied by Cedar (not prompt-only)



### D2-C — Task loop + AgentCore wiring

- [ ] D2-C1 On task: verified identity (or fixture) → Gateway tools → open PR
- [ ] D2-C2 Log chain: sub, github user, issue, Cedar decision, PR URL
- [ ] D2-C3 Update `agentcore/agentcore.json` (credentials, gateway, policyEngines)
- [ ] D2-C4 `agentcore validate`; document deploy/dev commands



### Dev 2 done when

- [ ] A4–A6 from `acceptance.md` pass with **fixture** Cognito identity + PAT/fixture GitHub if needed
- [ ] Cedar allow/deny demo works without the UI



### Dev 2 handoff artifacts

- Gateway ARN / name, Policy Engine name
- How to invoke agent locally with fixture payload
- Cedar allow/deny evidence for `modify_source_code`

---



## Integration (both — after tracks meet)

Only after Dev 1 A1–A3 and Dev 2 A4–A6 (fixture) are green:


| #   | Task                                                                        | Who            |
| --- | --------------------------------------------------------------------------- | -------------- |
| I1  | Point UI JWT at live runtime authorizer; drop fixtures                      | Both           |
| I2  | Agent uses real workload token + GitHub federation (no PAT fixture)         | Both           |
| I3  | Create Task from UI → real issue → agent run → PR                           | Both           |
| I4  | Full `acceptance.md` A1–A7 as Priya                                         | Both           |
| I5  | Capture evidence (screens + issue # + PR URL + Cedar deny + log notes)     | Either         |
| I6  | Append `version.md` entry for the implementation batch                      | Whoever merges |


---



## Parallel calendar (suggested)

```text
Day 0     Both: kickoff + shared contract
Day 1–2   Dev1: D1-A, D1-D (UI mock)     |  Dev2: D2-A, D2-B
Day 2–3   Dev1: D1-B, D1-C               |  Dev2: D2-C
Day 4     Both: Integration I1–I6 + acceptance
```

---



## Do not block each other on


| Temptation                   | Instead                                        |
| ---------------------------- | ---------------------------------------------- |
| Dev 2 waits for real Cognito | Use fixture identity matching `data-model.md`  |
| Dev 1 waits for real tools   | Stub agent / “accepted” invoke that returns OK |
| Dev 2 waits for UI           | CLI/`agentcore invoke` with fixture payload    |
| Either waits for S3/STS ABAC | **Deferred** — not required for this POC       |


---



## Explicitly out of scope (either)

- Multi-agent orchestration
- Cognito `role` → Python tool allowlists
- Prompt-only RBAC
- Implementing S3/STS ABAC before Cedar is done
- Trusting authorization from the browser body
