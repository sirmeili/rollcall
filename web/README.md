# RollCall web app

The SvelteKit web app (TypeScript), built to static files that the server serves. The phone app wraps the same build; see [android/README.md](../android/README.md). See the [repository README](../README.md) for the project overview.

## Development

The web app needs Node.js 24. Run these from `web/` before requesting a review, or from the repo root in a subshell (for example `(cd web && npm run test:coverage)`); `npm --prefix web` breaks Vitest's coverage run. CI runs the same checks on every PR that changes `web/`, and on every merge to `main`. Lint is Prettier only; the web app has no ESLint.

```sh
npm ci                 # Install dependencies
npm run check          # Type-check
npm run lint           # Check formatting (fix with npm run format)
npm run test:coverage  # Run tests with the 90% coverage gate
npm run audit          # Audit dependencies
npm run build          # Build to web/build
```

Inner loop, with coverage off: `npx vitest run <test files>`.

Changed-file coverage, without the 90% gate: `npx vitest run <test files> --coverage --coverage.include=<source file> --coverage.thresholds.lines=0 --coverage.thresholds.functions=0 --coverage.thresholds.branches=0 --coverage.thresholds.statements=0`, with one `--coverage.include` per changed source file. A fully covered file prints only in the summary.

- **Build**: `npm run build` writes `web/build`. The server serves it at `/`.
- **Live reload**: start the server on port 8000 (see [server/README.md](../server/README.md#development)), then `npm run dev`. Vite proxies `/api` to it.
- **End-to-end tests**: `npx playwright install chromium` once, then `npm run build` and `npm run test:e2e`. They start the real server on a scratch database.
- **Audit**: `npm run audit` fails on any advisory not approved in `scripts/audit-policy.js`.
- **New packages**: add them with `npm install --save-dev --before=<a date at least 7 days ago> <package>@<version>`, so nothing brand new is pulled in, then run the audit. [CODING_STANDARDS.md](../CODING_STANDARDS.md#dependencies) has the rules.
