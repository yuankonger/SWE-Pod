# Saleor Dashboard (staff back office) of the platform company, at saleor/saleor-dashboard 7ea285835 (3.22.32), with
# its locked dependencies and Playwright's chromium (the dashboard's own @playwright/test, 1.56.1) for browser checks.
# Context: a directory with the dashboard tree under dashboard/.
#     docker build -t seedco-platform-dashboard:1 -f company/platform/dashboard.Dockerfile <context>
#
# Serving: the image's command, `pnpm run dev` (codegen from the tree's own schema files, then the vite development
# server on 0.0.0.0:9000). API_URL names the API the staff's browser calls; __VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS is
# the one host name, besides localhost and IP addresses, that vite answers to (others get 403).
# After the source changes: replace everything in /srv/dashboard except the node_modules link, restart the container.
# No network is needed (dependencies are in /srv/deps; a tree with another pnpm-lock.yaml needs a new image).
#
# Measured (11 CPUs shared with other work, container limit 3 GiB), development server against built-and-served:
#   pnpm run dev                       sign-in form in a browser 41-47 s after container start (codegen ~12 s, vite
#                                      ready in 1 s, the rest is compiling on first request); peak 1.6-1.8 GiB, 1.4 GiB
#                                      in use afterwards. Source replaced, restart, signed in and apps page read: 95 s.
#   vite build + vite preview          build 129 s on a quiet machine, 255 s on a busy one, and it fills the 3 GiB
#                                      limit (heap capped at 2560 MB; upstream gives it 8 GiB); serving then takes
#                                      250 MiB and answers at once. Works by host name with the same variable; API_URL,
#                                      STATIC_URL=/ and SKIP_SOURCEMAPS=true must be set at build time.
# So the development server: well inside both limits, where the build is at the edge of both. Its costs: every page
# compiles when first asked for (a browser check must wait, and an empty page is not a settled one), and a tree
# that does not compile shows an error overlay in the browser instead of failing at start.
# The API must answer CORS preflights for the browser: Saleor does so under uvicorn (saleor.asgi), not under
# `manage.py runserver`, where signing in fails with "Login went wrong".
FROM node:22-bookworm
RUN npm install -g pnpm@10.28.1
# The dependencies live beside the source, under /srv, which the dashboard's vite configuration lets its development
# server read (server.fs.allow has "../.." of src); anywhere else it answers 403 for files of packages it serves as they are.
ENV CI=true pnpm_config_verify_deps_before_run=false NODE_PATH=/srv/deps/node_modules PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY dashboard/package.json dashboard/pnpm-lock.yaml dashboard/pnpm-workspace.yaml dashboard/.npmrc /srv/deps/
RUN cd /srv/deps && pnpm install --frozen-lockfile && rm -rf /root/.local/share/pnpm/store /root/.cache
RUN cd /srv/deps && npx playwright install --with-deps chromium && rm -rf /var/lib/apt/lists/*
COPY dashboard /srv/dashboard
RUN ln -s /srv/deps/node_modules /srv/dashboard/node_modules
WORKDIR /srv/dashboard
ENV API_URL=http://core.internal:8000/graphql/ __VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS=dashboard.internal
EXPOSE 9000
CMD ["pnpm", "run", "dev"]
