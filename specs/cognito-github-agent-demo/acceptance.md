# Acceptance — final demo scenario

These scenarios are the definition of done for the current POC. All must pass with **Priya** unless noted.

## Demo identity

| Attribute | Value |
| --- | --- |
| Cognito user | Priya |
| Repository | `agent-demo` |
| Task | Update README with local deployment instructions |
| RBAC | Cedar on Gateway: docs tools allow; `modify_source_code` deny |

---

## A1 — Cognito login

**Given** Priya is not signed in  
**When** she chooses Sign in with Cognito and authenticates  
**Then** the UI shows Welcome with her email and Cognito `sub`  
**And** subsequent AgentCore calls carry a Cognito JWT that passes inbound JWT validation

---

## A2 — Connect GitHub (separate step)

**Given** Priya is signed in with Cognito  
**When** she chooses Connect GitHub and approves on GitHub  
**Then** AgentCore holds a federated GitHub OAuth credential for her  
**And** a Cognito `sub` ↔ GitHub user mapping exists  
**And** the UI does not rely on a long-lived GitHub token in local storage as the source of truth

---

## A3 — Create agent task (issue)

**Given** Priya is Cognito-authenticated and GitHub-connected  
**When** she submits Create Agent Task for repo `agent-demo` with a documentation task  
**Then** GitHub issue `#N` exists with label `agent-task`  
**And** the issue references her Cognito `sub`  
**And** an agent session is bound to that issue and her verified identity

---

## A4 — Tool RBAC (Cedar allow docs)

**Given** Gateway Policy Engine is in `ENFORCE` with the demo Cedar policies  
**When** the task is “Update the README installation steps”  
**Then** `inspect_repository` is allowed  
**And** `update_documentation` is allowed  
**And** `modify_source_code` is denied / not successfully executable

---

## A5 — Tool RBAC (Cedar deny source)

**Given** the same Cedar policies  
**When** the agent (or a test client) attempts `modify_source_code`  
**Then** the Gateway / Policy Engine denies the call  
**And** the denial is **not** only a system-prompt instruction

---

## A6 — Repository outcome

**Given** A1–A5 succeeded for the README task  
**When** the agent completes  
**Then** documentation in `agent-demo` is updated on a branch  
**And** a pull request is opened  
**And** CloudWatch / GitHub (and CloudTrail where applicable) can show the corresponding activity

---

## A7 — End-to-end checklist (narration order)

Use this as the live demo script:

1. Priya logs in through Cognito.
2. Priya connects GitHub.
3. UI creates GitHub issue `#N` using Priya’s authorization.
4. Cognito JWT identifies Priya.
5. Agent tool calls go through the Gateway; Cedar allows inspect + docs update.
6. Cedar denies `modify_source_code`.
7. Agent updates README.
8. Agent pushes a branch and creates a PR.
9. Logs show sub, issue, Cedar decisions, PR URL.

**Pass criterion:** Steps 1–9 complete without a successful source-code tool invocation.

---

## Deferred (not acceptance for this POC)

| Scenario | Status |
| --- | --- |
| STS AssumeRole + session tags | Deferred |
| S3 `AgentDemo` allow / `ProjectB` deny (ABAC) | Deferred |

---

## Negative controls (quick)

| Case | Expected |
| --- | --- |
| No / invalid Cognito JWT | Runtime rejects; no workload token |
| Cognito signed in but GitHub not connected | Cannot create issue / cannot run GitHub tools |
| Call `modify_source_code` despite prompt asking for it | Cedar deny |
| Prompt-only “please don’t use source tool” without Cedar | **Insufficient** — must fail A5 |
