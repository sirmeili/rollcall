# Print Requests owns its permissions and its transactions behind one interface

Print Requests is used through one interface, a `PrintRequests` object made for each HTTP request around that request's session (#243). It checks every permission itself, and each action that changes something is one transaction: it checks, changes, commits, runs the work that must wait for the commit (deleting replaced files, notifications, emailed photo copies), and returns the caller's view of the request. Refusals are one `Refused` exception, so nothing is saved. The `api/request*` routes only translate HTTP: they never commit, never send notifications and never decide who may do what. This goes against the rest of the app, where the route commits what it changes (`get_session`).

Why, from #243's grilling (2026-11-23):

- **The order around the commit is a Print Requests rule.** An old model file is deleted, and an email sent, only once the change has committed. When every route had to repeat commit, after-commit work, refresh and read, getting the order wrong meant deleting a file whose change was then lost, or announcing a change that never saved.
- **The returned request has to be the committed one.** A change to holds sets off the retry that runs before commit (ADR-0020), which can move the request to Queued, so the caller's view is read after the commit.
- **The route committing was rejected**, with the module handing back after-commit callbacks: every caller (routes, tests, a later phone path) would have to follow the sequence, and forgetting a step fails silently. **The session committing at the end of the HTTP request was rejected** too: it would change the whole app's transactions, hide where a save happens, and read the response before the retry runs.

## Consequences

- Two Print Requests actions can't share one transaction, and nothing outside Print Requests can include one in its own. Two actions that don't depend on each other can still run one after the other. If an action ever has to be atomic with another, add an internal action that doesn't commit, wrapped by the public one, rather than making routes commit again.
- Reading a request never writes: the shopping list stage it shows no longer commits the dismissals the shopping list clears (ADR-0021).
- `test_module_boundary.py` holds the `api/request*` routes to the interface, its dataclasses and `Refused`, so the rules don't leak back into the routes.
