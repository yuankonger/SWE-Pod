# Home Assistant frontend at its August 2026 toolchain: Node 24.19.0 (`.nvmrc`), yarn 4.18.0 from the repository's own
# release (`.yarn/releases`), and the locked dependencies of the base commit with the project's yarn patches (the
# feature's commits change none of them). No source: the repository is mounted, and its `node_modules` links here.
FROM node:24.19.0-bookworm@sha256:4196d66a565c6f195728d9952f161f4adfe2ad753052a08b7ec7f1c5a6bda42b
# Only the files the install reads: the manifest, the lock, yarn's settings, its release and the project's patches.
COPY package.json yarn.lock .yarnrc.yml /deps/
COPY .yarn /deps/.yarn
RUN cd /deps && node .yarn/releases/yarn-4.18.0.cjs install --immutable && rm -rf /root/.cache /root/.yarn /deps/.yarn/cache
# Without a network nothing may be installed or checked when a script runs.
ENV CI=true NODE_PATH=/deps/node_modules
CMD ["bash"]
