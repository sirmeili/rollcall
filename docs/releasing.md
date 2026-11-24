# Releasing

RollCall follows the `/release` skill's conventions for releases: release candidates, a release record issue and a sign-off. The skill and a person releasing by hand both follow this page, which gives only RollCall's own parts. The conventions themselves are the skill's and aren't repeated here, but the **App release** workflow (`.github/workflows/app-release.yml`) relies on these:

- **The release record** is one open issue titled exactly `App release <version>`, such as `App release 1.3.0`, labelled `release-check` from the start. The [release record template](../.github/ISSUE_TEMPLATE/release-record.md) makes one by hand.
- **`release-approved`** is added to the record at sign-off, never before, and removed whenever a new release candidate is published. A release candidate published by hand must remove it too (`gh issue edit <record> --remove-label release-approved`), or an older candidate's approval would pass the gate for the new one. Only people with write or triage access can add a label, so the label is the approval; see [ADR-0024](adr/0024-release-candidates-share-the-final-version-code.md).
- **Comment lines**, each on a line of its own: `Candidate: <tag> <40-character commit>` for each release candidate, `Result: <step id> <pass|fail|waived> <candidate tag> <flavor>: <what the tester saw, or the waiver's reason>` for each result, and `Signed off: <40-character commit> (<candidate tag>)` at sign-off. The workflow reads none of them: they are the human record.
- **The record closes** only after the final release is out, with a link to it. A failed publish leaves it open and signed off, ready to try again.

## Target

RollCall has one release target, the Android app.

- **Name:** `App`, so records are titled `App release <version>`.
- **Tags:** `app-v<version>`, such as `app-v1.3.0-rc.1` and `app-v1.3.0`, on a commit in `main`. Releases come only from `main`: there are no maintenance branches.
- **What counts as a change:** anything under `android/` or `web/`. The app holds its own copy of the web app, so a web change reaches phones only in a new release.

The server image (`ghcr.io/sirmeili/rollcall`, published by `.github/workflows/image.yml`) and the scanner firmware are future targets: they don't go through release candidates or records yet.

## Last release

The last release is the newest final `app-v*` tag, release candidates left out:

```sh
git fetch --tags
git tag -l 'app-v*' | grep -v -- '-rc\.' | sort -V | tail -n 1
```

The changes since it are `git log --name-only <last tag>..origin/main -- android web`. Release notes for release candidates and final releases alike start at that tag.

## Versioning

A version is `major.minor.patch`, each part 0 to 99 and not all 0, optionally followed by `-rc.N` for a release candidate, with N from 1 and no leading zero: `1.3.0`, `1.3.0-rc.1`, `1.3.0-rc.12`. The workflow, the Gradle build and `android/scripts/verify-release.sh` refuse anything else, such as `01.3.0`, `1.3.0-rc.01` or `1.3.0-beta`; the dry run refuses it too.

The app's version name is the full version, which Account and Devices show. Its version code comes from `major.minor.patch` alone (`major·10000 + minor·100 + patch`), so a release candidate shares its final release's code and each installs over the other (ADR-0024).

Pick the next version from the last release:

- **Major** when existing phones must be set up again, or the app needs a server that older apps can't use.
- **Minor** for a new feature or screen a user can see.
- **Patch** for fixes and wording only.

A major or minor version runs the whole checklist (see [Checklist](#checklist)).

## Release candidate

Every release has at least one release candidate, numbered from `rc.1` for each version. Pick the next number from the existing tags (`git tag -l 'app-v1.3.0-rc.*'`), then tag `main`:

```sh
git switch main && git pull
git tag app-v1.3.0-rc.1
git push origin app-v1.3.0-rc.1
```

The **App release** workflow builds both flavors at that version, signs and checks them, and publishes a GitHub prerelease titled **RollCall app 1.3.0-rc.1**. It refuses a malformed version ([Versioning](#versioning)), a commit not in `main`, and a release candidate for a version whose final tag already exists: pick the next version instead. [Final release](#final-release) lists every refusal.

Then, on the record:

1. Post `Candidate: app-v1.3.0-rc.1 <commit>`, with the commit from `git rev-list -n 1 app-v1.3.0-rc.1`.
2. Remove `release-approved` if the record carries it: `gh issue edit <record> --remove-label release-approved`.

Check the release candidate, on its release page or with `gh release view app-v1.3.0-rc.1`:

- it is a prerelease, and GitHub's **Latest** release is still the last final release;
- `rollcall-1.3.0-rc.1-google.apk` and `rollcall-1.3.0-rc.1-foss.apk` are both attached.

A fix found while testing merges into `main` through a pull request as usual, then goes out as the next release candidate (`rc.2`). Merges after the last release candidate wait for the next version.

## Installing a release candidate

Everyday phones keep their Obtainium setup ([android/README.md, Installing on a phone](../android/README.md#installing-on-a-phone-releases-with-obtainium)) and are never offered a release candidate.

A test phone is a phone set up with the release app from Obtainium, then changed once so it takes release candidates too. In Obtainium, edit RollCall and set:

- **Include prereleases:** on.
- **Version string extraction RegEx:** `(\d+\.\d+\.\d+(?:-rc\.\d+)?)`, so the tag `app-v1.3.0-rc.1` reads as `1.3.0-rc.1`, the version the app reports.

Keep the flavor's APK filter. Obtainium then offers each release candidate as an update over the current release, then each later release candidate, then the final release (`1.3.0` over `1.3.0-rc.2`). Each installs in place, so the phone stays set up throughout and stays a test phone for the next release. Account shows the version installed, such as **RollCall app 1.3.0-rc.1**.

To test the other flavor, download its APK from the release candidate's page and install it over the top, as the checklist's step 42 does.

## Checklist

The phone checklist is in [android/README.md, Checklist](../android/README.md#checklist). Its step ids, flavor marks, Always list, each section's triggers, the shared web code and unmapped-file rules and the full-run triggers are all there; this page doesn't repeat them.

- A release runs the Always steps, plus every section its changes since the last release trigger, unless a full-run trigger fires.
- A changed file no section names makes it a full run, and the record lists the file, so the checklist can name it next time.
- Each step in scope goes in the record as `- [ ] <step id>: <step text> (<flavors>)`, its flavors from the step's mark.
- Results are posted per release candidate, as `Result:` lines on the record. A step marked `[both]` needs a result for each flavor.

## Waivers

Only the owner, the repository's owner `sirmeili`, waives a step, with the reason in its `Result: <step id> waived …` line. A step waived after failing names its bug, which stays open.

## Final release

When every step in scope has a pass or a waiver on the latest release candidate, the owner signs off: the `Signed off:` comment on the record, and the `release-approved` label.

Then tag the final version on the latest release candidate's commit, not on `main`'s tip:

```sh
git fetch --tags
git tag app-v1.3.0 'app-v1.3.0-rc.2^{commit}'
git push origin app-v1.3.0
```

The workflow rebuilds the app at the final version from that commit, because the version name is compiled in. Before building, it checks the tag and refuses, saying what to do and naming a section of this page. Its refusals, for release candidates and final releases alike:

| Tag | The workflow says | What it means | What to do |
| --- | --- | --- | --- |
| Any, and the dry run's version | The version `<version>` must look like 1.2.3, or 1.2.3-rc.1 for a release candidate, each part 0 to 99 with no leading zero and not all 0, and N from 1 with no leading zero (Versioning) | The version isn't `major.minor.patch`, each part 0 to 99 and not all 0, optionally followed by `-rc.N` with N from 1 and no leading zero, such as `app-v1.3.0-rc.01` or `app-v1.3.0-beta`. | Delete the tag and tag the release again with a valid version. |
| Any | The tagged commit `<commit>` is not in main (Release candidate) | The tag is on a commit that isn't in `main`, such as a branch's. | Delete the tag and tag a commit in `main`. |
| Release candidate | `app-v<version>` is already released, so it can't have another release candidate (Versioning, Release candidate) | The final tag for this version exists. | Delete the tag, pick the next version and tag its first release candidate. |
| Final | No release candidate for `<version>` (Release candidate) | No `app-v<version>-rc.N` tag exists. | Delete the tag, then tag and test `app-v<version>-rc.1` first. |
| Final | `app-v<version>` is on `<commit>`, not on the newest release candidate (Final release) | The final tag is on another commit, such as `main`'s tip; the message names the newest release candidate and its commit. | Delete the tag and tag the commit the message names, as above. |
| Final | No open release-check issue `App release <version>` with `release-approved` (Final release) | No open issue titled exactly `App release <version>` has both `release-check` and `release-approved`. | Finish the checklist and sign off, then delete the tag and push it again. |
| Final | `<n>` open release-check issues are titled `App release <version>` with `release-approved` (Final release) | More than one open record matches, so the gate can't tell which is the release's. | Close all but the release's record, then delete the tag and push it again. |

To delete a refused tag before pushing it again:

```sh
git push origin --delete app-v1.3.0
git tag -d app-v1.3.0
```

The workflow doesn't read the sign-off comment, or check that every step passed: that is the skill's job and the owner's. The dry run (**Run workflow** on the Actions page) checks only the version's form, and skips this gate.

After the release, check on its page or with `gh release view app-v1.3.0`:

- it is marked **Latest**, not a prerelease;
- `rollcall-1.3.0-google.apk` and `rollcall-1.3.0-foss.apk` are both attached;
- its notes give the version `1.3.0` and a signing certificate SHA-256 equal to the `RELEASE_CERT_SHA256` variable;
- a test phone updates to it in Obtainium, and Account shows **RollCall app 1.3.0**.

Then close the record with a link to the release.
