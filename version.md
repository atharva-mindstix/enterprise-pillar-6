# Development log

Running append-only changelog of code changes in this project.

## 2026-07-21 14:05 +05:30 — Project changelog rule

- Added `.cursor/rules/version-changelog.mdc` so the agent always appends change summaries here after code edits (append-only, never delete)

## 2026-07-21 14:09 +05:30 — Cognito + GitHub agent demo specs

- Added `specs/` with constitution and SDD package for Cognito auth, GitHub OAuth, RBAC tools, ABAC/STS, UI, and acceptance (no implementation)

## 2026-07-21 14:10 +05:30 — Changelog entries include time

- Updated `version-changelog.mdc` entry format to `YYYY-MM-DD HH:MM ±HH:MM`; aligned existing `version.md` headings
