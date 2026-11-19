#!/bin/bash
# Runs the task's rubric (/tests/rubric.toml, with /tests/score.py) against the company as it runs: new orders are
# placed and what the provider's ledger says is compared with what was asked. Writes the reward, score.json and
# rubric.txt (one line per criterion).
mkdir -p /logs/verifier
python3 /tests/score.py /tests /logs/verifier > /logs/verifier/output.txt 2>&1
[ -f /logs/verifier/reward.txt ] || echo 0 > /logs/verifier/reward.txt
cat /logs/verifier/reward.txt
