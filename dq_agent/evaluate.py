"""Score an RCA against the seeded ground truth.

For each injected defect we ask two questions:
  detected:   did the deterministic engine fail at least one expected check?
  explained:  does some finding cite one of those checks AND mention the real
              cause (keyword match in hypothesis/facts)?
Defect D5 has no documented cause, so the correct behaviour is to NOT claim a
confident cause: we count it as explained if its checks are listed as
unexplained or the finding covering them is low confidence.
"""
from __future__ import annotations


def score(ground_truth: list[dict], validation: dict, rca: dict) -> dict:
    failed = {c["check_id"] for c in validation["checks"] if c["status"] == "FAIL"}
    rows = []
    for d in ground_truth:
        exp = set(d["expected_checks"])
        detected = bool(exp & failed)
        undocumented = "not documented" in d["true_cause"].lower()
        explained = False
        for f in rca.get("findings", []):
            if not exp & set(f["check_ids"]):
                continue
            text = (f["hypothesis"] + " " + " ".join(x["statement"] for x in f["facts"])).lower()
            if undocumented:
                explained = explained or f["confidence"] == "low"
            elif any(k.lower() in text for k in d["keywords"]):
                explained = True
        if undocumented and exp & set(rca.get("unexplained_checks", [])):
            explained = True
        rows.append({"id": d["id"], "symptom": d["symptom"], "detected": detected, "explained": explained})
    n = len(rows)
    return {
        "detection_rate": sum(r["detected"] for r in rows) / n,
        "explanation_rate": sum(r["explained"] for r in rows) / n,
        "defects": rows,
    }
