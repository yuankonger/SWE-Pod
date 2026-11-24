#!/bin/bash
# The oracle for the seat: its own repository's part of the feature as the real project wrote it, pushed to `main`.
# Then it submits. The other owner publishes at the latest on a first submission; the oracle waits for that push and
# submits again, which is final.
set -e
cd /work/dashboard && git apply --binary --whitespace=nowarn /solution/dashboard.patch
git add -A -f && git commit -qm "The feature" && git push -q http://oracle:oracle-9a17c3e55b@git:8080/dashboard.git HEAD:main
submit() { curl -s -m 60 -X POST -H 'Content-Type: application/json' -d "{\"name\": \"$SEAT\", \"token\": \"$SEAT_TOKEN\", \"report\": \"the oracle\"}" http://chat:8080/submit; echo; }
before() { git ls-remote http://oracle:oracle-9a17c3e55b@git:8080/$1.git main | cut -f1; }
was=$(before core)
submit
for i in $(seq 180); do [ "$(before core)" != "$was" ] && break; sleep 5; done
[ "$(before core)" != "$was" ] || { echo "the owner of core did not publish" >&2; exit 1; }
submit
