# Data Validation Report: orders

Run at 2026-10-11T16:24:41+00:00 · source rows 2000 · target rows 1985

**PASS: 10  FAIL: 8  (of 18 checks)**

## Issues

- Record count differs: source 2000, target 1985
- 25 duplicate order_id values in target
- 40 source records missing from target
- customer_id missing in 122 records
- revenue mismatch between source and target (474 records)
- status mismatch between source and target (60 records)
- Business rule failed: revenue = quantity * unit_price * (1 - discount) (478 records)
- Business rule failed: status in allowed set (60 records)

## Checks

| Status | Check | Expected | Actual | Affected rows |
|---|---|---|---|---|
| FAIL | `record_count` | 2000 | 1985 | 15 |
| FAIL | `duplicates.order_id` | 0 | 25 | 25 |
| FAIL | `keys_missing_in_target` | 0 | 40 | 40 |
| FAIL | `missing_values.customer_id` | 0 | 122 | 122 |
| FAIL | `value_match.revenue` | 0 | 474 | 474 |
| FAIL | `value_match.status` | 0 | 60 | 60 |
| FAIL | `rule.revenue_formula` | 0 | 478 | 478 |
| FAIL | `rule.allowed_status` | 0 | 60 | 60 |
| PASS | `schema_columns` | ["currency", "customer_id", "discount", "order_date", "order_id", "quantity",... | ["currency", "customer_id", "discount", "order_date", "order_id", "quantity",... | 0 |
| PASS | `duplicates.order_id.source` | 0 | 0 | 0 |
| PASS | `keys_unexpected_in_target` | 0 | 0 | 0 |
| PASS | `data_types` | {"order_id": "int", "customer_id": "int", "order_date": "date", "currency": "... | {"order_id": "int", "customer_id": "int", "order_date": "date", "currency": "... | 0 |
| PASS | `missing_values.order_id` | 0 | 0 | 0 |
| PASS | `missing_values.revenue` | 0 | 0 | 0 |
| PASS | `missing_values.status` | 0 | 0 | 0 |
| PASS | `value_match.quantity` | 0 | 0 | 0 |
| PASS | `value_match.unit_price` | 0 | 0 | 0 |
| PASS | `rule.discount_range` | 0 | 0 | 0 |

## Mismatch details

### `record_count`: Target row count equals source row count

```json
{
 "difference": -15
}
```

### `duplicates.order_id`: order_id is unique in target

```json
{
 "sample_duplicate_keys": [
  101117,
  100584,
  100459,
  100388,
  101522
 ]
}
```

### `keys_missing_in_target`: Every source order_id exists in target

```json
{
 "sample_keys": [
  100087,
  100128,
  100154,
  100328,
  100392
 ]
}
```

### `missing_values.customer_id`: No NULLs in required column customer_id

```json
{
 "null_pct": 6.15
}
```

### `value_match.revenue`: revenue matches source for matched order_ids

```json
{
 "rows_compared": 1960,
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

### `value_match.status`: status matches source for matched order_ids

```json
{
 "rows_compared": 1960,
 "null_in_target": 0,
 "sample": [
  {
   "order_id": 100003,
   "status_src": "delivered",
   "status_tgt": "DELIVERED"
  },
  {
   "order_id": 100110,
   "status_src": "shipped",
   "status_tgt": "SHIPPED"
  },
  {
   "order_id": 100130,
   "status_src": "delivered",
   "status_tgt": "DELIVERED"
  },
  {
   "order_id": 100143,
   "status_src": "shipped",
   "status_tgt": "SHIPPED"
  },
  {
   "order_id": 100176,
   "status_src": "placed",
   "status_tgt": "PLACED"
  }
 ]
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

### `rule.allowed_status`: status in allowed set

```json
{
 "rule": "status in allowed set",
 "sample": [
  {
   "order_id": 100003,
   "customer_id": 393.0,
   "order_date": "2026-09-12",
   "currency": "INR",
   "quantity": 3,
   "unit_price": 154.52,
   "discount": 0.0,
   "revenue": 463.56,
   "status": "DELIVERED"
  },
  {
   "order_id": 100110,
   "customer_id": 423.0,
   "order_date": "2026-09-09",
   "currency": "USD",
   "quantity": 8,
   "unit_price": 169.25,
   "discount": 0.15,
   "revenue": 1150.9,
   "status": "SHIPPED"
  },
  {
   "order_id": 100130,
   "customer_id": 381.0,
   "order_date": "2026-09-10",
   "currency": "USD",
   "quantity": 2,
   "unit_price": 288.38,
   "discount": 0.05,
   "revenue": 547.92,
   "status": "DELIVERED"
  },
  {
   "order_id": 100143,
   "customer_id": 166.0,
   "order_date": "2026-09-29",
   "currency": "EUR",
   "quantity": 4,
   "unit_price": 89.26,
   "discount": 0.1,
   "revenue": 347.05,
   "status": "SHIPPED"
  },
  {
   "order_id": 100176,
   "customer_id": 277.0,
   "order_date": "2026-09-23",
   "currency": "EUR",
   "quantity": 6,
   "unit_price": 315.33,
   "discount": 0.05,
   "revenue": 1941.17,
   "status": "PLACED"
  }
 ],
 "unexpected_values": {
  "DELIVERED": 28,
  "SHIPPED": 18,
  "PLACED": 14
 }
}
```


## Root cause analysis (offline heuristic baseline)

Heuristic analysis matched 4 known failure patterns.

### 1. Duplicate rows from non-idempotent load  ·  confidence: high

Explains: `duplicates.order_id`

**Facts (from evidence)**

- 25 duplicate key rows in target  _[duplicates.order_id]_
- Context mentions a retried load  _[changelog.md]_
- Load mode is APPEND  _[etl_transform.sql]_
- Load mode is APPEND  _[metadata.json]_
- Source keys are unique, so duplicates were introduced by the load  _[duplicates.order_id.source]_

**Likely root cause (hypothesis):** A load was re-run in append mode, inserting part of a batch twice.

**Assumptions**

- The retry is the only re-run in the window

**Recommended next steps**

1. Count duplicates by load batch/ingestion timestamp
2. Switch the load to MERGE on the primary key
3. Deduplicate the affected partition

### 2. Source rows dropped by transform  ·  confidence: high

Explains: `keys_missing_in_target`, `record_count`

**Facts (from evidence)**

- 40 source keys absent from target  _[keys_missing_in_target]_
- All missing rows have quantity between -3 and -1  _[keys_missing_in_target]_
- Transform filters on quantity > 0  _[etl_transform.sql]_
- Net row difference -15 = -40 dropped + 25 duplicates  _[record_count]_

**Likely root cause (hypothesis):** The filter `quantity > 0` in the transform removes these rows.

**Assumptions**

- The dropped rows are valid business records (e.g. refunds)

**Recommended next steps**

1. Confirm with the data owner whether these rows should be excluded
2. If not, remove or narrow the filter and backfill

### 3. NULL customer_id in target  ·  confidence: high

Explains: `missing_values.customer_id`

**Facts (from evidence)**

- 122 NULL customer_id values in target  _[missing_values.customer_id]_
- customer_id is taken from a LEFT JOIN to warehouse.dim_customer  _[etl_transform.sql]_
- Context records a change to dim_customer  _[changelog.md]_
- Context records a change to dim_customer  _[metadata.json]_

**Likely root cause (hypothesis):** A key change in dim_customer breaks the join, so unmatched rows get NULL customer_id.

**Assumptions**

- Missing values are not present upstream

**Recommended next steps**

1. Query unmatched customer_id values against the dimension
2. Update the join to the new key format or add a mapping table

### 4. revenue mismatch  ·  confidence: high

Explains: `value_match.revenue`, `rule.revenue_formula`

**Facts (from evidence)**

- 474 rows differ; target/source ratio median 1.08 (range 1.0799–1.0801)  _[value_match.revenue]_
- All mismatched rows have currency = EUR  _[value_match.revenue]_
- Transform has special handling when currency = 'EUR'  _[etl_transform.sql]_

**Likely root cause (hypothesis):** The transform converts revenue for EUR rows, but source revenue is already converted (double conversion).

**Assumptions**

- The rate used equals the observed ratio

**Recommended next steps**

1. Compare revenue for a few EUR orders at each pipeline stage
2. Remove the duplicate conversion and reprocess affected dates

### Not explained by the analysis

These checks failed but no finding explains them. Investigate manually:

- `rule.allowed_status`
- `value_match.status`
