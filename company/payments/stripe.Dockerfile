# The payment app (saleor/apps, apps/stripe) of the payment-path company. Context: a tree of saleor/apps.
FROM node:24-bookworm
RUN npm install -g pnpm@10.28.1
ENV CI=true NEXT_TELEMETRY_DISABLED=1
WORKDIR /srv/apps
COPY apps /srv/apps
RUN pnpm install --frozen-lockfile --filter . --filter "saleor-app-payment-stripe..."
# What the build needs to be set, not what runs: the running container sets its own.
RUN cd apps/stripe && SECRET_KEY=0000000000000000000000000000000000000000000000000000000000000000 \
    DYNAMODB_MAIN_TABLE_NAME=stripe-main-table AWS_REGION=localhost APL=dynamodb pnpm build
WORKDIR /srv/apps/apps/stripe
