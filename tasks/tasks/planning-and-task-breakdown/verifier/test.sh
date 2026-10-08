#!/bin/bash
mkdir -p /logs/verifier

mkdir -p /logs/verifier/submission
[ -d /root/results ] && cp -R /root/results/. /logs/verifier/submission/
[ -f /verifier/review_criteria.md ] && \
  cp /verifier/review_criteria.md /logs/verifier/review_criteria.md
[ -f /verifier/evaluation_rubric.json ] && \
  cp /verifier/evaluation_rubric.json /logs/verifier/evaluation_rubric.json
[ -f /verifier/judge_prompt.md ] && \
  cp /verifier/judge_prompt.md /logs/verifier/judge_prompt.md

TEST_EXPR="$(python3 - <<'PYCODE'
import json
rubric = json.load(open('/verifier/evaluation_rubric.json', encoding='utf-8'))
ids = sorted({test for criterion in rubric['criteria'] if criterion['evaluator'] == 'rule'
              for test in criterion['test_ids']})
print(' or '.join(ids))
PYCODE
)"
if [ -n "$TEST_EXPR" ]; then
  python3 -m pytest /verifier/test_outputs.py -rA -v -k "$TEST_EXPR" \
    --junitxml=/logs/verifier/pytest.xml \
    > /logs/verifier/output.txt 2>&1
  RC=$?
else
  printf '<testsuite tests="0"/>\n' > /logs/verifier/pytest.xml
  printf 'No deterministic delivery conditions; LLM Judge decides completion.\n' > /logs/verifier/output.txt
  RC=0
fi

cat /logs/verifier/output.txt

JUDGE_RESULT="${LLM_JUDGE_RESULT_PATH:-/logs/verifier/llm_judge_result.json}"
python3 /verifier/criterion_score.py \
  --junit /logs/verifier/pytest.xml \
  --rubric /verifier/evaluation_rubric.json \
  --judge-result "$JUDGE_RESULT" \
  --reward /logs/verifier/reward.txt \
  --details /logs/verifier/score_details.json

echo "pytest_exit_code=$RC" >> /logs/verifier/output.txt
exit 0
