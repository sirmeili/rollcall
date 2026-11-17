# Coding Standards

The rules every change in this repo follows. `/code-review` checks a branch against this file. The commands that run the checks are in each area's README: `server/README.md`, `web/README.md` and `android/README.md`.

## Modularity

- Keep files small and focused. No monolithic files.
- Put helper functions and UI components in their own files, in logical, separate directories.

## Naming

- Names in code use the terms in [GLOSSARY.md](GLOSSARY.md). A word on a term's _Avoid_ list appears only with the meaning the glossary keeps it for: `variant` is the tag's variant ID.

## Tests

- Every change comes with tests.
- Each acceptance criterion in the issue has a test that fails when that behaviour breaks.
- A change that touches authentication, input handling or secrets also comes with security tests.
- Each branch keeps unit test coverage at 90% or higher. If it falls below, add tests before asking for a review.
- Code is left out of coverage only as listed in [docs/testing.md, Coverage exclusions](docs/testing.md#coverage-exclusions): code that cannot run without real hardware, covered by a manual checklist instead. A change to an exclusion updates that page.

## Dependencies

These apply to npm, Python, Android (Gradle) packages and base images alike.

- Use a release at least 7 days old. For npm, install with `npm install --save-dev --before=<a date at least 7 days ago> <package>@<version>`.
- Before adding a dependency, check it for known advisories (for example GitHub Advisories, OSV, `npm run audit`, `pip-audit`, `docker scout cves`).
- A dependency with a known advisory, or one younger than 7 days, is used only as an approved exception. Ask the owner first, giving:
  - why this package or version is needed;
  - the advisory and what it allows;
  - a link to the advisory (CVE, GitHub Advisory or Snyk);
  - why the risk is acceptable here.
- An exception needs the owner's written approval. The PR that needs it adds it to [Approved exceptions](#approved-exceptions), and the place that applies it carries a one-line comment pointing at that list.

## Secrets and tag data

Never commit secrets, `.env` files, tag dumps or printer captures (`ft-printer check --save`). Settings are listed in `docs/configuration.md`.

## Architecture decision records

- The reason an ADR in `docs/adr/` gives must be traceable to the issue, a decision from the owner, or the code.
- When the reason isn't known, the ADR says so instead of supplying one.

## Toolchain notes

- **SvelteKit 3** differs from earlier versions: its config goes in `sveltekit({...})` in `web/vite.config.ts` (there is no `svelte.config.js`), the library alias is `#lib` (a `package.json` import) instead of `$lib`, and imports name their `.ts` extension.
- **TypeScript** stays pinned to 6.0, because SvelteKit 3.1 and `svelte-check` require it.
- **Android** builds need JDK 21, with `JAVA_HOME` pointing at it: Gradle 8.14 cannot run on newer JDKs, such as Android Studio's bundled JDK 25.

## Approved exceptions

Each exception the owner approved, with where it is applied. New exceptions are added here in the PR that needs them.

| Exception | Advisory | Reason | Approved | Applied in |
| --- | --- | --- | --- | --- |
| `deepmerge` 4.3.1 | [GHSA-gcqx-w48m-w2h4](https://github.com/advisories/GHSA-gcqx-w48m-w2h4) (CVE-2026-93753), low: prototype poisoning when merging attacker-supplied objects | No fixed version exists. It comes in through `@sveltejs/vite-plugin-svelte`, which SvelteKit requires, and only merges our own build config at build time; it is never shipped to browsers. The audit allows only this advisory, at low severity. | 2026-11-05 | `web/scripts/audit-policy.js` |
| `picomatch` 4.0.7 | [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf), high: ReDoS through single-branch repeated extglobs | No fixed version exists; 4.0.7 is the latest. It comes in through `vite`, `vitest` and `svelte-check` (via `fdir` and `tinyglobby`), and only matches our own globs at build and test time; it is never shipped to browsers or run by the server. The audit allows only this advisory, at up to high severity. | 2026-11-17 | `web/scripts/audit-policy.js` |
| npm 11.21.2, 5 days old when approved (an exception to the 7-day rule) | HIGH advisories in the undici and brace-expansion versions carried by the npm bundled with Node 24 (11.19.1) and by npm 11.21.1; 11.21.2 scans clean | The image's web build stage is thrown away; only the built files are kept. | 2026-11-09 | `Dockerfile`, web build stage |
