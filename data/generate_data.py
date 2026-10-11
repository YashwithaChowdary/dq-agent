"""Generate the sample datasets.

Run from the project folder:
    python data/generate_data.py             # both scenarios
    python data/generate_data.py basic       # one scenario

Writes data/<scenario>/source_orders.csv, target_orders.csv, ground_truth.json
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dq_agent.sample_data import SCENARIOS, build, write  # noqa: E402

if __name__ == "__main__":
    names = sys.argv[1:] or list(SCENARIOS)
    for name in names:
        out = write(name, Path(__file__).parent)
        src, tgt, truth = build(name)
        print(f"[{name}] source rows={len(src)}  target rows={len(tgt)}  -> {out}")
        for d in truth:
            print(f"   {d['id']}: {d['symptom']}")
