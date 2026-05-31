{{ config(materialized='view') }}

with source as (
    select *
    from read_parquet('{{ var("clean_transactions_path") }}')
)

select
    cast(InvoiceNo as varchar) as invoice_no,
    cast(StockCode as varchar) as stock_code,
    cast(Description as varchar) as description,
    cast(Quantity as integer) as quantity,
    cast(InvoiceDate as timestamp) as invoice_date,
    cast(UnitPrice as double) as unit_price,
    cast(CustomerID as bigint) as customer_id,
    cast(Country as varchar) as country,
    cast(line_revenue_gross as double) as line_revenue_gross,
    cast(is_cancelled_invoice as boolean) as is_cancelled_invoice,
    cast(is_refund_or_return as boolean) as is_refund_or_return,
    cast(is_positive_purchase as boolean) as is_positive_purchase,
    cast(is_identified_customer as boolean) as is_identified_customer,
    cast(exclusion_reason as varchar) as exclusion_reason,
    cast(is_valid_order_line as boolean) as is_valid_order_line,
    cast(analytical_revenue as double) as analytical_revenue
from source
