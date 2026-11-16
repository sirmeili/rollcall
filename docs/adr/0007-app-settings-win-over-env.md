# A setting saved in the app wins over .env, with exceptions

Most settings can be edited in the app, with `.env` as the starting value and a saved value winning (reversing the earlier plan, where `.env` won). Settings that could lock the admin out or open LAN-only routes, such as `TRUSTED_NETWORKS` and `SETTINGS_KEY`, stay in `.env` only. Secrets saved in the app are encrypted with `SETTINGS_KEY` (or the generated `settings.key`) and never returned or logged.
