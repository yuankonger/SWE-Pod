# Saleor Dashboard at its August 2026 toolchain: Node 24, pnpm 11 and the locked dependencies of the base commit
# (the feature changes none of them). No source: the repository is mounted, and its `node_modules` links here.
FROM node:24-bookworm
RUN npm install -g pnpm@11.13.1
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml /deps/
RUN cd /deps && pnpm install --frozen-lockfile --ignore-scripts && rm -rf /root/.local/share/pnpm/store /root/.cache
# Without a network pnpm must not try to check or reinstall dependencies before every `pnpm run`.
ENV CI=true pnpm_config_verify_deps_before_run=false NODE_PATH=/deps/node_modules
