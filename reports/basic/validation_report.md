# Data Validation Report: orders

Run at 2026-10-11T16:24:41+00:00 · source rows 2000 · target rows 2000

**PASS: 15  FAIL: 3  (of 18 checks)**

## Issues

- customer_id missing in 120 records
- revenue mismatch between source and target (488 records)
- Business rule failed: revenue = quantity * unit_price * (1 - discount) (488 records)

## Checks

| Status | Check | Expected | Actual | Affected rows |
|---|---|---|---|---|
| FAIL | `missing_values.customer_id` | 0 | 120 | 120 |
| FAIL | `value_match.revenue` | 0 | 488 | 488 |
| FAIL | `rule.revenue_formula` | 0 | 488 | 488 |
| PASS | `record_count` | 2000 | 2000 | 0 |
| PASS | `schema_columns` | ["currency", "customer_id", "discount", "order_date", "order_id", "quantity",... | ["currency", "customer_id", "discount", "order_date", "order_id", "quantity",... | 0 |
| PASS | `duplicates.order_id.source` | 0 | 0 | 0 |
| PASS | `duplicates.order_id` | 0 | 0 | 0 |
| PASS | `keys_missing_in_target` | 0 | 0 | 0 |
| PASS | `keys_unexpected_in_target` | 0 | 0 | 0 |
| PASS | `data_types` | {"order_id": "int", "customer_id": "int", "order_date": "date", "currency": "... | {"order_id": "int", "customer_id": "int", "order_date": "date", "currency": "... | 0 |
| PASS | `missing_values.order_id` | 0 | 0 | 0 |
| PASS | `missing_values.revenue` | 0 | 0 | 0 |
| PASS | `missing_values.status` | 0 | 0 | 0 |
| PASS | `value_match.quantity` | 0 | 0 | 0 |
| PASS | `value_match.unit_price` | 0 | 0 | 0 |
| PASS | `value_match.status` | 0 | 0 | 0 |
| PASS | `rule.discount_range` | 0 | 0 | 0 |
| PASS | `rule.allowed_status` | 0 | 0 | 0 |

## Mismatch details

### `missing_values.customer_id`: No NULLs in required column customer_id

```json
{
 "null_pct": 6.0
}
```

### `value_match.revenue`: revenue matches source for matched order_ids

```json
{
 "rows_compared": 2000,
 "null_in_target": 0,
 "sample": [
  {
   "order_id": 100004,
   "revenue_src": 245.54,
   "revenue_tgt": 265.18
  },
  {
   "order_id": 100010,
   "revenue_src": 1206.83,
   "revenue_tgt": 1303.38
  },
  {
   "order_id": 100019,
   "revenue_src": 481.28,
   "revenue_tgt": 519.78
  },
  {
   "order_id": 100021,
   "revenue_src": 232.97,
   "revenue_tgt": 251.61
  },
  {
   "order_id": 100030,
   "revenue_src": 848.05,
   "revenue_tgt": 915.89
  }
 ],
 "target_to_source_ratio": {
  "median": 1.08,
  "min": 1.0799,
  "max": 1.0801
 }
}
```

### `rule.revenue_formula`: revenue = quantity * unit_price * (1 - discount)

```json
{
 "rule": "revenue = quantity * unit_price * (1 - discount)",
 "sample": [
  {
   "order_id": 100004,
   "customer_id": 263.0,
   "order_date": "2026-09-14",
   "currency": "EUR",
   "quantity": 4,
   "unit_price": 76.73,
   "discount": 0.2,
   "revenue": 265.18,
   "status": "delivered"
  },
  {
   "order_id": 100010,
   "customer_id": 57.0,
   "order_date": "2026-09-19",
   "currency": "EUR",
   "quantity": 5,
   "unit_price": 254.07,
   "discount": 0.05,
   "revenue": 1303.38,
   "status": "returned"
  },
  {
   "order_id": 100019,
   "customer_id": 504.0,
   "order_date": "2026-09-22",
   "currency": "EUR",
   "quantity": 3,
   "unit_price": 178.25,
   "discount": 0.1,
   "revenue": 519.78,
   "status": "returned"
  },
  {
   "order_id": 100021,
   "customer_id": 300.0,
   "order_date": "2026-09-10",
   "currency": "EUR",
   "quantity": 3,
   "unit_price": 91.36,
   "discount": 0.15,
   "revenue": 251.61,
   "status": "shipped"
  },
  {
   "order_id": 100030,
   "customer_id": 266.0,
   "order_date": "2026-09-11",
   "currency": "EUR",
   "quantity": 6,
   "unit_price": 148.78,
   "discount": 0.05,
   "revenue": 915.89,
   "status": "placed"
  }
 ]
}
```


## Root cause analysis (offline heuristic baseline)

Heuristic analysis matched 2 known failure patterns.

### 1. NULL customer_id in target  ·  confidence: high

Explains: `missing_values.customer_id`

**Facts (from evidence)**

- 120 NULL customer_id values in target  _[missing_values.customer_id]_
- customer_id is taken from a LEFT JOIN to warehouse.dim_customer  _[etl_transform.sql]_
- Context records a change to dim_customer  _[changelog.md]_
- Context records a change to dim_customer  _[metadata.json]_

**Likely root cause (hypothesis):** A key change in dim_customer breaks the join, so unmatched rows get NULL customer_id.

**Assumptions**

- Missing values are not present upstream

**Recommended next steps**

1. Query unmatched customer_id values against the dimension
2. Update the join to the new key format or add a mapping table

### 2. revenue mismatch  ·  confidence: high

Explains: `value_match.revenue`, `rule.revenue_formula`

**Facts (from evidence)**

- 488 rows differ; target/source ratio median 1.08 (range 1.0799–1.0801)  _[value_match.revenue]_
- All mismatched rows have currency = EUR  _[value_match.revenue]_
- Transform has special handling when currency = 'EUR'  _[etl_transform.sql]_

**Likely root cause (hypothesis):** The transform converts revenue for EUR rows, but source revenue is already converted (double conversion).

**Assumptions**

- The rate used equals the observed ratio

**Recommended next steps**

1. Compare revenue for a few EUR orders at each pipeline stage
2. Remove the duplicate conversion and reprocess affected dates
