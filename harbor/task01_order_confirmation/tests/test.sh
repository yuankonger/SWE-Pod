#!/bin/bash
# Runs the task's rubric against the company as the agent left it and writes the reward:
#   share of feature criteria passed x share of regression criteria passed   (see /tests/rubric.py)
# Nothing here trusts files the agent could have changed to grade itself: the stack runner, the checks, the
# regression suite, the production history, the released mobile build and the driver that replays it all come
# from /tests. Before the company is started, whatever the agent left listening on its ports is killed.
mkdir -p /logs/verifier
python3 /tests/rubric.py --workspace /work --checks /tests /tests/checks/* --seed /tests/seed --platform /tests/platform \
    --out /logs/verifier > /logs/verifier/output.txt 2>&1
[ -f /logs/verifier/reward.txt ] || echo 0 > /logs/verifier/reward.txt
cat /logs/verifier/reward.txt
