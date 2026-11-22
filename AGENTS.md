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

Keep `README.md` accurate. A change to what it describes (status, components, setup, the repository layout, the enclosure or the roadmap) updates it in the same branch.

## Commands

- Working in `server/` or on the Docker image: its commands, including the checks CI runs, are in `server/README.md`.
- Working in `web/`: its commands, including the checks CI runs, are in `web/README.md`.
- Working in `android/`: its commands, including the checks CI runs, are in `android/README.md`.

## Testing

Narrow while working, complete before the PR, with evidence both times.

- **Inner loop**: after each edit, run the tests for the code you changed, with coverage off, using the inner-loop command in that area's README. When the edit touches shared code, widen the loop to the tests of the code that uses it.
- **Final gate**: when the branch is ready for a PR, run every check in the README of each area the branch changes, with coverage on. Run it again only if code changes after it; a clean merge of tested code needs no new run.
- **A failing test**: rerun that test alone, not the suite. A test that passes only on retry is flaky: report it with the first failure's output.
- **Fix the code, or report the failure.** Tests, skips, timeouts and thresholds change only as `CODING_STANDARDS.md` allows.

Before the PR, report this to the user (not in the PR body), filling in every line and writing "none" where it applies. Take `main`'s numbers from the latest successful CI run on `main`; where its log has no count, write "not in the CI log".

```text
Gate:     each command, and the commit it ran on
Counts:   passed / failed / skipped per command   (main: … / … / …)
Flaky:    each test that passed only on retry
Missing:  each test removed or newly skipped, and why
Edited:   each existing test changed, and why
Coverage: total per area, and lines or branches newly missed
Break it: if you touched security rules, changed existing tests or sped up testing:
          on a throwaway copy, break the rule, and name the assert that failed
          in each edited test file
```

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `sirmeili/rollcall`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the five default triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
