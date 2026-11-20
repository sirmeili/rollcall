# Request photos are files beside the model files, not rows in the database

Photos of a finished print are stored as files in the `request-files` folder beside the model files, outside the web root and each under a random name. The database holds only the request they belong to, their stored names and their original name. This is what spec #76 sets out and the owner chose, following the model files from #135.

## Consequences

Nightly backups hold the database only, so they don't include photos. The Admin backs up the photos by backing up that volume or folder themselves, as with model files; [docs/deploy.md](../deploy.md#backups) shows how. A backup restored without that folder leaves requests whose photos are missing.
