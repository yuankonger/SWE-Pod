#!/bin/bash
# The oracle for the requirement as `reassign` has it: the feature as the real project wrote it, pushed to `main`.
set -e
cd /work/core && git apply --binary --whitespace=nowarn /solution/core.patch
git add -A -f && git commit -qm "The feature" && git push -q http://oracle:oracle-9a17c3e55b@git:8080/core.git HEAD:main
