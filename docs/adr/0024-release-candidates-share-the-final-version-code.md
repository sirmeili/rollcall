# Release candidates share the final version code, and the final release is the signed-off candidate rebuilt

The phone checklist needs the release-signed APK, which can't be installed before a release exists: debug builds install as a separate app with their own pairing, so switching flavors and updating from the previous release can't be tested with them. So every app release goes through at least one release candidate, tagged `app-v<version>-rc.<n>` and published as a GitHub prerelease, which Obtainium skips unless **Include prereleases** is on. A candidate's `versionName` is the full version (`1.3.0-rc.1`), but its `versionCode` comes from `major.minor.patch` alone, so a candidate shares its code with the final release. Android installs an equal code over the top, so a test phone goes from `1.2.0` to `rc.1`, `rc.2` and `1.3.0`, updating in place each time and staying set up. The final release is built again from the latest candidate's commit, not copied from it, because the version name is compiled in. The **App release** workflow refuses a final tag that isn't on that commit, or when there isn't exactly one open `App release <version>` issue labelled both `release-check` and `release-approved`. The label is the approval: only people with write or triage access can add it, and the `/release` skill removes it whenever a new candidate is published, so it always means the latest candidate is signed off. The sign-off comment stays as the human record, and the workflow doesn't read it. RollCall adopts the skill's conventions for the record, and the skill closes it only after the final release is out (#269).

## Considered options

- **Codes that count up through the candidates** (for example the version's code times 100 plus the candidate number, with the final release at 99): it would change the existing scheme, cap the candidates per version, and buy nothing, because Android already installs an equal code over the top.
- **A separate test app ID for candidates**: it would install beside the release app with its own pairing, which is the gap release candidates are meant to close.
- **Gating on a closed record**: it deadlocks with closing the record only after the release is out, and a failed publish would leave a closed record with no release.
- **No gate, relying on the procedure**: tagging the final release on the right commit (and keeping release candidates required) already stops an untested commit. The approval label is what stops a tag on a candidate whose checklist isn't finished.
- **Reading the sign-off comment** (the newest `Signed off:` line, from a user with write access, naming the tagged commit): it would catch a label left over from an older candidate, but it needs comment parsing and an author check in the workflow. Removing the label at each new candidate gives the same guarantee more simply.

## Consequences

- A candidate and its final release can't be told apart by version code, only by version name. Obtainium on a test phone compares version strings, so it offers `1.3.0` over `1.3.0-rc.2`.
- A fix found during testing goes through `main` and a new candidate. Merges after the last candidate wait for the next version, and there are no maintenance branches.
- The workflow reads the issue tracker (`issues: read`), so the release depends on the `/release` record's title and labels. A change to those conventions is a change to this workflow.
- A candidate published by hand must also remove `release-approved`. Otherwise an older candidate's approval would pass the gate for the new one.
