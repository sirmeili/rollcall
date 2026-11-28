# Releasing

RollCall follows the `/release` skill's conventions for releases: release candidates, a release record issue and a sign-off. The skill and a person releasing by hand both follow this page, which gives only RollCall's own parts. The conventions themselves are the skill's and aren't repeated here, but the **Release** workflow (`.github/workflows/release.yml`) relies on these:

- **The release record** is one open issue titled exactly `RollCall release <version>`, such as `RollCall release 1.4.0`, labelled `release-check` from the start. The [release record template](../.github/ISSUE_TEMPLATE/release-record.md) makes one by hand.
- **`release-approved`** is added to the record at sign-off, never before, and removed whenever a new release candidate is published. A release candidate published by hand must remove it too (`gh issue edit <record> --remove-label release-approved`), or an older candidate's approval would pass the gate for the new one. Only people with write or triage access can add a label, so the label is the approval; see [ADR-0024](adr/0024-release-candidates-share-the-final-version-code.md).
- **Comment lines**, each on a line of its own: `Candidate: <tag> <40-character commit>` for each release candidate, `Result: <step id> <pass|fail|waived> <candidate tag> <flavor>: <what the tester saw, or the waiver's reason>` for each result, and `Signed off: <40-character commit> (<candidate tag>)` at sign-off. The workflow reads none of them: they are the human record.
- **The record closes** only after the final release is out, with a link to it. A failed publish leaves it open and signed off, ready to try again.

## Target

RollCall has one release target: all of RollCall, the phone app's two flavors (`google` and `foss`) and the server image with its web app, built from one commit, tested together and published under one version ([ADR-0025](adr/0025-one-release-for-the-app-and-the-server.md)).

- **Name:** `RollCall`, so records are titled `RollCall release <version>`.
- **Tags:** `v<version>`, such as `v1.4.0-rc.1` and `v1.4.0`, on a commit in `main`. Releases come only from `main`: there are no maintenance branches. Releases up to 1.3.0 were the app alone, tagged `app-v<version>`; those tags stay.
- **What counts as a change:** anything under `android/`, `web/`, `server/` or `deploy/`, and the image's build files `Dockerfile` and `.dockerignore`. The app holds its own copy of the web app, and everyday servers run only final releases, so a change reaches phones and servers only in a new release.

The scanner firmware joins this release once it exists.

## Previous release

The previous release is the newest final `v*` tag, else (until 1.4.0 is out) the newest final `app-v*` tag, release candidates left out:

```sh
git fetch --tags
last=$(git tag -l 'v*' | grep -v -- '-rc\.' | sort -V | tail -n 1)
[ -n "$last" ] || last=$(git tag -l 'app-v*' | grep -v -- '-rc\.' | sort -V | tail -n 1)
echo "$last"
```

The changes since it are `git log --name-only "$last"..origin/main -- android web server deploy Dockerfile .dockerignore`. Release notes for release candidates and final releases alike start at that tag, so 1.4.0's start at `app-v1.3.0`.

The Release workflow upgrades the previous release's image to each new one in its upgrade test, and a test server runs it before the upgrade ([Testing a release candidate](#testing-a-release-candidate)). Its image is tagged with its version, such as `1.4.0`. `app-v1.3.0` had no versioned image, so its image is the one tagged with that tag's commit, `git rev-list -n 1 app-v1.3.0`.

## Versioning

A version is `major.minor.patch`, each part 0 to 999 and not all 0, optionally followed by `-rc.N` for a release candidate, with N from 1 and no leading zero: `1.4.0`, `1.4.0-rc.1`, `1.4.0-rc.12`. The workflow, the Gradle build and `android/scripts/verify-release.sh` refuse anything else, such as `01.4.0`, `1.4.0-rc.01` or `1.4.0-beta`; the dry run refuses it too. The version comes from the tag alone: no file in the repository holds it.

The app's version name is the full version, which Account and Devices show. Its version code comes from `major.minor.patch` alone (`major·1000000 + minor·1000 + patch`: `1.4.0` is 1004000). A release candidate therefore shares its final release's code, and each installs over the other. Releases up to `1.2.0` used `major·10000 + minor·100 + patch`, whose codes are all lower, so phones on them still update in place (ADR-0024). The image is built with the full version too, and the server reports it in `/api/v1/health` and on Account (**RollCall server 1.4.0**).

Pick the next version from the previous release:

- **Major** when existing phones must be set up again, or a server update needs more than pulling the image and restarting.
- **Minor** for a new feature or screen a user can see, in any part.
- **Patch** for fixes and wording only.

A major or minor version runs the whole checklist (see [Checklist](#checklist)).

## Release candidate

Every release has at least one release candidate, numbered from `rc.1` for each version. Pick the next number from the existing tags (`git tag -l 'v1.4.0-rc.*'`), then tag `main`:

```sh
git switch main && git pull
git tag v1.4.0-rc.1
git push origin v1.4.0-rc.1
```

The **Release** workflow builds both flavors of the app at that version, signs and checks them, builds the image at that version and runs it end to end in the Compose test stack, including the upgrade test from the previous release's image. Only when all of that passes does it push the image as `1.4.0-rc.1` and publish a GitHub prerelease titled **RollCall app and server 1.4.0-rc.1**. It refuses a malformed version ([Versioning](#versioning)), a commit not in `main`, a release candidate for a version whose final tag already exists, and a version not newer than the newest final release: pick the next version instead. [Final release](#final-release) lists every refusal.

Then, on the record:

1. Post `Candidate: v1.4.0-rc.1 <commit>`, with the commit from `git rev-list -n 1 v1.4.0-rc.1`.
2. Remove `release-approved` if the record carries it: `gh issue edit <record> --remove-label release-approved`.

Check the release candidate, on its release page or with `gh release view v1.4.0-rc.1`:

- it is a prerelease titled **RollCall app and server 1.4.0-rc.1**, and GitHub's **Latest** release is still the previous final release;
- `rollcall-1.4.0-rc.1-google.apk` and `rollcall-1.4.0-rc.1-foss.apk` are both attached;
- its notes name the image tag `1.4.0-rc.1` and a digest, and `docker buildx imagetools inspect ghcr.io/sirmeili/rollcall:1.4.0-rc.1` (logged in to `ghcr.io`) shows that digest;
- `latest` is unchanged: `docker buildx imagetools inspect ghcr.io/sirmeili/rollcall:latest` shows the previous final release's digest, not this one's.

A fix found while testing merges into `main` through a pull request as usual, then goes out as the next release candidate (`rc.2`). Merges after the last release candidate wait for the next version.

## Installing a release candidate

Everyday phones keep their Obtainium setup ([android/README.md, Installing on a phone](../android/README.md#installing-on-a-phone-releases-with-obtainium)) and are never offered a release candidate.

A test phone is any phone set up with the release app from Obtainium, then changed once so it takes release candidates too. An Android private space on an everyday phone works as one: install Obtainium inside the private space and add RollCall there, so the private space's RollCall is a separate app with its own setup. In Obtainium, edit RollCall and set:

- **Include prereleases:** on.
- **Version string extraction RegEx:** `(\d+\.\d+\.\d+(?:-rc\.\d+)?)`, so the tag `v1.4.0-rc.1` reads as `1.4.0-rc.1`, the version the app reports.

Keep the title and flavor filters. Obtainium then offers each release candidate as an update over the current release, then each later release candidate, then the final release (`1.4.0` over `1.4.0-rc.2`). Each installs in place, so the app keeps its data, and the phone stays a test phone for the next release. Install a release candidate only when [Testing a release candidate](#testing-a-release-candidate) says to: the test phone has to be set up on the previous release first. Account shows the version installed, such as **RollCall app 1.4.0-rc.1**.

A test phone is only ever set up with the test server, never the live one. To test the other flavor, download its APK from the release candidate's page and install it over the top, as the checklist's step 42 does.

## The test server (once)

The test server is a second stack, `rollcall-candidate`, beside the live one on the same Docker host, with its own port (8001) and its own data volume (`rollcall-candidate_data`). It is set up from [`deploy/candidate/compose.yaml`](../deploy/candidate/compose.yaml) and [`deploy/candidate/.env.example`](../deploy/candidate/.env.example). Its one-shot `prepare` service runs the candidate's image (`CANDIDATE_TAG`) and, with `RESTORE=1`, replaces the test server's data with the newest live backup, scrubbed (`ft-admin restore --for-test`, see [docs/deploy.md, Restoring a backup](deploy.md#restoring-a-backup)): no email, Home Assistant or printers, and none of the household's phones, scanners, machine tokens or push registrations. The server (`ROLLCALL_TAG`) then starts on it, and makes no backups.

In Portainer:

1. **Stack.** Stacks › Add stack, named `rollcall-candidate`, Web editor, and paste `deploy/candidate/compose.yaml`. The registry set up for the live stack ([docs/deploy.md, With Portainer instead](deploy.md#with-portainer-instead)) serves it too.
2. **Settings.** Under Environment variables, load a filled-in copy of `deploy/candidate/.env.example`:
   - `SETTINGS_KEY`: the live server's, from the live stack's Environment variables, or, if the live server has none, the contents of its `/data/settings.key` (Containers › rollcall › Console, `cat /data/settings.key`). The restored Firebase settings, the Cloudflare Access service token and the salt can then be read, so notifications and away-from-home steps work on a test phone. Keep it as private as the live one.
   - `TRUSTED_NETWORKS` and `TZ` as on the live server, and `COOKIE_SECURE` and `FORWARDED_ALLOW_IPS` as in step 4.
   - `ROLLCALL_TAG`, `CANDIDATE_TAG` and `RESTORE=1` as for the first release candidate's restore ([Testing a release candidate](#testing-a-release-candidate), step 3). The stack can't start without both tags, so deploying it is that first restore.
3. **The live backups.** `prepare` reads the live stack's backup volume, `rollcall-backups`, read only. If the live stack keeps its backups on a host path instead ([docs/deploy.md, Backups](deploy.md#backups)), change `prepare`'s `live-backups:/live-backups:ro` to that path, such as `/mnt/backup/rollcall:/live-backups:ro`, and delete the `live-backups:` volume at the bottom of the file. A volume of another name only needs `LIVE_BACKUPS_VOLUME` set to it.
4. **Away from home.** The away-from-home phone steps (22, 23, 29, 50 and 51) need the test server behind the Cloudflare Tunnel and Cloudflare Access, as the live server is ([docs/deploy.md, The reverse proxy](deploy.md#5-the-reverse-proxy)), on a second hostname such as `rollcall-candidate.example.com`:
   1. In the pasted Compose file, add the `candidate` service to the tunnel's network as [A Cloudflare Tunnel](deploy.md#a-cloudflare-tunnel), step 3, does for the live server. The service is named `candidate`, not `rollcall`, because on a shared network Docker answers a service's name with every container of that name, so a second `rollcall` there would take a share of the live hostname's traffic. Its container is `rollcall-candidate`.

      ```yaml
      services:
        candidate:
          # ...as in deploy/candidate/compose.yaml...
          networks:
            - default
            - rollcall-tunnel

      networks:
        rollcall-tunnel:
          external: true
          name: rollcall-tunnel
      ```

   2. If the live server has HTTPS at home ([docs/deploy.md, HTTPS at home with Traefik and split DNS](deploy.md#https-at-home-with-traefik-and-split-dns)), give the `candidate` service Traefik labels of its own, with another router and service name, and add a local DNS entry for the test hostname, as step 6 there does for the live one:

      ```yaml
          labels:
            - traefik.enable=true
            - traefik.docker.network=rollcall-tunnel
            - traefik.http.routers.rollcall-candidate.rule=Host(`rollcall-candidate.example.com`)
            - traefik.http.routers.rollcall-candidate.entrypoints=https
            - traefik.http.services.rollcall-candidate.loadbalancer.server.port=8000
      ```

      Without it, the test phone reaches the test hostname through Cloudflare even at home, where it can't set up or scan.
   3. Set `FORWARDED_ALLOW_IPS` as on the live server (`172.30.0.10`, or `172.30.0.10,172.30.0.20` with Traefik) and `COOKIE_SECURE=true`.
   4. In the Cloudflare dashboard, add a Public Hostname for the test hostname on the same tunnel, pointing at `http://rollcall-candidate:8000`.
   5. In Cloudflare Access, add the test hostname to the RollCall application, so its Allow policy for people and its Service Auth policy for the phones' service token cover it too ([docs/deploy.md, The phone app behind Cloudflare Access](deploy.md#the-phone-app-behind-cloudflare-access)). The restored copy keeps the service token saved in Settings, so there is nothing to enter.

   Then check it as the live server's tunnel is checked ([A Cloudflare Tunnel](deploy.md#a-cloudflare-tunnel)), with the test hostname, and that the live hostname still opens the live server: its Account shows its own version, not the candidate's.

Commands in the test server's Console (Containers › rollcall-candidate › Console) are for looking only. Never run `ft-admin backup` there: the Console's shell has the image's `BACKUP_DIR`, which the server itself is started without, so it would write a backup into the container's own `/backups` volume, nowhere near the live backups, and nothing would use it.

## Testing a release candidate

Each release candidate starts from a fresh restore of the live data on the previous release, so its upgrade is tested from the previous release, never from an earlier candidate. Every step is in Portainer, on the `rollcall-candidate` stack. Where a step says to update the stack, edit its Environment variables, then Update the stack with Re-pull image turned on.

1. Wait for the Release workflow to publish the release candidate, and check it ([Release candidate](#release-candidate)).
2. Optional, for today's data: make a backup on the live server (Containers › rollcall › Console, `ft-admin backup`). The restore takes the newest live backup, which is otherwise last night's.
3. **Restore on the previous release.** Stop the test server first: Containers › rollcall-candidate › Stop. An update runs `prepare` before it replaces the server's container, so a running test server would still have the database open while it is replaced. Then update the stack with:
   - `RESTORE=1`;
   - `ROLLCALL_TAG` the previous release's image ([Previous release](#previous-release)): its version, such as `1.4.0`, or for 1.4.0's candidates the full commit of `app-v1.3.0`, from `git rev-list -n 1 app-v1.3.0`;
   - `CANDIDATE_TAG` this release candidate's image, such as `1.4.0-rc.1`.

   Check Containers › rollcall-candidate-prepare-1 › Logs: it says `restored filament-<time>.db; removed …`. rollcall-candidate then shows healthy.
4. **Set up the test phone on the previous release.** On a test phone with the previous release of the app (Account shows it), sign out or unlink if it is still set up from an earlier candidate: the restore removed its pairing. Then, at home, set it up by signing in to the test server, at the test hostname (`https://rollcall-candidate.example.com`), or `http://<server>:8001` without the tunnel. Choose its start page, as in step 26, which step 48 checks. Don't update the app yet.
5. **Upgrade the test server to the release candidate.** Update the stack with `RESTORE=0` and `ROLLCALL_TAG` set to the release candidate, the same as `CANDIDATE_TAG`. `RESTORE` must be back to 0, or the update restores again. `prepare` logs `RESTORE is not 1`, and the server upgrades the restored database as it starts.
6. **Check the upgrade.** `http://<server>:8001/api/v1/health` answers with the candidate's version, such as `"version": "1.4.0-rc.1"`, and the checklist's step 62 passes. Step 64's first half runs now, before the phone is updated.
7. **Update the test phone.** In Obtainium, update RollCall to the release candidate: the checklist's step 48.
8. **Run the checklist** ([Checklist](#checklist)) on the test phone and in a desktop browser at the test server's address, and post each result on the record. Step 65, when it is in scope, empties the test server, so it runs last.

The next release candidate starts again from step 1. The test server can stay running between releases, or be stopped (Stacks › rollcall-candidate › Stop this stack); its data is replaced at the next restore either way.

## Checklist

The checklist is in [docs/checklist.md](checklist.md). Its step ids, flavor marks, Always list, each section's triggers, the shared web code and unmapped-file rules and the full-run triggers are all there; this page doesn't repeat them.

- A release runs the Always steps, plus every section its changes since the previous release trigger, unless a full-run trigger fires.
- A changed non-test file in the app, web or server source, or under `server/` or `deploy/`, that no section names makes it a full run, and the record lists the file, so the checklist can name it next time. Test files trigger nothing, nor do docs and the checks in `android/scripts/` and `web/scripts/`, which aren't app or web source.
- Each step in scope goes in the record as `- [ ] <step id>: <step text> (<flavors>)`, its flavors from the step's mark.
- Results are posted per release candidate, as `Result:` lines on the record. A step marked `[both]` needs a result for each flavor, and a `[browser]` step one result, with `browser` as its flavor.

## Waivers

Only the owner, the repository's owner `sirmeili`, waives a step, with the reason in its `Result: <step id> waived …` line. A step waived after failing names its bug, which stays open.

## Final release

When every step in scope has a pass or a waiver on the latest release candidate, the owner signs off: the `Signed off:` comment on the record, and the `release-approved` label.

Then tag the final version on the latest release candidate's commit, not on `main`'s tip:

```sh
git fetch --tags
git tag v1.4.0 'v1.4.0-rc.2^{commit}'
git push origin v1.4.0
```

The workflow rebuilds the app and the image at the final version from that commit, because the version is compiled into both, and tests the image again. Before building, it checks the tag and refuses, saying what to do and naming a section of this page. Its refusals, for release candidates and final releases alike:

| Tag | The workflow says | What it means | What to do |
| --- | --- | --- | --- |
| Any, and the dry run's version | The version `<version>` must look like 1.2.3, or 1.2.3-rc.1 for a release candidate (the tag like v1.2.3 or v1.2.3-rc.1), each part 0 to 999 with no leading zero and not all 0, and N from 1 with no leading zero (Versioning) | The version isn't `major.minor.patch`, each part 0 to 999 and not all 0, optionally followed by `-rc.N` with N from 1 and no leading zero, such as `v1.4.0-rc.01` or `v1.4.0-beta`. | Delete the tag and tag the release again with a valid version. |
| Any | The tagged commit `<commit>` is not in main (Release candidate) | The tag is on a commit that isn't in `main`, such as a branch's. | Delete the tag and tag a commit in `main`. |
| Any | `<version>` is not newer than the newest final release, `<tag>`, so latest would move back: pick the next version after `<newest>` (Versioning, Release candidate) | A later final release is already out (the newest final `v*` tag, else `app-v*`), such as `v1.3.9-rc.1` after `v1.4.0`. | Delete the tag, pick the next version after the newest final release and tag its first release candidate. |
| Release candidate | `v<version>` is already released, so it can't have another release candidate (Versioning, Release candidate) | The final tag for this version exists (or, for 1.3.0 and earlier, `app-v<version>`). | Delete the tag, pick the next version and tag its first release candidate. |
| Final | No release candidate for `<version>` (Release candidate) | No `v<version>-rc.N` tag exists. | Delete the tag, then tag and test `v<version>-rc.1` first. |
| Final | `v<version>` is on `<commit>`, not on the newest release candidate `v<version>-rc.<n>` (`<its commit>`) (Final release) | The final tag is on another commit, such as `main`'s tip; the message names the newest release candidate and its commit. | Delete the tag and tag the commit the message names, as above. |
| Final | No open release-check issue `RollCall release <version>` with `release-approved` (Final release) | No open issue titled exactly `RollCall release <version>` has both `release-check` and `release-approved`. | Finish the checklist and sign off, then delete the tag and push it again. |
| Final | `<n>` open release-check issues are titled `RollCall release <version>` with `release-approved` (Final release) | More than one open record matches, so the gate can't tell which is the release's. | Close all but the release's record, then delete the tag and push it again. |

To delete a refused tag before pushing it again:

```sh
git push origin --delete v1.4.0
git tag -d v1.4.0
```

The workflow doesn't read the sign-off comment, or check that every step passed: that is the skill's job and the owner's. The dry run (**Run workflow** on the Actions page) builds, signs and tests everything a tag does with a version you give, publishes nothing, and checks only the version's form, skipping this gate.

Nothing is published unless every check passes. The image's tags are pushed just before the GitHub release is created, so if creating the release fails, the image is already out: delete the tag and push it again, as above, and the workflow pushes the same tags again and creates the release.

After the release, check on its page or with `gh release view v1.4.0`:

- it is titled **RollCall app and server 1.4.0** and marked **Latest**, not a prerelease;
- `rollcall-1.4.0-google.apk` and `rollcall-1.4.0-foss.apk` are both attached;
- its notes give the version `1.4.0`, a signing certificate SHA-256 equal to the `RELEASE_CERT_SHA256` variable, the image tags `1.4.0`, `1.4` and `latest`, and a digest;
- `docker buildx imagetools inspect` shows that digest for each of `ghcr.io/sirmeili/rollcall:1.4.0`, `:1.4` and `:latest`;
- a test phone updates to it in Obtainium, and Account shows **RollCall app 1.4.0**.

Then update the live server ([docs/deploy.md, Updating](deploy.md#updating)): its Account shows **RollCall server 1.4.0**. Close the record with a link to the release.
