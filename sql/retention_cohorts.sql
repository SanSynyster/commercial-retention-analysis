-- Retention cohorts parity query
--
-- Source: data/processed/clean_transactions.parquet
-- Grain: one row per cohort month and month index
-- Purpose: reproduce the retention cohort logic from
-- notebooks/02_retention_analysis.ipynb using DuckDB SQL.
--
-- The notebook writes a pivoted retention_matrix.csv. This SQL keeps the
-- output long-form because it is easier to use in BI tools and dashboards.

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

orders_with_months AS (
    SELECT
        customer_id,
        invoice_no,
        order_date,
        DATE_TRUNC('month', order_date)::DATE AS order_month,
        MIN(DATE_TRUNC('month', order_date)::DATE) OVER (
            PARTITION BY customer_id
        ) AS cohort_month
    FROM customer_orders
),

orders_with_month_index AS (
    SELECT
        customer_id,
        invoice_no,
        order_date,
        order_month,
        cohort_month,
        DATE_DIFF('month', cohort_month, order_month) AS month_index
    FROM orders_with_months
),

cohort_counts AS (
    SELECT
        cohort_month,
        month_index,
        COUNT(DISTINCT customer_id) AS customers
    FROM orders_with_month_index
    GROUP BY
        cohort_month,
        month_index
),

cohort_sizes AS (
    SELECT
        cohort_month,
        customers AS cohort_size
    FROM cohort_counts
    WHERE month_index = 0
)

SELECT
    cohort_counts.cohort_month,
    cohort_counts.month_index,
    cohort_counts.customers,
    cohort_sizes.cohort_size,
    cohort_counts.customers / cohort_sizes.cohort_size AS retention_pct
FROM cohort_counts
INNER JOIN cohort_sizes
    ON cohort_counts.cohort_month = cohort_sizes.cohort_month
ORDER BY
    cohort_counts.cohort_month,
    cohort_counts.month_index;
