# Development log

Running append-only changelog of code changes in this project.

## 2026-07-21 14:05 +05:30 — Project changelog rule

- Added `.cursor/rules/version-changelog.mdc` so the agent always appends change summaries here after code edits (append-only, never delete)

## 2026-07-21 14:09 +05:30 — Cognito + GitHub agent demo specs

- Added `specs/` with constitution and SDD package for Cognito auth, GitHub OAuth, RBAC tools, ABAC/STS, UI, and acceptance (no implementation)

## 2026-07-21 14:10 +05:30 — Changelog entries include time

- Updated `version-changelog.mdc` entry format to `YYYY-MM-DD HH:MM ±HH:MM`; aligned existing `version.md` headings

## 2026-07-21 14:48 +05:30 — Dev 1 / Dev 2 parallel tasklist

- Added `specs/cognito-github-agent-demo/dev-split.md` with independent Dev 1 (identity/UI/GitHub) and Dev 2 (IAM/S3/STS/agent) checklists plus integration pass

## 2026-07-21 14:56 +05:30 — Shared contract env file

- Added `.env.shared` + `.env.shared.example` for Day-0 shared contract; gitignore local env; pointed `dev-split.md` at the env file

## 2026-07-21 15:28 +05:30 — Minimal shared env

- Slimmed `.env.shared` / example to AWS + Cognito + optional `AGENTCORE_GATEWAY_ARN` + dev owners; other names stay as spec defaults

## 2026-07-21 15:40 +05:30 — Remove Cognito group RBAC from specs

- Specs now use verified custom `role` claim only (no `cognito:groups`); updated spec, design, data-model, tasks, acceptance, and dev-split

## 2026-07-21 15:45 +05:30 — githubWorkflow system prompt

- Added `specs/cognito-github-agent-demo/system-prompt.md` and runtime `system_prompt.md` derived from spec R5–R9
- Wired `prompt.py` + `main.py` to load the prompt and optionally inject verified session context
