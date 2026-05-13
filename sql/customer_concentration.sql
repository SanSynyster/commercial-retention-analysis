-- Customer concentration parity query
--
-- Source: data/processed/clean_transactions.parquet
-- Grain: one row per revenue-ranked customer decile
-- Purpose: reproduce customer_revenue_deciles.csv from
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
        SUM(order_revenue) AS revenue
    FROM customer_orders
    GROUP BY customer_id
),

ranked_customers AS (
    SELECT
        customer_id,
        revenue,
        ROW_NUMBER() OVER (ORDER BY revenue DESC, customer_id) AS rank,
        COUNT(*) OVER () AS total_customers,
        SUM(revenue) OVER () AS total_revenue
    FROM customer_metrics
),

customer_deciles AS (
    SELECT
        customer_id,
        revenue,
        total_customers,
        total_revenue,
        CASE
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.1) THEN 'Top 10%'
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.2) THEN '10-20%'
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.3) THEN '20-30%'
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.4) THEN '30-40%'
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.5) THEN '40-50%'
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.6) THEN '50-60%'
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.7) THEN '60-70%'
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.8) THEN '70-80%'
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.9) THEN '80-90%'
            ELSE 'Bottom 10%'
        END AS customer_decile,
        CASE
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.1) THEN 1
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.2) THEN 2
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.3) THEN 3
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.4) THEN 4
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.5) THEN 5
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.6) THEN 6
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.7) THEN 7
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.8) THEN 8
            WHEN rank <= FLOOR(1 + (total_customers - 1) * 0.9) THEN 9
            ELSE 10
        END AS decile_sort
    FROM ranked_customers
)

SELECT
    customer_decile,
    COUNT(*) AS customers,
    SUM(revenue) AS revenue,
    COUNT(*) / MAX(total_customers) AS customer_pct,
    SUM(revenue) / MAX(total_revenue) AS revenue_pct
FROM customer_deciles
GROUP BY
    decile_sort,
    customer_decile
ORDER BY decile_sort;
