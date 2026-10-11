# Pipeline change log

## 2026-09-18 — transform_orders v2.3 (PR #881)
- Added FX normalisation: EUR revenue converted to USD using reference.fx_rates.
- Added filter `quantity > 0` to exclude invalid quantities.

## 2026-09-15 — DIM-412: dim_customer key migration
- dim_customer.customer_id moving from INTEGER to STRING with `C-` prefix (e.g. `C-1042`).
- Migration runs in waves; about 6% of customers migrated so far.
- Downstream joins to be updated "in a follow-up".

## 2026-09-22 — Incident INC-2291
- load_fact_orders timed out at 02:14 and was automatically retried by the scheduler.
- Retry completed successfully. No further action taken.

## Contract note (source system)
- Source `revenue` is ALREADY reported in USD for all currencies since 2026-01 (see data contract v4).
