#!/bin/bash
# The oracle: a fix, laid over each repository it touches as it is on `main`, committed and pushed.
set -e
for r in payments; do
  rm -rf /tmp/oracle-$r && git clone -q http://oracle:oracle-9a17c3e55b@git:8080/$r.git /tmp/oracle-$r && cd /tmp/oracle-$r
  git apply --whitespace=nowarn /solution/$r.patch
  git add -A && git commit -qm "Fix" && git push -q origin HEAD:main
done
