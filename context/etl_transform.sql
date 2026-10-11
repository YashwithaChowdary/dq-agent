-- transform_orders.sql  (version 2.3, deployed 2026-09-18)
-- Loads staged orders into warehouse.fact_orders

INSERT INTO warehouse.fact_orders            -- load mode: APPEND (see load_config.yaml)
SELECT
    o.order_id,
    c.customer_id,                            -- taken from dimension, not from staging
    o.order_date,
    o.currency,
    o.quantity,
    o.unit_price,
    o.discount,
    CASE
        WHEN o.currency = 'EUR' THEN ROUND(o.revenue * fx.eur_usd_rate, 2)   -- added in v2.3
        ELSE o.revenue
    END AS revenue,
    o.status
FROM staging.orders o
LEFT JOIN warehouse.dim_customer c
       ON c.customer_id = o.customer_id       -- dim key type changed in DIM-412
CROSS JOIN reference.fx_rates fx
WHERE o.quantity > 0;                         -- added in v2.3: "exclude invalid quantities"
