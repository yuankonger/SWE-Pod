- Python 3.14, with every requirement of the repository installed in `/venv`. Nothing needs to be installed.
- Before running tests, generate the translations once: `python3 -m script.translations develop --all` (a second). Tests match messages that come from them.
- Run tests a file or a directory at a time, with at most two workers: `python3 -m pytest --timeout=9 -n 2 tests/helpers/test_device_registry.py`. With more workers, or the whole suite at once, the machine runs out of memory.
- To run Home Assistant itself: `python3 -m homeassistant -c <a configuration directory> --skip-pip`.
- `INTERFACE.md` lists the names the hidden tests import that do not exist yet. Use exactly those names and places.

## The running company

- This repository is a clone of the company's git server (`origin`), which decides who may push where. `main` there is what is deployed and what is judged.
- It runs as Home Assistant, at `http://core:8123/`, with the demo integration (`kitchen_sink`) set up and an owner who can sign in (`owner` / `owner-password`). It serves the frontend as last deployed, and keeps its configuration and registries across deploys.
- CI and deploy are at `http://ci:8080/`. Whenever `main` of a repository moves it deploys that repository, then tests the systems together as they run: that each started, that Home Assistant answers over its WebSocket API as its owner, that every command the frontend sends is one core registers, and that the devices core lists have every field the frontend's own types for that answer require. `curl http://ci:8080/` shows the latest run and `curl http://ci:8080/runs` every run.
- The other system, `frontend`: the frontend's production build, served by core at `http://core:8123/`. A deploy builds it again (about a minute); reload the page to get it.
