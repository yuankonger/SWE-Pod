# atproto at its October 2026 toolchain: Node 24 (`.nvmrc`; 24.22.1, the same image as social-app), pnpm 11.11.0 (corepack)
# (`packageManager`), and the locked dependencies of the base commit fetched into a pnpm store with `pnpm fetch`
# (it reads only the lockfile). The feature's commits change no dependency. No source: the repository is mounted,
# and `pnpm install --offline --frozen-lockfile` links its node_modules from this store (`--store-dir /pnpm/atproto`).
# The AppView's tests need Postgres and Redis (`packages/dev-infra/docker-compose.yaml`: postgres 14, redis 7),
# so both run inside this container, on the ports and credentials that compose file uses.
FROM node:24.22.1-bookworm@sha256:d862bb5d082c5ae0210ac07e8c0344cb8cf7bef6d78e9b8c50c179da923108ea
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/pgdg.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends postgresql-14 redis-server \
    && rm -rf /var/lib/apt/lists/*
# pnpm through corepack, both versions the company's repositories pin (atproto's `packageManager` pnpm@11.11.0,
# social-app's `devEngines` 11.28.5, the default where no `packageManager` is named), prepared here so that it never
# downloads; corepack must not pin a version into a repository's package.json either.
ENV COREPACK_HOME=/opt/corepack COREPACK_ENABLE_AUTO_PIN=0 COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable pnpm && corepack prepare pnpm@11.11.0 && corepack prepare pnpm@11.28.5 --activate \
    && chmod -R a+rX /opt/corepack
ENV COREPACK_ENABLE_NETWORK=0
# Only the files the fetch reads.
COPY pnpm-lock.yaml pnpm-workspace.yaml .npmrc /deps/
ENV PUPPETEER_SKIP_DOWNLOAD=1 CI=true
# The store's place is given on the command line (pnpm ignores `npm_config_store_dir`); installs pass the same flag.
# It is this repository's alone (two stores cannot be merged: each has its own index.db). Its packages stay root's
# and read-only, so that what a tree links from it cannot be changed; only its index, which pnpm 11 writes even
# offline, is writable, in a sticky folder where nobody can move what root put there.
RUN cd /deps && corepack pnpm@11.11.0 fetch --store-dir /pnpm/atproto && chmod -R a+rX /pnpm/atproto && chmod 1777 /pnpm/atproto/v11 /pnpm/atproto/v11/projects && chmod a+w /pnpm/atproto/v11/index.db && rm -rf /deps/node_modules
# Postgres and Redis as dev-infra's compose file sets them up: user pg, password `password`, Postgres on 5433, Redis on 6380.
RUN printf '%s\n' \
    '#!/bin/sh' \
    '# Postgres 14 on 5433 (user pg, password `password`, max_connections 1000) and Redis 7 on 6380, empty, as' \
    '# atproto'"'"'s packages/dev-infra/docker-compose.yaml starts them for a test run. Safe to run twice.' \
    'set -e' \
    'PGBIN=/usr/lib/postgresql/14/bin' \
    'DATA=/tmp/pg-test' \
    'if ! redis-cli -p 6380 ping >/dev/null 2>&1; then' \
    '  redis-server --port 6380 --save '"'"''"'"' --appendonly no --daemonize yes >/dev/null' \
    'fi' \
    'if ! pg_isready -h 127.0.0.1 -p 5433 >/dev/null 2>&1; then' \
    '  RUNAS=""' \
    '  [ "$(id -u)" = 0 ] && RUNAS="runuser -u postgres --"' \
    '  rm -rf "$DATA" && mkdir -p "$DATA" && [ -n "$RUNAS" ] && chown postgres "$DATA"' \
    '  echo password > /tmp/pg-pass && chmod 644 /tmp/pg-pass' \
    '  $RUNAS $PGBIN/initdb -D "$DATA" -U pg --pwfile=/tmp/pg-pass -A md5 >/dev/null' \
    '  $RUNAS $PGBIN/pg_ctl -D "$DATA" -l /tmp/pg-test.log -w -o "-p 5433 -c max_connections=1000 -c fsync=off -k /tmp" start >/dev/null' \
    'fi' \
    'redis-cli -p 6380 flushall >/dev/null' \
    > /usr/local/bin/start-test-db
RUN chmod 755 /usr/local/bin/start-test-db
ENV PGPORT=5433 PGHOST=localhost PGUSER=pg PGPASSWORD=password PGDATABASE=postgres \
    DB_POSTGRES_URL=postgresql://pg:password@127.0.0.1:5433/postgres REDIS_HOST=127.0.0.1:6380 LOG_ENABLED=false
CMD ["bash"]
