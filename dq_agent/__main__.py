"""Command-line interface.

Quick start (uses the sample data in data/<scenario>/):
  python -m dq_agent demo                       # basic scenario: PASS 15 / FAIL 3
  python -m dq_agent demo --scenario advanced   # five defects

Your own data:
  python -m dq_agent run --source S.csv --target T.csv --rules R.json [--context DIR]
                         [--mode auto|llm|heuristic] [--out reports/] [--ground-truth GT.json]
                         [--fail-on-error]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import engine, rca as rca_mod, report, sample_data
from .evaluate import score

ROOT = Path(__file__).resolve().parent.parent
BULLET = "•"


def run_pipeline(source, target, rules, context, mode, model, out, ground_truth=None, fail_on_error=False) -> int:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    val = engine.run_from_files(source, target, rules)
    (out / "validation_results.json").write_text(json.dumps(val, indent=2, default=str))
    failed = [c for c in val["checks"] if c["status"] == "FAIL"]
    s = val["summary"]
    print("Validation Report")
    print(f"PASS: {s['passed']}")
    print(f"FAIL: {s['failed']}")
    if failed:
        print("\nIssues:")
        for c in failed:
            print(f"  {BULLET} {report.issue_line(c)}")

    analysis = rca_mod.analyze(val, context, mode=mode, model=model)
    (out / "root_cause_analysis.json").write_text(json.dumps(analysis, indent=2, default=str))
    if analysis["findings"]:
        print(f"\nPossible Root Causes ({analysis['mode']}):")
        for f in analysis["findings"]:
            print(f"  {BULLET} [{f['confidence']}] {f['hypothesis']}")
    if analysis.get("unexplained_checks"):
        print(f"\nNot explained (investigate manually): {', '.join(analysis['unexplained_checks'])}")

    (out / "validation_report.md").write_text(report.to_markdown(val, analysis), encoding="utf-8")
    (out / "validation_report.html").write_text(report.to_html(val, analysis), encoding="utf-8")

    if ground_truth:
        gt = json.loads(Path(ground_truth).read_text())
        sc = score(gt, val, analysis)
        (out / "rca_evaluation.json").write_text(json.dumps(sc, indent=2))
        print(f"\nEvaluation vs ground truth: detected {sc['detection_rate']:.0%}, "
              f"explained {sc['explanation_rate']:.0%}")
        for r in sc["defects"]:
            print(f"  {r['id']}  detected={r['detected']!s:<5} explained={r['explained']!s:<5} {r['symptom']}")

    print(f"\nReport: {out / 'validation_report.html'}")
    return 1 if (fail_on_error and s["failed"]) else 0


def cmd_run(a) -> int:
    return run_pipeline(a.source, a.target, a.rules, a.context, a.mode, a.model, a.out,
                        a.ground_truth, a.fail_on_error)


def cmd_demo(a) -> int:
    data_dir = ROOT / "data" / a.scenario
    if not (data_dir / "target_orders.csv").exists():
        sample_data.write(a.scenario, ROOT / "data")
    return run_pipeline(data_dir / "source_orders.csv", data_dir / "target_orders.csv",
                        ROOT / "rules" / "orders_rules.json", ROOT / "context", a.mode, a.model,
                        ROOT / "reports" / a.scenario, data_dir / "ground_truth.json", a.fail_on_error)


def main(argv=None) -> int:
    try:  # keep bullets/arrows from crashing older Windows consoles
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    p = argparse.ArgumentParser(prog="dq_agent", description="Data Quality & Root Cause Agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--mode", default="auto", choices=["auto", "llm", "heuristic"],
                        help="auto = Claude if ANTHROPIC_API_KEY is set, else heuristic")
    common.add_argument("--model", default=rca_mod.DEFAULT_MODEL)
    common.add_argument("--fail-on-error", action="store_true", help="exit 1 if any check fails (for CI)")

    d = sub.add_parser("demo", parents=[common], help="run on the bundled sample data")
    d.add_argument("--scenario", default="basic", choices=list(sample_data.SCENARIOS))
    d.set_defaults(func=cmd_demo)

    r = sub.add_parser("run", parents=[common], help="validate, analyse and report your own files")
    r.add_argument("--source", required=True)
    r.add_argument("--target", required=True)
    r.add_argument("--rules", required=True)
    r.add_argument("--context", help="folder with ETL SQL, metadata, change log")
    r.add_argument("--out", default="reports")
    r.add_argument("--ground-truth", help="score the RCA against seeded defects")
    r.set_defaults(func=cmd_run)

    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
