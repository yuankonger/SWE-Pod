#!/bin/bash
# The oracle: the feature as the real project wrote it, laid over each checkout, committed and pushed to `main`.
set -e
for r in core frontend; do
  cd /work/$r && git apply --binary --whitespace=nowarn /solution/$r.patch
  git add -A -f && git commit -qm "The feature, as the project wrote it" && git push -q http://oracle:oracle-9a17c3e55b@git:8080/$r.git HEAD:main
done
