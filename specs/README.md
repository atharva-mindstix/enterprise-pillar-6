# Specs (source of truth)

This directory is the **spec-driven** source of truth for the Cognito + GitHub + AgentCore demo.

## How to use

1. Read `constitution.md` first — non-negotiable constraints.
2. Implement against `cognito-github-agent-demo/` in task order (`tasks.md`).
3. Do not invent behavior outside these specs. If something is missing, update the spec before coding.
4. Acceptance is defined in `acceptance.md` — the demo must pass those scenarios.

## Spec set

| Path | Purpose |
| --- | --- |
| [`constitution.md`](./constitution.md) | Hard invariants (auth vs GitHub, trust boundaries) |
| [`cognito-github-agent-demo/spec.md`](./cognito-github-agent-demo/spec.md) | Requirements (MUST / SHALL) |
| [`cognito-github-agent-demo/design.md`](./cognito-github-agent-demo/design.md) | Architecture, flows, component responsibilities |
| [`cognito-github-agent-demo/data-model.md`](./cognito-github-agent-demo/data-model.md) | Claims, tokens, Cedar tool matrix (ABAC deferred) |
| [`cognito-github-agent-demo/system-prompt.md`](./cognito-github-agent-demo/system-prompt.md) | Advisory agent prompt (Cedar is the RBAC boundary) |
| [`cognito-github-agent-demo/tasks.md`](./cognito-github-agent-demo/tasks.md) | Ordered implementation checklist (single queue) |
| [`cognito-github-agent-demo/dev-split.md`](./cognito-github-agent-demo/dev-split.md) | Parallel Dev 1 / Dev 2 tasklists |
| [`cognito-github-agent-demo/.env.shared.example`](./cognito-github-agent-demo/.env.shared.example) | Minimal shared env (AWS, Cognito, optional gateway ARN) |
| [`cognito-github-agent-demo/acceptance.md`](./cognito-github-agent-demo/acceptance.md) | Demo walkthrough as acceptance criteria |

## Existing codebase baseline

Specs target extending `githubpoc/` (AgentCore runtime `githubWorkflow`). Current agent is a stub (`add_numbers` + optional MCP). Specs describe the target demo behavior, not current behavior. Demo UI lives in `ui/` (Streamlit).

## Change process

When requirements change: edit the relevant spec first, then implement. Keep `tasks.md` checkboxes as the work queue.
