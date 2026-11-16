# The web app may be public; machine access stays on the LAN

People may reach the web app from the internet, but only behind an HTTPS reverse proxy. Scanner routes, bearer tokens (device and machine tokens) and the API docs are answered only from `TRUSTED_NETWORKS`; a bearer token from elsewhere gets 403. This replaced the original "LAN only, never exposed" rule: the whole web app is reachable from the internet, and only scanning and machine access stay on the LAN.

## Consequences

A phone away from home can browse through Cloudflare Access but queues its scans until it is back on the LAN.
