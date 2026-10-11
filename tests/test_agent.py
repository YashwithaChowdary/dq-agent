from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from dq_agent import rca, validations as v
from dq_agent.engine import run_validations

RULES = {
    "dataset": "t",
    "primary_key": "id",
    "required_columns": ["id", "amount"],
    "expected_types": {"id": "int", "amount": "float", "status": "string"},
    "compare_columns": ["amount", "status"],
    "numeric_tolerance": 0.01,
    "business_rules": [
        {"id": "allowed_status", "description": "status allowed", "type": "allowed_values",
         "column": "status", "values": ["a", "b"]},
        {"id": "amount_range", "description": "amount 0..100", "type": "range",
         "column": "amount", "min": 0, "max": 100},
    ],
}


@pytest.fixture
def src():
    return pd.DataFrame({"id": [1, 2, 3, 4], "amount": [10.0, 20.0, 30.0, 40.0], "status": ["a", "b", "a", "b"]})


def statuses(res):
    return {c["check_id"]: c["status"] for c in res["checks"]}


# ------------------------------------------------------------ validations

def test_identical_data_all_pass(src):
    res = run_validations(src, src.copy(), RULES, today=date(2026, 10, 1))
    assert res["summary"]["failed"] == 0


def test_detects_each_defect_type(src):
    tgt = src.copy()
    tgt.loc[0, "amount"] = None          # missing value
    tgt.loc[1, "amount"] = 25.0          # value mismatch
    tgt.loc[2, "status"] = "A"           # business rule
    tgt = pd.concat([tgt, tgt.iloc[[3]]])  # duplicate
    s = statuses(run_validations(src, tgt, RULES))
    assert s["record_count"] == "FAIL"
    assert s["duplicates.id"] == "FAIL"
    assert s["duplicates.id.source"] == "PASS"
    assert s["missing_values.amount"] == "FAIL"
    assert s["value_match.amount"] == "FAIL"
    assert s["value_match.status"] == "FAIL"
    assert s["rule.allowed_status"] == "FAIL"
    assert s["keys_missing_in_target"] == "PASS"


def test_value_match_tolerance(src):
    tgt = src.copy()
    tgt["amount"] += 0.005
    assert v.check_value_match(src, tgt, "id", "amount", 0.01).status == "PASS"


def test_missing_keys_reported(src):
    res = v.check_key_reconciliation(src, src[src.id != 3], "id")
    assert res[0].status == "FAIL" and res[0].details["sample_keys"] == [3]


def test_int_column_with_nulls_is_still_int(src):
    tgt = src.copy()
    tgt["id"] = tgt["id"].astype(float)
    tgt.loc[0, "id"] = None
    assert v._infer_type(tgt["id"]) == "int"


# -------------------------------------------------------------- guardrails

def _validation():
    return {"checks": [
        {"check_id": "a", "status": "FAIL"},
        {"check_id": "b", "status": "FAIL"},
        {"check_id": "c", "status": "PASS"},
    ]}


def test_guardrails_strip_bad_citations_and_flag_unexplained():
    out = rca.enforce_guardrails({"findings": [{
        "title": "x", "check_ids": ["a", "c", "zzz"], "confidence": "high", "assumptions": [],
        "facts": [{"statement": "real", "source": "a"}, {"statement": "made up", "source": "jira-123"}],
    }]}, _validation(), {"etl.sql": ""})
    f = out["findings"][0]
    assert f["check_ids"] == ["a"]                     # passing + unknown checks removed
    assert [x["source"] for x in f["facts"]] == ["a"]  # unsourced fact demoted
    assert "made up" in f["assumptions"]
    assert out["unexplained_checks"] == ["b"]          # nothing silently dropped


def test_guardrails_lower_confidence_without_facts():
    out = rca.enforce_guardrails({"findings": [{
        "title": "x", "check_ids": ["a"], "confidence": "high", "assumptions": [],
        "facts": [{"statement": "?", "source": "nowhere"}]}]}, _validation(), {})
    assert out["findings"][0]["confidence"] == "medium"


# ----------------------------------------------------------- LLM wiring

class FakeClient:
    def __init__(self, payload):
        self.payload, self.calls = payload, []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(
            content=[SimpleNamespace(type="tool_use", input=self.payload)],
            usage=SimpleNamespace(input_tokens=100, output_tokens=50))


def test_llm_analyzer_forces_tool_and_parses_output():
    payload = {"findings": [], "summary": "ok"}
    client = FakeClient(payload)
    out = rca.LLMAnalyzer(model="m", client=client).analyze({"failed_checks": [], "context_files": {}})
    call = client.calls[0]
    assert call["tool_choice"]["name"] == "submit_root_cause_analysis"
    assert "Evidence" in call["messages"][0]["content"]
    assert out["summary"] == "ok" and out["usage"]["input_tokens"] == 100


def test_evidence_contains_results_not_raw_data(src):
    tgt = src.copy()
    tgt.loc[0, "amount"] = 99.0
    ev = rca.build_evidence(run_validations(src, tgt, RULES), {})
    assert {c["check_id"] for c in ev["failed_checks"]} == {"value_match.amount"}
    assert "passed_check_ids" in ev


# ------------------------------------------------------------ scenarios

def _run_scenario(name):
    import json
    from pathlib import Path
    from dq_agent.sample_data import build
    src, tgt, truth = build(name)
    rules = json.loads((Path(__file__).parent.parent / "rules" / "orders_rules.json").read_text())
    return run_validations(src, tgt, rules), truth


def test_basic_scenario_matches_plan_expected_output():
    res, _ = _run_scenario("basic")
    assert res["summary"] == {"total": 18, "passed": 15, "failed": 3}
    failed = {c["check_id"]: c["affected_rows"] for c in res["checks"] if c["status"] == "FAIL"}
    assert failed["missing_values.customer_id"] == 120
    assert set(failed) == {"missing_values.customer_id", "value_match.revenue", "rule.revenue_formula"}


def test_every_seeded_defect_is_detected_and_explained():
    from dq_agent.evaluate import score
    from pathlib import Path
    ctx = rca.load_context(Path(__file__).parent.parent / "context")
    for name in ("basic", "advanced"):
        res, truth = _run_scenario(name)
        analysis = rca.enforce_guardrails(
            rca.HeuristicAnalyzer().analyze(rca.build_evidence(res, ctx)), res, ctx)
        sc = score(truth, res, analysis)
        assert sc["detection_rate"] == 1.0 and sc["explanation_rate"] == 1.0, name
