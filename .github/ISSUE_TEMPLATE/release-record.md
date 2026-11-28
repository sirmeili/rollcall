---
name: App release record
about: The record of one app release, from its first release candidate to the final release (docs/releasing.md)
title: "App release <version>"
labels: release-check
---

<!-- Replace <version> in the title with the final version, such as 1.3.0, exactly: the App release workflow finds this record by its title. Follow docs/releasing.md. -->

## Version

<!-- The final version, such as 1.3.0, and why it is a major, minor or patch release (docs/releasing.md, Versioning). -->

## Changes

<!-- The pull requests merged since the last release that touch android/ or web/, the checklist sections each triggers, any full-run trigger that fired, and any unmapped file (docs/releasing.md, Checklist). -->

## Steps

<!-- The Always steps and every step of the triggered sections, from docs/checklist.md, one per line:
- [ ] <step id>: <step text> (<flavors>)
-->

## Recording a result

Test on the latest release candidate, installed as [docs/releasing.md](https://github.com/sirmeili/rollcall/blob/main/docs/releasing.md#installing-a-release-candidate) says. Post each result as a comment, on a line of its own:

```text
Result: <step id> <pass|fail|waived> <candidate tag> <flavor>: <what you saw>
```

For example, `Result: 5 pass app-v1.3.0-rc.1 google: buzzed, beeped and showed the spool`. A step marked `[both]` needs one line per flavor. On a fail, open a bug, link it from the line, and leave the step unticked. Only the owner waives a step, with the reason after the colon.
