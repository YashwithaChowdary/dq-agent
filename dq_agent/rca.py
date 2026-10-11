"""AI root cause analysis.

Design rules (the important part of this project):
  1. The AI never sees raw data, only validation RESULTS + small row profiles
     + pipeline context (ETL SQL, metadata, changelog). The facts come from code.
  2. Every finding must cite the check_ids and context files it relies on.
     Facts and hypotheses are separate fields.
  3. Output is checked after generation: citations to unknown or passing checks
     are removed, and any failed check the AI didn't explain is reported as
     "unexplained" instead of disappearing.

Two analyzers share one output format:
  - LLMAnalyzer: Claude via the Anthropic API (needs ANTHROPIC_API_KEY)
  - HeuristicAnalyzer: offline, rule-based baseline. Useful for tests, for runs
    without an API key, and as a yardstick the LLM has to beat.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

DEFAULT_MODEL = os.environ.get("DQ_MODEL", "claude-sonnet-5-5")

# ------------------------------------------------------------------ evidence

def load_context(context_dir: str | Path | None) -> dict[str, str]:
    if not context_dir:
        return {}
    files = {}
    for p in sorted(Path(context_dir).glob("*")):
        if p.is_file() and p.suffix in {".sql", ".md", ".json", ".yaml", ".yml", ".txt"}:
            files[p.name] = p.read_text()[:20_000]
    return files


def build_evidence(validation: dict, context: dict[str, str]) -> dict:
    failed = [c for c in validation["checks"] if c["status"] == "FAIL"]
    passed = [c["check_id"] for c in validation["checks"] if c["status"] == "PASS"]
    return {
        "dataset": validation.get("dataset"),
        "source_rows": validation.get("source_rows"),
        "target_rows": validation.get("target_rows"),
        "failed_checks": failed,
        "passed_check_ids": passed,
        "context_files": context,
    }


# ----------------------------------------------------------------- schema

FINDING_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short name of the issue"},
                    "check_ids": {"type": "array", "items": {"type": "string"},
                                  "description": "Failed check_ids this finding explains"},
                    "facts": {
                        "type": "array",
                        "description": "Observations taken directly from the evidence",
                        "items": {
                            "type": "object",
                            "properties": {
                                "statement": {"type": "string"},
                                "source": {"type": "string",
                                           "description": "check_id or context file name"},
                            },
                            "required": ["statement", "source"],
                        },
                    },
                    "hypothesis": {"type": "string", "description": "Most likely root cause"},
                    "assumptions": {"type": "array", "items": {"type": "string"},
                                    "description": "Things inferred but NOT shown by the evidence"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "next_steps": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "check_ids", "facts", "hypothesis", "assumptions",
                             "confidence", "next_steps"],
            },
        },
        "summary": {"type": "string", "description": "2-3 sentence overall assessment"},
    },
    "required": ["findings", "summary"],
}

SYSTEM_PROMPT = """You are a senior data engineer doing root cause analysis on a failed \
source-to-target data validation.

You receive JSON evidence: failed checks (with counts, samples and row profiles), the ids \
of checks that passed, and pipeline context files (ETL SQL, metadata, change log).

Rules:
- Group related failed checks into findings. One root cause can explain several checks; \
one check can be affected by several causes (e.g. a row count difference that is the net \
of dropped rows and duplicates). Show the arithmetic when you do that.
- "facts" must be directly visible in the evidence, each with its source (a check_id or a \
context file name). Do not put guesses in facts.
- "hypothesis" is your best explanation. Anything you inferred goes in "assumptions".
- Passed checks are evidence too: use them to rule causes out.
- If the context does not explain a failure, say so, set confidence to "low", and \
recommend how to find out. Never invent changes, tickets or people.
- Next steps must be concrete (a query to run, a file to check, a fix to make).
Submit your answer with the submit_root_cause_analysis tool."""


# --------------------------------------------------------------- analyzers

class LLMAnalyzer:
    mode = "llm"

    def __init__(self, model: str = DEFAULT_MODEL, client=None):
        self.model = model
        if client is None:
            import anthropic  # imported lazily so offline mode needs no SDK
            client = anthropic.Anthropic()
        self.client = client

    def analyze(self, evidence: dict) -> dict:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            tools=[{
                "name": "submit_root_cause_analysis",
                "description": "Submit the structured root cause analysis.",
                "input_schema": FINDING_SCHEMA,
            }],
            tool_choice={"type": "tool", "name": "submit_root_cause_analysis"},
            messages=[{"role": "user", "content": "Evidence:\n```json\n"
                       + json.dumps(evidence, indent=1, default=str) + "\n```"}],
        )
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                out = dict(block.input)
                out["usage"] = {"input_tokens": resp.usage.input_tokens,
                                "output_tokens": resp.usage.output_tokens}
                return out
        raise RuntimeError("Model did not return a tool_use block")


class HeuristicAnalyzer:
    """Offline baseline: pattern rules over the same evidence the LLM gets.
    Deliberately simple. It is generic (no hard-coded column names) but
    only knows a handful of failure patterns."""

    mode = "heuristic"
    model = None

    def analyze(self, evidence: dict) -> dict:
        failed = {c["check_id"]: c for c in evidence["failed_checks"]}
        ctx = evidence["context_files"]
        all_ctx = "\n".join(ctx.values())
        sql_name, sql = next(((n, t) for n, t in ctx.items() if n.endswith(".sql")), (None, ""))
        findings = []

        # Pattern 1: duplicates + retry/append in context
        for cid, c in failed.items():
            if cid.startswith("duplicates.") and not cid.endswith(".source"):
                facts = [{"statement": f"{c['actual']} duplicate key rows in target", "source": cid}]
                src_files = [n for n, t in ctx.items() if re.search(r"retr(y|ied)", t, re.I)]
                app_files = [n for n, t in ctx.items() if re.search(r"\bappend\b", t, re.I)]
                conf = "high" if src_files and app_files else "low"
                for n in src_files:
                    facts.append({"statement": "Context mentions a retried load", "source": n})
                for n in app_files:
                    facts.append({"statement": "Load mode is APPEND", "source": n})
                if "duplicates." + cid.split(".")[1] + ".source" not in failed:
                    facts.append({"statement": "Source keys are unique, so duplicates were introduced by the load",
                                  "source": "duplicates." + cid.split(".")[1] + ".source"})
                findings.append(_f("Duplicate rows from non-idempotent load", [cid], facts,
                                   "A load was re-run in append mode, inserting part of a batch twice.",
                                   ["The retry is the only re-run in the window"], conf,
                                   ["Count duplicates by load batch/ingestion timestamp",
                                    "Switch the load to MERGE on the primary key",
                                    "Deduplicate the affected partition"]))

        # Pattern 2: keys missing in target + a WHERE filter in SQL on a profiled column
        c = failed.get("keys_missing_in_target")
        if c:
            prof = c["details"].get("profile_of_missing_rows", {})
            facts = [{"statement": f"{c['actual']} source keys absent from target", "source": c["check_id"]}]
            hyp, conf, ids = "Rows were dropped during transform; cause not identified from context.", "low", [c["check_id"]]
            for m in re.finditer(r"WHERE\s+[\w.]*?(\w+)\s*(>|>=|<|<=|=|<>|!=)\s*([\w'.-]+)", sql, re.I):
                col, op, val = m.groups()
                p = prof.get(col)
                if isinstance(p, dict) and "max" in p:
                    facts.append({"statement": f"All missing rows have {col} between {p['min']} and {p['max']}",
                                  "source": c["check_id"]})
                    facts.append({"statement": f"Transform filters on {col} {op} {val}", "source": sql_name})
                    hyp = f"The filter `{col} {op} {val}` in the transform removes these rows."
                    conf = "high"
            if "record_count" in failed:
                ids.append("record_count")
                rc = failed["record_count"]
                dup = next((x for k, x in failed.items() if k.startswith("duplicates.") and not k.endswith(".source")), None)
                if dup:
                    facts.append({"statement": f"Net row difference {rc['details']['difference']} = "
                                  f"-{c['actual']} dropped + {dup['actual']} duplicates",
                                  "source": "record_count"})
            findings.append(_f("Source rows dropped by transform", ids, facts, hyp,
                               ["The dropped rows are valid business records (e.g. refunds)"], conf,
                               ["Confirm with the data owner whether these rows should be excluded",
                                "If not, remove or narrow the filter and backfill"]))

        # Pattern 3: NULLs in a column that comes from a JOIN to a changed table
        for cid, c in failed.items():
            if not cid.startswith("missing_values."):
                continue
            col = cid.split(".", 1)[1]
            ids = [cid] + ([f"value_match.{col}"] if f"value_match.{col}" in failed else [])
            facts = [{"statement": f"{c['actual']} NULL {col} values in target", "source": cid}]
            join = re.search(rf"JOIN\s+([\w.]+)\s+(\w+)\s+ON\s+\2\.{col}", sql, re.I)
            hyp, conf = f"{col} is lost in the pipeline; cause not identified.", "low"
            if join:
                table = join.group(1).split(".")[-1]
                facts.append({"statement": f"{col} is taken from a LEFT JOIN to {join.group(1)}", "source": sql_name})
                mentions = [n for n, t in ctx.items() if table in t and not n.endswith(".sql")]
                for n in mentions:
                    facts.append({"statement": f"Context records a change to {table}", "source": n})
                if mentions:
                    hyp, conf = f"A key change in {table} breaks the join, so unmatched rows get NULL {col}.", "high"
                else:
                    hyp, conf = f"Rows fail to match {table} in the LEFT JOIN.", "medium"
            if f"missing_values.{col}" in failed and "value_match." + col in failed:
                facts.append({"statement": "Source has no NULLs for the same keys (value mismatch shows NULL in target)",
                              "source": f"value_match.{col}"})
            findings.append(_f(f"NULL {col} in target", ids, facts, hyp,
                               ["Missing values are not present upstream"], conf,
                               [f"Query unmatched {col} values against the dimension",
                                "Update the join to the new key format or add a mapping table"]))

        # Pattern 4: numeric mismatch with a constant ratio concentrated in one category
        for cid, c in failed.items():
            if not cid.startswith("value_match."):
                continue
            ratio = c["details"].get("target_to_source_ratio")
            if not ratio:
                continue
            col = cid.split(".")[1]
            prof = c["details"].get("profile_of_mismatched_rows", {})
            facts = [{"statement": f"{c['actual']} rows differ; target/source ratio median {ratio['median']} "
                      f"(range {ratio['min']}–{ratio['max']})", "source": cid}]
            cat = None
            for k, p in prof.items():
                tv = p.get("top_values", {}) if isinstance(p, dict) else {}
                if len(tv) == 1:
                    cat = (k, next(iter(tv)))
                    facts.append({"statement": f"All mismatched rows have {k} = {cat[1]}", "source": cid})
            ids = [cid] + [r for r in failed if r.startswith("rule.") and col in json.dumps(failed[r]["details"].get("rule", ""))]
            hyp, conf = f"A multiplicative transform (x{ratio['median']}) is applied to {col}.", "medium"
            if cat and re.search(rf"{cat[1]}", sql):
                facts.append({"statement": f"Transform has special handling when {cat[0]} = '{cat[1]}'", "source": sql_name})
                hyp = f"The transform converts {col} for {cat[1]} rows, but source {col} is already converted (double conversion)." \
                    if re.search(r"already", all_ctx, re.I) else f"The transform's {cat[1]}-specific logic changes {col}."
                conf = "high"
            findings.append(_f(f"{col} mismatch", ids, facts, hyp,
                               ["The rate used equals the observed ratio"], conf,
                               [f"Compare {col} for a few {cat[1] if cat else 'affected'} orders at each pipeline stage",
                                "Remove the duplicate conversion and reprocess affected dates"]))

        return {"findings": findings,
                "summary": f"Heuristic analysis matched {len(findings)} known failure patterns."}


def _f(title, ids, facts, hyp, assumptions, conf, steps) -> dict:
    return {"title": title, "check_ids": ids, "facts": facts, "hypothesis": hyp,
            "assumptions": assumptions, "confidence": conf, "next_steps": steps}


# ---------------------------------------------------------------- guardrails

def enforce_guardrails(rca: dict, validation: dict, context: dict[str, str]) -> dict:
    status = {c["check_id"]: c["status"] for c in validation["checks"]}
    allowed_sources = set(status) | set(context)
    warnings = []
    covered: set[str] = set()
    for f in rca.get("findings", []):
        good = [cid for cid in f.get("check_ids", []) if status.get(cid) == "FAIL"]
        dropped = set(f.get("check_ids", [])) - set(good)
        if dropped:
            warnings.append(f"'{f['title']}': removed citations to unknown/passing checks {sorted(dropped)}")
        f["check_ids"] = good
        covered |= set(good)
        kept = []
        for fact in f.get("facts", []):
            if fact.get("source") in allowed_sources:
                kept.append(fact)
            else:
                warnings.append(f"'{f['title']}': moved unsourced fact to assumptions: {fact.get('statement')}")
                f.setdefault("assumptions", []).append(fact.get("statement", ""))
        f["facts"] = kept
        if not kept and f.get("confidence") == "high":
            f["confidence"] = "medium"
            warnings.append(f"'{f['title']}': confidence lowered, no sourced facts")
    rca["unexplained_checks"] = sorted(cid for cid, s in status.items() if s == "FAIL" and cid not in covered)
    rca["guardrail_warnings"] = warnings
    return rca


def analyze(validation: dict, context_dir=None, mode: str = "auto", model: str = DEFAULT_MODEL) -> dict:
    """mode: 'llm', 'heuristic', or 'auto' (LLM if an API key is set)."""
    context = load_context(context_dir)
    evidence = build_evidence(validation, context)
    if not evidence["failed_checks"]:
        return {"mode": "none", "findings": [], "summary": "All checks passed.",
                "unexplained_checks": [], "guardrail_warnings": []}
    if mode == "auto":
        mode = "llm" if os.environ.get("ANTHROPIC_API_KEY") else "heuristic"
    analyzer = LLMAnalyzer(model) if mode == "llm" else HeuristicAnalyzer()
    rca = analyzer.analyze(evidence)
    rca["mode"] = analyzer.mode
    rca["model"] = analyzer.model
    rca["context_files"] = list(context)
    return enforce_guardrails(rca, validation, context)
