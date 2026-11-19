# The apps (saleor/apps) of the platform company: the payment app (apps/stripe) and the email app (apps/smtp), with
# the monorepo's shared packages. Context: a tree of saleor/apps under apps/.
FROM node:22-bookworm
RUN npm install -g pnpm@10.28.1
ENV CI=true NEXT_TELEMETRY_DISABLED=1
WORKDIR /srv/apps
COPY apps /srv/apps
RUN pnpm install --frozen-lockfile --filter . --filter "saleor-app-payment-stripe..." --filter "saleor-app-smtp..." --filter "./packages/*..."
# The company's package mirror, as far as the seat and the deploy can use one: they have no registry, only this
# image's package store. It is filled for a second, later lockfile of the same monorepo too (apps-next/), so that work
# which adds the packages that lockfile names can be installed; the later tree itself is not kept.
COPY apps-next /tmp/apps-next
RUN cd /tmp/apps-next && pnpm install --frozen-lockfile --ignore-scripts --filter . --filter "saleor-app-payment-stripe..." --filter "saleor-app-smtp..." --filter "./packages/*..." \
    && cd / && rm -rf /tmp/apps-next
# What the builds need to be set, not what runs: the running containers set their own.
ENV SECRET_KEY=0000000000000000000000000000000000000000000000000000000000000000
ENV AWS_REGION=localhost AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local APL=dynamodb
RUN cd apps/stripe && DYNAMODB_MAIN_TABLE_NAME=stripe-main-table pnpm build
RUN cd apps/smtp && DYNAMODB_MAIN_TABLE_NAME=smtp-main-table pnpm build
