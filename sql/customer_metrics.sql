-- Customer metrics parity query
--
-- Source: data/processed/clean_transactions.parquet
-- Grain: one row per identifiable customer with at least one valid order
-- Purpose: reproduce the customer_metrics.parquet output from
-- notebooks/02_retention_analysis.ipynb using DuckDB SQL.

WITH valid_order_lines AS (
    SELECT
        CAST(CustomerID AS BIGINT) AS customer_id,
        CAST(InvoiceNo AS VARCHAR) AS invoice_no,
        CAST(InvoiceDate AS TIMESTAMP) AS invoice_date,
        CAST(analytical_revenue AS DOUBLE) AS analytical_revenue
    FROM read_parquet('data/processed/clean_transactions.parquet')
    WHERE is_valid_order_line = TRUE
),

customer_orders AS (
    SELECT
        customer_id,
        invoice_no,
        MIN(invoice_date) AS order_date,
        SUM(analytical_revenue) AS order_revenue
    FROM valid_order_lines
    GROUP BY
        customer_id,
        invoice_no
    HAVING SUM(analytical_revenue) > 0
),

customer_metrics AS (
    SELECT
        customer_id,
        COUNT(DISTINCT invoice_no) AS total_orders,
        SUM(order_revenue) AS revenue,
        MIN(order_date) AS first_purchase,
        MAX(order_date) AS last_purchase
    FROM customer_orders
    GROUP BY customer_id
)

SELECT
    customer_id,
    total_orders,
    revenue,
    first_purchase,
    last_purchase,
    revenue / total_orders AS aov,
    DATE_DIFF('day', first_purchase, last_purchase) AS active_days,
    total_orders > 1 AS is_repeat_customer
FROM customer_metrics
ORDER BY customer_id;
