#!/bin/bash
# Builds the two images of the payment-path company from clones of the real repositories.
#     company/payments/build.sh <saleor clone> <saleor/apps clone> [core commit] [apps commit]
# IMAGES names the pair (default seedco-payments): a company pinned at other commits builds its own pair beside it.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
CORE=$1 APPS=$2 CORE_AT=${3:-HEAD} APPS_AT=${4:-HEAD}
CONTEXT=$(mktemp -d "${TMPDIR:-/tmp}/payments-context.XXXXXX")
mkdir -p "$CONTEXT/core" "$CONTEXT/apps"
git -C "$CORE" archive "$CORE_AT" | tar -x -C "$CONTEXT/core"
git -C "$APPS" archive "$APPS_AT" | tar -x -C "$CONTEXT/apps"
cp -R "$HERE/../../sidecars" "$CONTEXT/sidecars"
cp "$HERE"/*.py "$HERE"/*.sh "$CONTEXT/sidecars/"
docker build -t "${IMAGES:-seedco-payments}-core:1" -f "$HERE/core.Dockerfile" "$CONTEXT"
docker build -t "${IMAGES:-seedco-payments}-stripe:1" -f "$HERE/stripe.Dockerfile" "$CONTEXT"
echo "built; context left at $CONTEXT"
