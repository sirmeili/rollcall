# AGENTS.md

Instructions for every AI agent working in this repo. This is the only instruction file: agent instructions go here, not in an agent-specific file such as `CLAUDE.md`.

## What to read first

1. This file.
2. The issue being worked. The [Roadmap](https://github.com/sirmeili/rollcall/issues/69) issue lists the planned work.
3. `GLOSSARY.md`, and the ADRs in `docs/adr/` for that area.
4. `CODING_STANDARDS.md`, before writing code.
5. `docs/configuration.md` when a setting is added or changed, and `docs/testing.md` when a test layer, coverage exclusion or manual checklist is.
6. The mockups in `docs/mockups/`, for screens.

The archived spec, `docs/archive/SPEC-v1.md`, is background only.

## The issue is the contract

- Make the changes the issue describes, and only those. For behaviour already built, the code and its tests are the record.
- When something is ambiguous, stop and ask.
- Every acceptance criterion ships with its test.
- Build `ready-for-agent` issues. A `needs-info` or blocked issue waits.
- A hard-to-reverse, surprising trade-off gets an ADR in `docs/adr/`, in the same PR.

## Roadmap stubs

`/to-spec` on a Roadmap stub replaces the stub's body in place, keeping its number, and swaps the `roadmap` label for `ready-for-agent`.

## Branches

- `main` changes only through pull requests: commit on a branch.
- `/implement` syncs `main` and checks that the previous PR merged (ask before skipping that check, and say why), then uses one `<type>/<issue#>-<slug>` branch and PR per ticket.
- `/implement-spec` uses one integration branch and PR per spec.
- Make small, logical commits.

## Pull requests

- The body is the `/pr` template only.
- The last commit on the branch ends with `Closes #N` for each issue it resolves.

## README

Keep `README.md` accurate. A change to what it describes (status, components, setup, the repository layout or the enclosure) updates it in the same branch.

## Commands

- Working in `server/` or on the Docker image: its commands, including the checks CI runs, are in `server/README.md`.
- Working in `web/`: its commands, including the checks CI runs, are in `web/README.md`.
- Working in `android/`: its commands, including the checks CI runs, are in `android/README.md`.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `sirmeili/rollcall`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the five default triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
