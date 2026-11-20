# social-app at its October 2026 toolchain: Node 24 (`.nvmrc` 24.19.0, `devEngines.runtime` ^24.19.0; 24.22.1, the
# same image as atproto), pnpm 11.28.5 (`devEngines.packageManager`), and the locked dependencies of the base commit
# in a pnpm store. The feature's commits change no dependency. No source: the repository is mounted, and
# `pnpm install --offline --frozen-lockfile --store-dir /pnpm/social-app` links its node_modules from this store (`--store-dir /pnpm/social-app`) (its
# postinstall generates the lexicon code from the vendored `lexicons/`).
FROM node:24.22.1-bookworm@sha256:d862bb5d082c5ae0210ac07e8c0344cb8cf7bef6d78e9b8c50c179da923108ea
# pnpm through corepack, both versions the company's repositories pin (atproto's `packageManager` pnpm@11.11.0,
# social-app's `devEngines` 11.28.5, the default where no `packageManager` is named), prepared here so that it never
# downloads; corepack must not pin a version into a repository's package.json either.
ENV COREPACK_HOME=/opt/corepack COREPACK_ENABLE_AUTO_PIN=0 COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable pnpm && corepack prepare pnpm@11.11.0 && corepack prepare pnpm@11.28.5 --activate \
    && chmod -R a+rX /opt/corepack
ENV COREPACK_ENABLE_NETWORK=0
# Only the files an install reads: the manifest, the lockfile, the workspace file, the patches it names, and the
# manifests of the local packages it links (`link:./modules/...`, `link:lint-rules`).
COPY . /deps/
ENV CI=true PUPPETEER_SKIP_DOWNLOAD=1 SENTRY_DISABLE_AUTO_UPLOAD=true
# `pnpm fetch` fails here (it applies a patch under the hoisted linker before the package exists), so the store is
# filled by a real install without scripts, whose node_modules is then dropped. The store's place is given on the
# command line (pnpm ignores `npm_config_store_dir`); installs pass the same flag.
RUN cd /deps && rm Dockerfile && pnpm install --frozen-lockfile --ignore-scripts --store-dir /pnpm/social-app \
    && chmod -R a+rX /pnpm/social-app && chmod 1777 /pnpm/social-app/v11 /pnpm/social-app/v11/projects && chmod a+w /pnpm/social-app/v11/index.db && rm -rf /deps
CMD ["bash"]
