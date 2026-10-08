#!/usr/bin/env python3
"""Score task-specific delivery conditions as a binary, all-of completion gate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def read_cases(path: Path) -> tuple[list[dict], str | None]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        return [], f"JUnit report unavailable or invalid: {exc}"
    cases = []
    for node in root.iter():
        if node.tag.rsplit('}', 1)[-1] != 'testcase':
            continue
        name = node.get('name', '')
        child = next((item for item in node if item.tag.rsplit('}', 1)[-1] in {'skipped', 'failure', 'error'}), None)
        status = 'passed' if child is None else child.tag.rsplit('}', 1)[-1]
        message = '' if child is None else str(child.get('message', '') or child.text or '')
        if status == 'error' and any(marker in message.casefold() for marker in (
            'missing requested artifact', 'requested artifact is missing', 'artifact is missing',
            'missing /root/results/', 'required file is missing',
            'missing required file', '缺少要求的文件', 'assertionerror:',
        )):
            status = 'failure'
        cases.append({'name': name, 'test_id': name.split('[', 1)[0], 'status': status})
    return cases, None if cases else 'JUnit report contains no test cases'


def read_judge(path: Path, expected_ids: list[str]) -> tuple[str, dict, dict]:
    if not expected_ids:
        return 'not_required', {}, {'hard_fail': False, 'limitations': []}
    if not path.is_file():
        return 'pending', {}, {'reason': 'LLM completion decision not supplied'}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        rows = payload.get('scores')
        if not isinstance(rows, list) or len(rows) != len(expected_ids):
            raise ValueError('one Judge decision is required for every LLM completion condition')
        supplied = {row.get('criterion_id'): row for row in rows if isinstance(row, dict)}
        if set(supplied) != set(expected_ids) or len(supplied) != len(rows):
            raise ValueError('Judge criterion IDs do not match the rubric')
        if payload.get('hard_fail') is True:
            raise ValueError('record delivery failures on their binary condition, not as an extra hard fail')
        normalized = {}
        for criterion_id in expected_ids:
            row = supplied[criterion_id]
            score = row.get('score')
            if isinstance(score, bool) or score not in (0, 10):
                raise ValueError(f'{criterion_id} must be binary: 0 or 10')
            evidence = row.get('evidence')
            if not isinstance(evidence, str) or not evidence.strip():
                raise ValueError(f'{criterion_id} requires concrete evidence')
            normalized[criterion_id] = {'score': float(score) / 10, 'evidence': evidence.strip(),
                                        'counterexample_check': row.get('counterexample_check')}
        return 'complete', normalized, {
            'hard_fail': payload.get('hard_fail') is True,
            'hard_fail_reason': payload.get('hard_fail_reason'),
            'limitations': payload.get('limitations', []),
            'summary': payload.get('summary', ''),
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return 'invalid', {}, {'reason': str(exc)}


def rule_decision(criterion: dict, cases: list[dict]) -> tuple[float | None, str, dict]:
    requested = set(criterion['test_ids'])
    matched = [case for case in cases if case['test_id'] in requested]
    observed = {case['test_id'] for case in matched}
    missing = sorted(requested - observed)
    counts = {status: sum(case['status'] == status for case in matched)
              for status in ('passed', 'failure', 'error', 'skipped')}
    evidence = {'test_ids': sorted(requested), 'missing_test_ids': missing, 'counts': counts}
    if missing or not matched or counts['error']:
        return None, 'verifier_error', evidence
    passed = all(case['status'] == 'passed' for case in matched)
    return (1.0 if passed else 0.0), ('complete' if passed else 'failed_submission'), evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--junit', type=Path, required=True)
    parser.add_argument('--rubric', type=Path, required=True)
    parser.add_argument('--judge-result', type=Path, required=True)
    parser.add_argument('--reward', type=Path, required=True)
    parser.add_argument('--details', type=Path, required=True)
    args = parser.parse_args()
    rubric = json.loads(args.rubric.read_text(encoding='utf-8'))
    if rubric.get('scoring_mode') != 'completion_only':
        raise ValueError('completion-only rubric required')
    criteria = rubric['criteria']
    rule_criteria = [item for item in criteria if item['evaluator'] == 'rule']
    judge_criteria = [item for item in criteria if item['evaluator'] == 'llm_judge']
    cases, junit_error = read_cases(args.junit) if rule_criteria else ([], None)
    judge_status, judge_scores, judge_details = read_judge(
        args.judge_result, [item['id'] for item in judge_criteria]
    )
    rows = []
    verifier_error = junit_error is not None or judge_status == 'invalid'
    for criterion in criteria:
        criterion_id = criterion['id']
        if criterion['evaluator'] == 'rule':
            score, status, evidence = rule_decision(criterion, cases)
        elif judge_status == 'complete':
            decision = judge_scores[criterion_id]
            score, status = decision['score'], 'complete'
            evidence = {'evidence': decision['evidence'],
                        'raw_score_0_or_10': int(score * 10),
                        'counterexample_check': decision['counterexample_check']}
        else:
            score, status, evidence = None, judge_status, judge_details
        verifier_error |= status in {'verifier_error', 'invalid'}
        rows.append({'id': criterion_id, 'title': criterion['title'],
                     'evaluator': criterion['evaluator'], 'weight': 0,
                     'status': status, 'score': score, 'contribution': None,
                     'details': evidence})
    checks = [{'id': row['id'], 'passed': row['score'] == 1.0,
               'status': 'unscored' if row['score'] is None else 'complete'} for row in rows]
    any_failed = any(row['score'] == 0.0 for row in rows)
    any_pending = any(row['score'] is None for row in rows)
    if verifier_error:
        status, final = 'verifier_error', None
    elif any_failed:
        status, final = 'failed_delivery', 0.0
    elif any_pending:
        status, final = 'pending_judge', None
    else:
        status, final = 'complete', 1.0
    details = {'schema_version': '2.0', 'scoring_mode': 'completion_only',
               'status': status, 'criteria': rows, 'completion_gate': checks,
               'junit_error': junit_error, 'ignored_test_ids': sorted(
                   {case['test_id'] for case in cases} -
                   {test for item in rule_criteria for test in item['test_ids']}
               ), 'judge_status': judge_status, 'judge_details': judge_details,
               'provisional_score': None, 'final_score': final}
    args.details.write_text(json.dumps(details, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    args.reward.write_text(f"{0.0 if final is None else final:.6f}\n", encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
