"""Validation engine: loads data + rules, runs every check, returns structured results."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from . import validations as v


def load_rules(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def run_validations(src: pd.DataFrame, tgt: pd.DataFrame, rules: dict, today: date | None = None) -> dict:
    key = rules["primary_key"]
    tol = rules.get("numeric_tolerance", 0.01)
    checks: list[v.CheckResult] = [
        v.check_record_count(src, tgt),
        v.check_schema(src, tgt),
        v.check_duplicates(src, key, "source"),
        v.check_duplicates(tgt, key, "target"),
        *v.check_key_reconciliation(src, tgt, key),
        v.check_types(tgt, rules.get("expected_types", {})),
    ]
    checks += [v.check_missing_values(tgt, c) for c in rules.get("required_columns", [])]
    checks += [v.check_value_match(src, tgt, key, c, tol) for c in rules.get("compare_columns", [])]
    checks += [v.check_business_rule(tgt, r, today) for r in rules.get("business_rules", [])]

    results = [c.to_dict() for c in checks]
    passed = sum(r["status"] == "PASS" for r in results)
    return {
        "dataset": rules.get("dataset"),
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_rows": len(src),
        "target_rows": len(tgt),
        "summary": {"total": len(results), "passed": passed, "failed": len(results) - passed},
        "checks": results,
    }


def run_from_files(source: str | Path, target: str | Path, rules_path: str | Path) -> dict:
    src = pd.read_csv(source)
    tgt = pd.read_csv(target)
    return run_validations(src, tgt, load_rules(rules_path))
