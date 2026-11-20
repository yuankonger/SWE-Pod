- Node 24, with the repository's dependencies installed (`node_modules` links to them). Nothing needs to be installed.
- Before running tests, generate what they import once: `./node_modules/.bin/gulp gen-icons-json build-translations build-locale-data`. Then `npx vitest run --config test/vitest.config.ts` (about half a minute), or give it a test file.
- The production build, `IS_TEST=true ./node_modules/.bin/gulp build-app-modern` (about a minute), writes `hass_frontend/`. Home Assistant core serves it when its configuration has `frontend:` with `development_repo:` set to this repository's path.
- `INTERFACE.md` lists the names the hidden tests import that do not exist yet. Use exactly those names and places.

## The running company

- This repository is a clone of the company's git server (`origin`), which decides who may push where. `main` there is what is deployed and what is judged.
- It runs as the frontend's production build, served by core at `http://core:8123/`. A deploy builds it again (about a minute); reload the page to get it.
- CI and deploy are at `http://ci:8080/`. Whenever `main` of a repository moves it deploys that repository, then tests the systems together as they run: that each started, that Home Assistant answers over its WebSocket API as its owner, that every command the frontend sends is one core registers, and that the devices core lists have every field the frontend's own types for that answer require. `curl http://ci:8080/` shows the latest run and `curl http://ci:8080/runs` every run.
- The other system, `core`: Home Assistant, at `http://core:8123/`, with the demo integration (`kitchen_sink`) set up and an owner who can sign in (`owner` / `owner-password`). It serves the frontend as last deployed, and keeps its configuration and registries across deploys.
