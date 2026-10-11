"""Sample data with KNOWN, seeded defects.

Because we inject the defects ourselves, we know the true root cause of every
failure, so the AI root-cause agent can be scored instead of trusted.

Two scenarios:
  basic    - the two issues from the Week 5 plan's expected output
             (Customer_ID missing in 120 records, revenue mismatch)
             -> PASS 15 / FAIL 3
  advanced - five defects, including one with no documented cause
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_ROWS = 2000
MISSING_CUSTOMER_ROWS = 120


def make_source(rng: np.random.Generator) -> pd.DataFrame:
    n = N_ROWS
    customer_id = rng.integers(1, 600, size=n)
    order_date = pd.Timestamp("2026-09-01") + pd.to_timedelta(rng.integers(0, 30, size=n), unit="D")
    currency = rng.choice(["USD", "EUR", "INR"], size=n, p=[0.55, 0.25, 0.20])
    quantity = rng.integers(1, 10, size=n)
    refund_idx = rng.choice(n, size=40, replace=False)        # ~2% refunds (negative qty)
    quantity[refund_idx] = -rng.integers(1, 4, size=40)
    unit_price = np.round(rng.uniform(5, 500, size=n), 2)
    discount = np.round(rng.choice([0, 0.05, 0.1, 0.15, 0.2], size=n), 2)
    status = rng.choice(["placed", "shipped", "delivered", "returned"], size=n, p=[0.2, 0.3, 0.45, 0.05])
    revenue = np.round(quantity * unit_price * (1 - discount), 2)
    return pd.DataFrame({
        "order_id": np.arange(100001, 100001 + n),
        "customer_id": customer_id,
        "order_date": order_date.strftime("%Y-%m-%d"),
        "currency": currency,
        "quantity": quantity,
        "unit_price": unit_price,
        "discount": discount,
        "revenue": revenue,
        "status": status,
    })


# ------------------------------------------------------------------ defects

def _null_migrated_customers(tgt: pd.DataFrame, rng, target_rows: int) -> int:
    """Customer key migration (DIM-412): orders of migrated customers lose their
    customer_id because the join no longer matches. Customers are picked so the
    number of affected rows is exactly `target_rows`."""
    counts = tgt["customer_id"].value_counts()
    migrated, total = [], 0
    for cust in rng.permutation(counts.index.to_numpy()):
        c = int(counts[cust])
        if total + c <= target_rows:
            migrated.append(cust)
            total += c
        if total == target_rows:
            break
    mask = tgt["customer_id"].isin(migrated)
    tgt["customer_id"] = tgt["customer_id"].astype("Int64")
    tgt.loc[mask, "customer_id"] = pd.NA
    return int(mask.sum())


def _double_convert_eur(tgt: pd.DataFrame) -> int:
    eur = tgt["currency"] == "EUR"
    tgt.loc[eur, "revenue"] = np.round(tgt.loc[eur, "revenue"] * 1.08, 2)
    return int(eur.sum())


def D_customer(n):
    return {"id": "D2", "symptom": f"Customer_ID missing in {n} records",
            "true_cause": "dim_customer key migrated to 'C-' prefixed strings; LEFT JOIN on integer key fails for migrated customers",
            "expected_checks": ["missing_values.customer_id"],
            "keywords": ["join", "dim_customer", "key"]}


def D_revenue(n):
    return {"id": "D3", "symptom": f"Revenue mismatch between source and target ({n} EUR records, x1.08)",
            "true_cause": "FX conversion applied twice for EUR orders in transform v2.3",
            "expected_checks": ["value_match.revenue", "rule.revenue_formula"],
            "keywords": ["fx", "eur", "currency"]}


def make_basic(src: pd.DataFrame, rng) -> tuple[pd.DataFrame, list[dict]]:
    tgt = src.copy()
    n_null = _null_migrated_customers(tgt, rng, MISSING_CUSTOMER_ROWS)
    n_eur = _double_convert_eur(tgt)
    return tgt.reset_index(drop=True), [D_customer(n_null), D_revenue(n_eur)]


def make_advanced(src: pd.DataFrame, rng) -> tuple[pd.DataFrame, list[dict]]:
    truth: list[dict] = []
    # D1: new filter in transform v2.3 drops refunds (quantity <= 0)
    n_drop = int((src["quantity"] <= 0).sum())
    tgt = src[src["quantity"] > 0].copy()
    truth.append({"id": "D1", "symptom": f"{n_drop} source orders missing from target",
                  "true_cause": "Transform v2.3 added WHERE quantity > 0, silently dropping refund orders",
                  "expected_checks": ["record_count", "keys_missing_in_target"],
                  "keywords": ["quantity", "refund", "filter"]})
    # D2, D3: same as basic
    truth.append(D_customer(_null_migrated_customers(tgt, rng, MISSING_CUSTOMER_ROWS)))
    truth.append(D_revenue(_double_convert_eur(tgt)))
    # D4: failed load retried in APPEND mode -> duplicates
    tgt = pd.concat([tgt, tgt.sample(n=25, random_state=SEED)], ignore_index=True)
    truth.append({"id": "D4", "symptom": "25 duplicate order_id rows in target",
                  "true_cause": "Load job retried in append mode without MERGE/idempotency after timeout",
                  "expected_checks": ["duplicates.order_id"],
                  "keywords": ["retry", "append", "merge"]})
    # D5: undocumented upstream casing change -> agent should NOT invent a cause
    idx = tgt.sample(n=60, random_state=7).index
    tgt.loc[idx, "status"] = tgt.loc[idx, "status"].str.upper()
    truth.append({"id": "D5", "symptom": "60 rows with status outside the allowed set",
                  "true_cause": "Upstream casing change not documented in pipeline context (should be flagged as unknown)",
                  "expected_checks": ["rule.allowed_status", "value_match.status"],
                  "keywords": ["case", "status"]})
    return tgt.reset_index(drop=True), truth


SCENARIOS = {"basic": make_basic, "advanced": make_advanced}


def build(scenario: str) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    rng = np.random.default_rng(SEED)
    src = make_source(rng)
    tgt, truth = SCENARIOS[scenario](src, rng)
    return src, tgt, truth


def write(scenario: str, root: str | Path) -> Path:
    out = Path(root) / scenario
    out.mkdir(parents=True, exist_ok=True)
    src, tgt, truth = build(scenario)
    src.to_csv(out / "source_orders.csv", index=False)
    tgt.to_csv(out / "target_orders.csv", index=False)
    (out / "ground_truth.json").write_text(json.dumps(truth, indent=2))
    return out
