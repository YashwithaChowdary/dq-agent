"""Deterministic validation checks.

Every check is plain Python/pandas: same input -> same result, no AI involved.
Each returns a CheckResult, which is the only thing the AI layer ever sees.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

SAMPLE_SIZE = 5


@dataclass
class CheckResult:
    check_id: str
    category: str
    description: str
    status: str  # "PASS" | "FAIL"
    severity: str  # "high" | "medium" | "low"
    expected: Any = None
    actual: Any = None
    affected_rows: int = 0
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return _jsonable(asdict(self))


def _jsonable(obj: Any) -> Any:
    """Convert numpy/pandas scalars so results serialise cleanly to JSON."""
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else round(float(obj), 4)
    if isinstance(obj, float) and np.isnan(obj):
        return None
    if obj is pd.NA or obj is pd.NaT:
        return None
    return obj


def _result(check_id, category, description, ok, severity, **kw) -> CheckResult:
    return CheckResult(check_id, category, description, "PASS" if ok else "FAIL", severity, **kw)


# ---------------------------------------------------------------- structure

def check_record_count(src: pd.DataFrame, tgt: pd.DataFrame) -> CheckResult:
    diff = len(tgt) - len(src)
    return _result(
        "record_count", "completeness", "Target row count equals source row count",
        diff == 0, "high", expected=len(src), actual=len(tgt), affected_rows=abs(diff),
        details={"difference": diff},
    )


def check_schema(src: pd.DataFrame, tgt: pd.DataFrame) -> CheckResult:
    missing = sorted(set(src.columns) - set(tgt.columns))
    extra = sorted(set(tgt.columns) - set(src.columns))
    return _result(
        "schema_columns", "schema", "Target has the same columns as source",
        not missing and not extra, "high",
        expected=sorted(src.columns), actual=sorted(tgt.columns),
        details={"missing_in_target": missing, "extra_in_target": extra},
    )


# ------------------------------------------------------------- uniqueness

def check_duplicates(df: pd.DataFrame, key: str, side: str) -> CheckResult:
    dup_mask = df[key].duplicated(keep="first")
    dup_keys = df.loc[dup_mask, key].unique().tolist()
    return _result(
        f"duplicates.{key}" + ("" if side == "target" else ".source"), "uniqueness",
        f"{key} is unique in {side}", len(dup_keys) == 0, "high",
        expected=0, actual=int(dup_mask.sum()), affected_rows=int(dup_mask.sum()),
        details={"sample_duplicate_keys": dup_keys[:SAMPLE_SIZE]},
    )


# ----------------------------------------------------------- completeness

def check_missing_values(tgt: pd.DataFrame, column: str) -> CheckResult:
    if column not in tgt.columns:
        return _result(f"missing_values.{column}", "completeness", f"{column} present", False, "high",
                       details={"error": "column not found"})
    n_null = int(tgt[column].isna().sum())
    return _result(
        f"missing_values.{column}", "completeness", f"No NULLs in required column {column}",
        n_null == 0, "high", expected=0, actual=n_null, affected_rows=n_null,
        details={"null_pct": round(100 * n_null / max(len(tgt), 1), 2)},
    )


def check_key_reconciliation(src, tgt, key) -> list[CheckResult]:
    s, t = set(src[key]), set(tgt[key])
    missing, extra = sorted(s - t), sorted(t - s)
    out = [
        _result("keys_missing_in_target", "completeness", f"Every source {key} exists in target",
                not missing, "high", expected=0, actual=len(missing), affected_rows=len(missing),
                details={"sample_keys": missing[:SAMPLE_SIZE]}),
        _result("keys_unexpected_in_target", "completeness", f"Target has no {key} absent from source",
                not extra, "medium", expected=0, actual=len(extra), affected_rows=len(extra),
                details={"sample_keys": extra[:SAMPLE_SIZE]}),
    ]
    if missing:  # profile the missing rows: this is the evidence the AI needs
        out[0].details["profile_of_missing_rows"] = _profile(src[src[key].isin(missing)])
    return out


# ------------------------------------------------------------------ types

def _infer_type(series: pd.Series) -> str:
    s = series.dropna()
    if s.empty:
        return "unknown"
    if pd.api.types.is_bool_dtype(s):
        return "bool"
    if pd.api.types.is_integer_dtype(s):
        return "int"
    if pd.api.types.is_float_dtype(s):
        # floats that are all whole numbers are ints that picked up NULLs
        return "int" if np.all(np.mod(s, 1) == 0) else "float"
    parsed = pd.to_datetime(s, errors="coerce", format="%Y-%m-%d")
    if parsed.notna().all():
        return "date"
    return "string"


def check_types(tgt: pd.DataFrame, expected: dict[str, str]) -> CheckResult:
    bad = {}
    for col, exp in expected.items():
        if col not in tgt.columns:
            continue
        act = _infer_type(tgt[col])
        # an int column is acceptable where float is expected
        if act != exp and not (exp == "float" and act == "int"):
            bad[col] = {"expected": exp, "actual": act}
    return _result("data_types", "schema", "Column types match the rules", not bad, "medium",
                   expected=expected, actual={c: _infer_type(tgt[c]) for c in expected if c in tgt},
                   affected_rows=0, details={"mismatches": bad})


# ------------------------------------------------------- value comparison

def check_value_match(src, tgt, key, column, tolerance) -> CheckResult:
    t = tgt.drop_duplicates(subset=[key], keep="first")
    m = src[[key, column]].merge(t[[key, column]], on=key, suffixes=("_src", "_tgt"))
    a, b = m[f"{column}_src"], m[f"{column}_tgt"]
    both_null = a.isna() & b.isna()
    one_null = a.isna() ^ b.isna()
    if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
        diff = (a - b).abs() > tolerance
    else:
        diff = a.astype(str) != b.astype(str)
    mismatch = (diff | one_null) & ~both_null
    bad = m[mismatch]
    details: dict = {
        "rows_compared": len(m),
        "null_in_target": int((a.notna() & b.isna()).sum()),
        "sample": bad.head(SAMPLE_SIZE).to_dict("records"),
    }
    if len(bad) and pd.api.types.is_numeric_dtype(b) and b[mismatch].notna().any():
        ratio = (bad[f"{column}_tgt"] / bad[f"{column}_src"].replace(0, np.nan)).dropna()
        if len(ratio):
            details["target_to_source_ratio"] = {
                "median": round(float(ratio.median()), 4),
                "min": round(float(ratio.min()), 4),
                "max": round(float(ratio.max()), 4),
            }
    if len(bad):
        details["profile_of_mismatched_rows"] = _profile(src[src[key].isin(bad[key])])
    return _result(f"value_match.{column}", "accuracy", f"{column} matches source for matched {key}s",
                   len(bad) == 0, "high", expected=0, actual=len(bad), affected_rows=len(bad),
                   details=details)


# ----------------------------------------------------------- business rules

def check_business_rule(tgt: pd.DataFrame, rule: dict, today: date | None = None) -> CheckResult:
    col, kind = rule["column"], rule["type"]
    if kind == "formula":
        expected_vals = tgt.eval(rule["expression"])
        bad_mask = (tgt[col] - expected_vals).abs() > rule.get("tolerance", 0.01)
    elif kind == "range":
        bad_mask = (tgt[col] < rule["min"]) | (tgt[col] > rule["max"])
    elif kind == "allowed_values":
        bad_mask = tgt[col].notna() & ~tgt[col].isin(rule["values"])
    elif kind == "max_date":
        limit = pd.Timestamp(today or date.today()) if rule["max"] == "today" else pd.Timestamp(rule["max"])
        bad_mask = pd.to_datetime(tgt[col], errors="coerce") > limit
    else:
        raise ValueError(f"Unknown rule type: {kind}")
    bad = tgt[bad_mask.fillna(False)]
    details = {"rule": rule["description"], "sample": bad.head(SAMPLE_SIZE).to_dict("records")}
    if kind == "allowed_values" and len(bad):
        details["unexpected_values"] = bad[col].value_counts().head(10).to_dict()
    if len(bad):
        details["profile_of_failing_rows"] = _profile(bad)
    return _result(f"rule.{rule['id']}", "business_rule", rule["description"], bad.empty, "high",
                   expected=0, actual=len(bad), affected_rows=len(bad), details=details)


# ------------------------------------------------------------------ helpers

def _profile(df: pd.DataFrame) -> dict:
    """Small, factual profile of a set of rows: helps the AI see patterns
    (e.g. 'all mismatches are EUR') without sending raw data."""
    prof: dict = {"rows": len(df)}
    for col in df.columns:
        s = df[col]
        p: dict = {}
        if pd.api.types.is_numeric_dtype(s) and s.notna().any():
            p = {"min": s.min(), "max": s.max()}
        if s.dtype == object or s.nunique() <= 6:
            p["top_values"] = s.astype(str).value_counts().head(4).to_dict()
        if p:
            prof[col] = p
    return prof
