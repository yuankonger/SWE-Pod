#!/bin/bash
# Builds the images of the platform company from clones of the real repositories, each at the commit the company
# is pinned to: the last commit before the App Problems feature, or any copy of its API, reached that repository
# (February 2026; for the apps that is the commit before their schema copies were brought up to an API that had it).
#     company/platform/build.sh <saleor clone> <saleor/apps clone> <saleor-dashboard clone>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
CORE=$1 APPS=$2 DASHBOARD=$3
CORE_AT=${CORE_AT:-b4cc3b3f2} APPS_AT=${APPS_AT:-c1cbffb4} DASHBOARD_AT=${DASHBOARD_AT:-7ea285835}
CONTEXT=$(mktemp -d "${TMPDIR:-/tmp}/platform-context.XXXXXX")
mkdir -p "$CONTEXT/core" "$CONTEXT/apps" "$CONTEXT/dashboard"
git -c gc.auto=0 -C "$CORE" archive "$CORE_AT" | tar -x -C "$CONTEXT/core"
git -c gc.auto=0 -C "$APPS" archive "$APPS_AT" | tar -x -C "$CONTEXT/apps"
mkdir -p "$CONTEXT/apps-next"      # manifests and lockfile only, of the commit whose packages the store is also filled for
git -c gc.auto=0 -C "$APPS" archive "${APPS_NEXT:-f0d36e14}" | tar -x -C "$CONTEXT/apps-next" --include='*/package.json' --include='package.json' --include='pnpm-lock.yaml' --include='pnpm-workspace.yaml' --include='.npmrc'
git -c gc.auto=0 -C "$DASHBOARD" archive "$DASHBOARD_AT" | tar -x -C "$CONTEXT/dashboard"
cp -R "$HERE/../../sidecars" "$CONTEXT/sidecars"
cp "$HERE"/../payments/*.py "$HERE"/../payments/*.sh "$CONTEXT/sidecars/"
cp "$HERE"/*.py "$HERE"/*.sh "$HERE"/*.cjs "$CONTEXT/sidecars/" 2>/dev/null || true
for image in ${ONLY:-core apps dashboard}; do
  case $image in
    core) docker build -t seedco-platform-core:1 -f "$HERE/../payments/core.Dockerfile" "$CONTEXT" ;;
    apps) docker build -t seedco-platform-apps:1 -f "$HERE/apps.Dockerfile" "$CONTEXT" ;;
    dashboard) docker build -t seedco-platform-dashboard:1 -f "$HERE/dashboard.Dockerfile" "$CONTEXT" ;;
  esac
done
echo "built; context left at $CONTEXT"
