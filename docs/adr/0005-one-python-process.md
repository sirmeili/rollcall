# One Python process serves the API and the web app

The web app is a SvelteKit single-page app built to static files that FastAPI serves at `/`, instead of server-rendered Jinja2 + HTMX. Production stays one Python process in one image; Node.js is needed only to build and test.
