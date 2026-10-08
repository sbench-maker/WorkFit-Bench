#!/usr/bin/env python3
"""Create the deterministic, fictional pre-loan screening fixture."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path


SEED = 62026
OUT = Path(__file__).resolve().parent / "data"
MODEL_ORGS = ["Aster", "Briar", "Cobalt", "Dune", "Ember", "Fjord"]
OOS_ORGS = ["Grove-OOS", "Haven-OOS"]
MONTH_COUNTS = {
    "202501": 80,
    "202502": 80,
    "202503": 80,
    "202504": 40,
    "202505": 80,
    "202506": 80,
}
FEATURES = [
    "i_income_monthly",
    "i_income_shadow",
    "i_debt_ratio",
    "i_debt_shadow",
    "i_loan_to_income",
    "i_lti_shadow",
    "i_credit_age_months",
    "i_recent_delinquencies",
    "i_bank_balance_avg",
    "i_optional_social_score",
    "i_sparse_device_signal",
    "i_low_iv_random",
    "i_org_weak_signal",
    "i_drifting_utilization",
    "i_noise_hash",
    "i_stable_capacity",
    "i_constant_channel",
]


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def target_for(org_idx: int, month: str, row_idx: int) -> int:
    if month == "202505":
        # Exactly two bads per modeling organization: adequate volume, too few bads.
        return 1 if row_idx in (7, 43) else 0
    cycle = 9 + ((org_idx + int(month[-2:])) % 3)
    return 1 if (row_idx * 7 + org_idx * 3) % cycle == 0 else 0


def missing_token(feature: str, clean_index: int, rng: random.Random):
    # Rates are deterministic over the 1,920 retained modeling rows. The sparse
    # signal is exactly on the 0.60 boundary; social score is above it.
    specs = {
        "i_income_monthly": (20, 1),
        "i_income_shadow": (25, 1),
        "i_debt_ratio": (16, 1),
        "i_debt_shadow": (20, 1),
        "i_loan_to_income": (40, 1),
        "i_lti_shadow": (48, 1),
        "i_credit_age_months": (10, 1),
        "i_recent_delinquencies": (50, 1),
        "i_bank_balance_avg": (4, 1),
        "i_optional_social_score": (20, 13),
        "i_sparse_device_signal": (5, 3),
    }
    if feature not in specs:
        return None
    denominator, missing_slots = specs[feature]
    if clean_index % denominator < missing_slots:
        # Exercise every declared missing representation.
        return ["", -1, -999, -1111][(clean_index // denominator) % 4]
    return None


def main() -> None:
    rng = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    retained_index = 0

    for org_idx, org in enumerate(MODEL_ORGS):
        for month, count in MONTH_COUNTS.items():
            for j in range(count):
                day = 1 + ((j * 7 + org_idx) % 27)
                date = f"{month[:4]}-{month[4:]}-{day:02d}"
                target = target_for(org_idx, month, j)
                income = 2700 + org_idx * 185 + (j % 29) * 117 + rng.gauss(0, 115)
                debt = min(0.91, max(0.06, 0.18 + target * 0.21 + (j % 17) * 0.018 + rng.gauss(0, 0.025)))
                lti = min(1.65, max(0.05, debt * 0.68 + target * 0.10 + (j % 7) * 0.035 + rng.gauss(0, 0.11)))
                age = 8 + (j * 11 + org_idx * 9) % 180
                delin = min(6, ((j + org_idx) % 5) + target * 2)
                balance = income * (0.55 - debt / 3) + rng.gauss(0, 210)
                social = 420 + (j * 13 + org_idx * 17) % 310
                sparse = 100 + (j * 19 + org_idx * 23) % 480
                weak = (j * 31 + org_idx * 7) % 101
                drift = 0.25 + 0.025 * int(month[-2:]) + (j % 13) * 0.012 + rng.gauss(0, 0.02)
                noise = (j * 97 + org_idx * 37 + int(month)) % 997
                capacity = income * (1 - debt) / 1000 + rng.gauss(0, 0.08)
                row = {
                    "record_id": f"APP-{month}-{org_idx+1:02d}-{j+1:03d}",
                    "apply_date": date,
                    "target": target,
                    "org_info": org,
                    "i_income_monthly": round(income, 2),
                    "i_income_shadow": round(income * 1.012 + rng.gauss(0, 22), 2),
                    "i_debt_ratio": round(debt, 5),
                    "i_debt_shadow": round(debt * 0.992 + rng.gauss(0, 0.004), 5),
                    "i_loan_to_income": round(lti, 5),
                    "i_lti_shadow": round(lti * 1.006 + rng.gauss(0, 0.009), 5),
                    "i_credit_age_months": age,
                    "i_recent_delinquencies": delin,
                    "i_bank_balance_avg": round(balance, 2),
                    "i_optional_social_score": social,
                    "i_sparse_device_signal": sparse,
                    "i_low_iv_random": (j * 47 + org_idx * 29) % 211,
                    "i_org_weak_signal": weak if org not in ("Aster", "Briar") else (j * 17) % 101,
                    "i_drifting_utilization": round(drift, 5),
                    "i_noise_hash": noise,
                    "i_stable_capacity": round(capacity, 5),
                    "i_constant_channel": 1,
                }
                if month in ("202501", "202502", "202503", "202506"):
                    for feature in FEATURES:
                        token = missing_token(feature, retained_index, rng)
                        if token is not None:
                            row[feature] = token
                    retained_index += 1
                rows.append(row)

    # OOS partners are deliberately different and must not affect modeling gates.
    for org_idx, org in enumerate(OOS_ORGS, start=len(MODEL_ORGS)):
        for month in MONTH_COUNTS:
            for j in range(40):
                day = 1 + (j * 5 % 27)
                income = 3600 + (j % 19) * 95 + rng.gauss(0, 130)
                debt = 0.24 + (j % 11) * 0.025
                row = {
                    "record_id": f"APP-{month}-{org_idx+1:02d}-{j+1:03d}",
                    "apply_date": f"{month[:4]}-{month[4:]}-{day:02d}",
                    "target": 1 if j % 13 == 0 else 0,
                    "org_info": org,
                    "i_income_monthly": round(income, 2),
                    "i_income_shadow": round(income * 1.01, 2),
                    "i_debt_ratio": round(debt, 5),
                    "i_debt_shadow": round(debt * 0.99, 5),
                    "i_loan_to_income": round(debt * 1.2, 5),
                    "i_lti_shadow": round(debt * 1.205, 5),
                    "i_credit_age_months": 15 + j * 2,
                    "i_recent_delinquencies": j % 4,
                    "i_bank_balance_avg": round(income * 0.4, 2),
                    "i_optional_social_score": "" if j % 2 else 500 + j,
                    "i_sparse_device_signal": "" if j % 3 else 200 + j,
                    "i_low_iv_random": j * 3,
                    "i_org_weak_signal": j * 2,
                    "i_drifting_utilization": round(0.6 + int(month[-2:]) * 0.08 + j / 500, 5),
                    "i_noise_hash": (j * 53) % 997,
                    "i_stable_capacity": round(income * (1 - debt) / 1000, 5),
                    "i_constant_channel": 1,
                }
                rows.append(row)

    # First occurrence wins during deduplication.
    for original in rows[25:35]:
        duplicate = dict(original)
        duplicate["i_income_monthly"] = 999999
        rows.append(duplicate)
    for bad_idx, bad_target in enumerate((2, -1, "", 9, 2, "")):
        invalid = dict(rows[120 + bad_idx])
        invalid["record_id"] = f"INVALID-{bad_idx+1:03d}"
        invalid["target"] = bad_target
        rows.append(invalid)

    fields = ["record_id", "apply_date", "target", "org_info"] + FEATURES
    write_csv(OUT / "preloan_applications.csv", rows, fields)

    catalog = [
        {"feature": f, "description": f.replace("i_", "").replace("_", " "), "source_family": (
            "bureau" if any(k in f for k in ("debt", "credit", "delinq")) else
            "income" if any(k in f for k in ("income", "capacity", "lti")) else
            "digital" if any(k in f for k in ("device", "social", "hash")) else "banking"
        )}
        for f in FEATURES
    ]
    write_csv(OUT / "feature_catalog.csv", catalog, ["feature", "description", "source_family"])

    iv_overall = {
        "i_income_monthly": .24, "i_income_shadow": .22, "i_debt_ratio": .21,
        "i_debt_shadow": .20, "i_loan_to_income": .18, "i_lti_shadow": .16,
        "i_credit_age_months": .11, "i_recent_delinquencies": .17,
        "i_bank_balance_avg": .09, "i_optional_social_score": .30,
        "i_sparse_device_signal": .10, "i_low_iv_random": .04,
        "i_org_weak_signal": .15, "i_drifting_utilization": .20,
        "i_noise_hash": .12, "i_stable_capacity": .19,
    }
    iv_rows = []
    for feature, overall in iv_overall.items():
        iv_rows.append({"feature": feature, "scope": "overall", "org_info": "ALL_MODEL", "iv": f"{overall:.4f}"})
        for idx, org in enumerate(MODEL_ORGS):
            value = max(.01, overall - .025 + idx * .006)
            if feature == "i_org_weak_signal" and org in ("Aster", "Briar"):
                value = .04
            if feature == "i_sparse_device_signal" and org == "Aster":
                value = .05  # equality is not below the organization threshold
            iv_rows.append({"feature": feature, "scope": "organization", "org_info": org, "iv": f"{value:.4f}"})
    write_csv(OUT / "iv_by_org.csv", iv_rows, ["feature", "scope", "org_info", "iv"])

    transitions = ["202501->202502", "202502->202503", "202503->202504", "202504->202505", "202505->202506"]
    psi_rows = []
    for feature in iv_overall:
        for org_idx, org in enumerate(MODEL_ORGS):
            for trans_idx, transition in enumerate(transitions):
                value = .025 + ((org_idx * 5 + trans_idx * 3 + len(feature)) % 11) / 500
                if feature == "i_drifting_utilization" and org_idx < 4 and trans_idx in (1, 2, 4):
                    value = .145 + org_idx * .006 + trans_idx * .002
                if feature == "i_sparse_device_signal" and org == "Aster" and trans_idx in (0, 1):
                    value = .10  # equality is not above the PSI threshold
                psi_rows.append({
                    "feature": feature, "org_info": org, "transition": transition,
                    "psi": f"{value:.4f}", "valid": 1,
                })
    write_csv(OUT / "psi_by_org_transition.csv", psi_rows, ["feature", "org_info", "transition", "psi", "valid"])

    gains = {
        "i_income_monthly": (180, 25), "i_income_shadow": (170, 20),
        "i_debt_ratio": (160, 30), "i_debt_shadow": (155, 22),
        "i_loan_to_income": (130, 28), "i_lti_shadow": (92, 21),
        "i_credit_age_months": (80, 35), "i_recent_delinquencies": (120, 18),
        "i_bank_balance_avg": (75, 24), "i_optional_social_score": (105, 30),
        "i_sparse_device_signal": (88, 33), "i_low_iv_random": (38, 17),
        "i_org_weak_signal": (68, 25), "i_drifting_utilization": (110, 26),
        "i_noise_hash": (44, 19), "i_stable_capacity": (118, 31),
    }
    gain_rows = [
        {"feature": f, "original_gain": real, "permuted_gain": perm, "gain_difference": abs(real - perm)}
        for f, (real, perm) in gains.items()
    ]
    write_csv(OUT / "null_importance.csv", gain_rows, ["feature", "original_gain", "permuted_gain", "gain_difference"])

    policy = {
        "dataset": {
            "key_column": "record_id", "date_column": "apply_date", "label_column": "target",
            "organization_column": "org_info", "feature_prefix": "i_",
            "valid_labels": [0, 1], "missing_sentinels": [-1, -999, -1111],
            "oos_organizations": OOS_ORGS,
        },
        "screening_base": "Keep the first record per key, retain valid labels, exclude OOS organizations, then exclude abnormal months before calculating missingness and correlations.",
        "gates_in_order": [
            {"gate": "zero_variance", "rule": "drop any feature with one or fewer distinct non-missing values"},
            {"gate": "abnormal_month", "rule": "exclude a modeling month when total samples < 350 or bad samples < 20"},
            {"gate": "missingness", "rule": "drop a feature when overall missing rate > 0.60"},
            {"gate": "iv", "rule": "drop when overall IV < 0.10 or organization IV < 0.05 in at least 2 modeling organizations"},
            {"gate": "psi", "rule": "an organization is unstable when PSI > 0.10 in at least 2 valid transitions; drop a feature when at least 3 modeling organizations are unstable"},
            {"gate": "null_importance", "rule": "drop when absolute original-permuted gain difference < 50"},
            {"gate": "correlation", "rule": "among current survivors, for absolute Pearson correlation > 0.90 drop the lower-original-gain feature; if both are in the top 3 current survivors by original gain, retain both"},
        ],
        "comparison_semantics": "All inequalities are strict exactly as written; equality stays on the passing side.",
        "diagnostics": "The IV, PSI, and null-importance CSVs are frozen approved diagnostic outputs. Use them as authoritative; compute missingness and Pearson correlation from the screening base.",
    }
    (OUT / "screening_policy.json").write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")

    notes = {
        "method": "deterministic local construction",
        "seed": SEED,
        "fictional": True,
        "files": {
            "preloan_applications.csv": len(rows),
            "feature_catalog.csv": len(catalog),
            "iv_by_org.csv": len(iv_rows),
            "psi_by_org_transition.csv": len(psi_rows),
            "null_importance.csv": len(gain_rows),
        },
        "intentional_edge_cases": [
            "duplicate application keys and invalid labels",
            "two OOS organizations",
            "one low-volume and one low-bad-count month",
            "missingness and diagnostic values on strict threshold boundaries",
            "high-correlation pairs including a pair protected by gain rank",
        ],
    }
    (OUT / "generation_notes.json").write_text(json.dumps(notes, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
