#!/bin/bash
# The verifier. It does not score here: this is the agent's seat, and nothing in it can be trusted to judge. It hands
# the task's tests to the company's judge (sidecars/judge.py), a container the agent never had, which runs the rubric
# (/tests/rubric.toml, with /tests/score.py) on `main` of the company's git server, and takes back what it wrote: the
# reward, score.json and rubric.txt (one line per criterion). It also keeps what the company recorded of the work.
mkdir -p /logs/verifier/records
TOKEN=$(python3 -I -c "import json; print(json.load(open('/tests/config.json'))['judge_token'])")
GIT=$(python3 -I -c "import json; print(json.load(open('/tests/config.json'))['git'])")
JUDGE=http://judge:8095
curl -s -m 30 "$GIT/_log" > /logs/verifier/records/git.jsonl || true
curl -s -m 30 http://ci:8080/status.json > /logs/verifier/records/ci.json || true
curl -s -m 30 http://meter:8318/_records > /logs/verifier/records/model.jsonl || true
curl -s -m 30 "http://chat:8080/log?token=chat-admin-5d02e7" > /logs/verifier/records/chat.json 2>/dev/null || rm -f /logs/verifier/records/chat.json
tar -C /tests -czf /tmp/judge-tests.tgz .
code=$(curl -s -o /logs/verifier/judge-start.json -w '%{http_code}' -X POST --data-binary @/tmp/judge-tests.tgz -H 'Content-Type: application/gzip' "$JUDGE/judge?token=$TOKEN")
if [ "$code" != 202 ]; then echo "the judge did not take the work ($code)" > /logs/verifier/output.txt; echo 0 > /logs/verifier/reward.txt; cat /logs/verifier/reward.txt; exit 0; fi
until curl -s -m 20 "$JUDGE/status?token=$TOKEN" | grep -q '"state": "\(done\|failed\)"'; do sleep 20; done
curl -s -m 20 "$JUDGE/status?token=$TOKEN" > /logs/verifier/judge-status.json
curl -s -m 120 -o /tmp/judge-result.tgz "$JUDGE/result?token=$TOKEN" && tar -C /logs/verifier -xzf /tmp/judge-result.tgz
[ -f /logs/verifier/reward.txt ] || echo 0 > /logs/verifier/reward.txt
cat /logs/verifier/reward.txt
