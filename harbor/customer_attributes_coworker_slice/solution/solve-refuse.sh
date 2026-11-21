#!/bin/bash
# The oracle for the requirement as `refuse` has it: the feature as the real project wrote it, with this value's change on top, pushed to `main`.
set -e
cd /work/core && git apply --binary --whitespace=nowarn /solution/core.patch && git apply --whitespace=nowarn /solution/variants/refuse/core.patch
git add -A -f && git commit -qm "The feature" && git push -q http://oracle:oracle-9a17c3e55b@git:8080/core.git HEAD:main
