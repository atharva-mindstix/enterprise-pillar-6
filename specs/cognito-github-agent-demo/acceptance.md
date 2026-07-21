# Acceptance — final demo scenario

These scenarios are the definition of done for the POC. All must pass with **Priya** unless noted.

## Demo identity

| Attribute | Value |
| --- | --- |
| Cognito user | Priya |
| Group / role | `DocumentationDeveloper` |
| Project | `AgentDemo` |
| Environment | `dev` |
| Repository | `agent-demo` |
| Task | Update README with local deployment instructions |

---

## A1 — Cognito login

**Given** Priya is not signed in  
**When** she chooses Sign in with Cognito and authenticates  
**Then** the UI shows Welcome with her email, Role `DocumentationDeveloper`, Project `AgentDemo`  
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
**And** an agent session is bound to that issue and her verified claims

---

## A4 — Tool RBAC (allow docs)

**Given** Priya’s session role is `DocumentationDeveloper`  
**When** the task is “Update the README installation steps”  
**Then** `inspect_repository` is allowed  
**And** `update_documentation` is allowed  
**And** `modify_source_code` is not available to the agent

---

## A5 — Tool RBAC (deny source)

**Given** Priya’s session role is `DocumentationDeveloper`  
**When** she asks to modify authentication Python source  
**Then** the system denies source modification  
**And** the denial is enforced by missing/blocked tool (not only a system-prompt instruction)

---

## A6 — STS AssumeRole

**Given** a task for issue `#N` has started  
**When** the agent needs AWS project resources  
**Then** it assumes `GitHubTaskExecutionRole` with session tags including `Project=AgentDemo`, `Environment=dev`, `UserId=<sub>`, `Role=DocumentationDeveloper`  
**And** the runtime role itself cannot read project S3 directly

---

## A7 — ABAC allow / deny

**Given** STS session tag `Project=AgentDemo`  
**When** the agent reads `AgentDemo/coding-standards.md`  
**Then** access is allowed  

**When** the agent reads `ProjectB/coding-standards.md`  
**Then** access is denied  
**And** the IAM role/policy documents are unchanged between the two attempts

---

## A8 — Repository outcome

**Given** A1–A7 succeeded for the README task  
**When** the agent completes  
**Then** documentation in `agent-demo` is updated on a branch  
**And** a pull request is opened  
**And** task results are written under the `AgentDemo` S3 prefix  
**And** CloudTrail / CloudWatch / GitHub can show the corresponding activity

---

## A9 — End-to-end checklist (narration order)

Use this as the live demo script:

1. Priya logs in through Cognito.
2. Priya connects GitHub.
3. UI creates GitHub issue `#N` using Priya’s authorization.
4. Cognito JWT identifies Priya and her role.
5. Agent receives only `inspect_repository` and `update_documentation`.
6. Agent assumes `GitHubTaskExecutionRole`.
7. STS session includes `Project=AgentDemo`.
8. Agent reads `AgentDemo/coding-standards.md`.
9. Agent cannot read `ProjectB/coding-standards.md`.
10. Agent updates README.
11. Agent pushes a branch and creates a PR.
12. CloudTrail, CloudWatch, and GitHub show the activity.

**Pass criterion:** Steps 1–12 complete without granting Developer tools or cross-project S3 access.

---

## Negative controls (quick)

| Case | Expected |
| --- | --- |
| No / invalid Cognito JWT | Runtime rejects; no workload token |
| Cognito signed in but GitHub not connected | Cannot create issue / cannot run GitHub tools |
| Browser sends `role=Developer` while JWT is DocumentationDeveloper | Ignored; tools stay DocumentationDeveloper |
| Unknown Cognito group | Fail closed (no tools / deny) |
