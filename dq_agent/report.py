"""Day 25: turn validation results + RCA into a readable report (Markdown and HTML)."""
from __future__ import annotations

import html
import json


def _fmt(v) -> str:
    if isinstance(v, (dict, list)):
        s = json.dumps(v, default=str)
        return s if len(s) < 80 else s[:77] + "..."
    return str(v)


def issue_line(c: dict) -> str:
    """One plain-English sentence per failed check (as in the plan's example output)."""
    cid, n = c["check_id"], c["affected_rows"]
    col = cid.split(".", 1)[1] if "." in cid else ""
    if cid.startswith("missing_values."):
        return f"{col} missing in {n} records"
    if cid.startswith("value_match."):
        return f"{col} mismatch between source and target ({n} records)"
    if cid.startswith("duplicates."):
        side = "source" if cid.endswith(".source") else "target"
        return f"{n} duplicate {col.split('.')[0]} values in {side}"
    if cid == "keys_missing_in_target":
        return f"{n} source records missing from target"
    if cid == "keys_unexpected_in_target":
        return f"{n} target records not found in source"
    if cid == "record_count":
        return f"Record count differs: source {c['expected']}, target {c['actual']}"
    if cid.startswith("rule."):
        return f"Business rule failed: {c['description']} ({n} records)"
    return f"{c['description']}: failed"


def to_markdown(val: dict, rca: dict) -> str:
    s = val["summary"]
    failed_checks = [c for c in val["checks"] if c["status"] == "FAIL"]
    L = [
        f"# Data Validation Report: {val.get('dataset', '')}",
        "",
        f"Run at {val['run_at']} · source rows {val['source_rows']} · target rows {val['target_rows']}",
        "",
        f"**PASS: {s['passed']}  FAIL: {s['failed']}  (of {s['total']} checks)**",
        "",
    ]
    if failed_checks:
        L += ["## Issues", ""] + [f"- {issue_line(c)}" for c in failed_checks] + [""]
    L += [
        "## Checks",
        "",
        "| Status | Check | Expected | Actual | Affected rows |",
        "|---|---|---|---|---|",
    ]
    for c in sorted(val["checks"], key=lambda c: c["status"]):
        L.append(f"| {c['status']} | `{c['check_id']}` | {_fmt(c['expected'])} | {_fmt(c['actual'])} | {c['affected_rows']} |")

    failed = [c for c in val["checks"] if c["status"] == "FAIL"]
    if failed:
        L += ["", "## Mismatch details", ""]
        for c in failed:
            L.append(f"### `{c['check_id']}`: {c['description']}")
            d = {k: v for k, v in c["details"].items() if not k.startswith("profile_")}
            L += ["", "```json", json.dumps(d, indent=1, default=str)[:1500], "```", ""]

    mode = rca.get("mode")
    label = f"Claude ({rca.get('model')})" if mode == "llm" else "offline heuristic baseline"
    L += ["", f"## Root cause analysis ({label})", "", rca.get("summary", ""), ""]
    for i, f in enumerate(rca.get("findings", []), 1):
        L += [f"### {i}. {f['title']}  ·  confidence: {f['confidence']}",
              "", f"Explains: {', '.join(f'`{x}`' for x in f['check_ids'])}", "",
              "**Facts (from evidence)**", ""]
        L += [f"- {x['statement']}  _[{x['source']}]_" for x in f["facts"]] or ["- none"]
        L += ["", f"**Likely root cause (hypothesis):** {f['hypothesis']}", "", "**Assumptions**", ""]
        L += [f"- {a}" for a in f.get("assumptions", [])] or ["- none"]
        L += ["", "**Recommended next steps**", ""]
        L += [f"{n}. {step}" for n, step in enumerate(f.get("next_steps", []), 1)]
        L.append("")
    if rca.get("unexplained_checks"):
        L += ["### Not explained by the analysis", "",
              "These checks failed but no finding explains them. Investigate manually:", ""]
        L += [f"- `{x}`" for x in rca["unexplained_checks"]]
        L.append("")
    if rca.get("guardrail_warnings"):
        L += ["### Guardrail corrections", ""] + [f"- {w}" for w in rca["guardrail_warnings"]] + [""]
    return "\n".join(L)


CSS = """
:root{--bg:#fbfaf7;--fg:#1f2328;--muted:#5b6370;--card:#fff;--line:#e3e0d8;--pass:#1a7f4b;--fail:#c2410c;--accent:#3b5bdb}
@media (prefers-color-scheme:dark){:root{--bg:#15171a;--fg:#e6e6e6;--muted:#9aa3ad;--card:#1d2024;--line:#2d3137;--pass:#4ade80;--fail:#fb923c;--accent:#8ea4ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:980px;margin:0 auto;padding:32px 16px 64px}h1{font-size:26px;margin:0 0 4px}h2{margin-top:40px;font-size:19px}
.meta{color:var(--muted);font-size:13px}.kpis{display:flex;gap:12px;margin:20px 0;flex-wrap:wrap}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 18px;min-width:120px}
.kpi b{display:block;font-size:28px}.pass{color:var(--pass)}.fail{color:var(--fail)}
.tablewrap{overflow-x:auto}table{border-collapse:collapse;width:100%;background:var(--card);border:1px solid var(--line);border-radius:10px;font-size:13.5px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:600}
code{font:12.5px ui-monospace,Menlo,monospace}.card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:10px;padding:14px 18px;margin:14px 0}
.card h3{margin:0 0 6px;font-size:16px}.tag{font-size:12px;border:1px solid var(--line);border-radius:99px;padding:1px 8px;color:var(--muted)}
.src{color:var(--muted);font-size:12px}.hyp{background:color-mix(in srgb,var(--accent) 8%,transparent);padding:8px 10px;border-radius:6px}
details pre{white-space:pre-wrap;font-size:12px;background:var(--bg);padding:8px;border-radius:6px}
"""


def to_html(val: dict, rca: dict) -> str:
    e = html.escape
    s = val["summary"]
    rows = "".join(
        f"<tr><td class='{c['status'].lower()}'><b>{c['status']}</b></td><td><code>{e(c['check_id'])}</code><br>"
        f"<span class='src'>{e(c['description'])}</span></td><td>{e(_fmt(c['expected']))}</td>"
        f"<td>{e(_fmt(c['actual']))}</td><td>{c['affected_rows']}</td></tr>"
        for c in sorted(val["checks"], key=lambda c: c["status"])
    )
    details = "".join(
        f"<details><summary><code>{e(c['check_id'])}</code> · {c['affected_rows']} rows</summary><pre>"
        f"{e(json.dumps({k: v for k, v in c['details'].items() if not k.startswith('profile_')}, indent=1, default=str)[:2000])}"
        f"</pre></details>" for c in val["checks"] if c["status"] == "FAIL"
    )
    cards = ""
    for f in rca.get("findings", []):
        facts = "".join(f"<li>{e(x['statement'])} <span class='src'>[{e(x['source'])}]</span></li>" for x in f["facts"])
        assm = "".join(f"<li>{e(a)}</li>" for a in f.get("assumptions", []))
        steps = "".join(f"<li>{e(n)}</li>" for n in f.get("next_steps", []))
        cards += (f"<div class='card'><h3>{e(f['title'])} <span class='tag'>confidence: {e(f['confidence'])}</span></h3>"
                  f"<div class='src'>Explains: {', '.join(f'<code>{e(x)}</code>' for x in f['check_ids'])}</div>"
                  f"<p><b>Facts (from evidence)</b></p><ul>{facts or '<li>none</li>'}</ul>"
                  f"<p class='hyp'><b>Likely root cause:</b> {e(f['hypothesis'])}</p>"
                  f"<p><b>Assumptions</b></p><ul>{assm or '<li>none</li>'}</ul>"
                  f"<p><b>Next steps</b></p><ol>{steps}</ol></div>")
    unexplained = ""
    if rca.get("unexplained_checks"):
        unexplained = ("<div class='card' style='border-left-color:var(--fail)'><h3>Not explained by the analysis</h3>"
                       "<p>These checks failed but no finding explains them. Investigate manually.</p><ul>"
                       + "".join(f"<li><code>{e(x)}</code></li>" for x in rca["unexplained_checks"]) + "</ul></div>")
    label = f"Claude ({rca.get('model')})" if rca.get("mode") == "llm" else "offline heuristic baseline"
    failed_checks = [c for c in val["checks"] if c["status"] == "FAIL"]
    issues = ("<h2>Issues</h2><ul>" + "".join(f"<li>{e(issue_line(c))}</li>" for c in failed_checks) + "</ul>"
              if failed_checks else "")
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Validation Report</title><style>{CSS}</style></head><body><main>
<h1>Data Validation Report: {e(str(val.get('dataset', '')))}</h1>
<div class="meta">Run {e(val['run_at'])} · source rows {val['source_rows']} · target rows {val['target_rows']}</div>
<div class="kpis"><div class="kpi">Checks<b>{s['total']}</b></div><div class="kpi">Passed<b class="pass">{s['passed']}</b></div>
<div class="kpi">Failed<b class="fail">{s['failed']}</b></div></div>
{issues}
<h2>Root cause analysis</h2><div class="meta">Analyzer: {e(label)}</div><p>{e(rca.get('summary', ''))}</p>{cards}{unexplained}
<h2>All checks</h2><div class="tablewrap"><table><tr><th>Status</th><th>Check</th><th>Expected</th><th>Actual</th><th>Affected</th></tr>{rows}</table></div>
<h2>Mismatch details</h2>{details}
</main></body></html>"""
