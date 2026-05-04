```python
import pandas as pd
from pathlib import Path

PROCESSED_DIR = Path("../data/processed")

df = pd.read_parquet(PROCESSED_DIR / "clean_transactions.parquet")

df = df[df["is_valid_order_line"]].copy()
```


```python
df.columns
```




    Index(['InvoiceNo', 'StockCode', 'Description', 'Quantity', 'InvoiceDate',
           'UnitPrice', 'CustomerID', 'Country', 'line_revenue_gross',
           'is_cancelled_invoice', 'is_refund_or_return', 'is_positive_purchase',
           'is_identified_customer', 'exclusion_reason', 'is_valid_order_line',
           'analytical_revenue'],
          dtype='str')




```python
df = pd.read_parquet(PROCESSED_DIR / "clean_transactions.parquet")

df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace(" ", "_")
)

df.head()
```




<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>invoiceno</th>
      <th>stockcode</th>
      <th>description</th>
      <th>quantity</th>
      <th>invoicedate</th>
      <th>unitprice</th>
      <th>customerid</th>
      <th>country</th>
      <th>line_revenue_gross</th>
      <th>is_cancelled_invoice</th>
      <th>is_refund_or_return</th>
      <th>is_positive_purchase</th>
      <th>is_identified_customer</th>
      <th>exclusion_reason</th>
      <th>is_valid_order_line</th>
      <th>analytical_revenue</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>536365</td>
      <td>85123A</td>
      <td>WHITE HANGING HEART T-LIGHT HOLDER</td>
      <td>6</td>
      <td>2010-12-01 08:26:00</td>
      <td>2.55</td>
      <td>17850</td>
      <td>United Kingdom</td>
      <td>15.30</td>
      <td>False</td>
      <td>False</td>
      <td>True</td>
      <td>True</td>
      <td>&lt;NA&gt;</td>
      <td>True</td>
      <td>15.30</td>
    </tr>
    <tr>
      <th>1</th>
      <td>536365</td>
      <td>71053</td>
      <td>WHITE METAL LANTERN</td>
      <td>6</td>
      <td>2010-12-01 08:26:00</td>
      <td>3.39</td>
      <td>17850</td>
      <td>United Kingdom</td>
      <td>20.34</td>
      <td>False</td>
      <td>False</td>
      <td>True</td>
      <td>True</td>
      <td>&lt;NA&gt;</td>
      <td>True</td>
      <td>20.34</td>
    </tr>
    <tr>
      <th>2</th>
      <td>536365</td>
      <td>84406B</td>
      <td>CREAM CUPID HEARTS COAT HANGER</td>
      <td>8</td>
      <td>2010-12-01 08:26:00</td>
      <td>2.75</td>
      <td>17850</td>
      <td>United Kingdom</td>
      <td>22.00</td>
      <td>False</td>
      <td>False</td>
      <td>True</td>
      <td>True</td>
      <td>&lt;NA&gt;</td>
      <td>True</td>
      <td>22.00</td>
    </tr>
    <tr>
      <th>3</th>
      <td>536365</td>
      <td>84029G</td>
      <td>KNITTED UNION FLAG HOT WATER BOTTLE</td>
      <td>6</td>
      <td>2010-12-01 08:26:00</td>
      <td>3.39</td>
      <td>17850</td>
      <td>United Kingdom</td>
      <td>20.34</td>
      <td>False</td>
      <td>False</td>
      <td>True</td>
      <td>True</td>
      <td>&lt;NA&gt;</td>
      <td>True</td>
      <td>20.34</td>
    </tr>
    <tr>
      <th>4</th>
      <td>536365</td>
      <td>84029E</td>
      <td>RED WOOLLY HOTTIE WHITE HEART.</td>
      <td>6</td>
      <td>2010-12-01 08:26:00</td>
      <td>3.39</td>
      <td>17850</td>
      <td>United Kingdom</td>
      <td>20.34</td>
      <td>False</td>
      <td>False</td>
      <td>True</td>
      <td>True</td>
      <td>&lt;NA&gt;</td>
      <td>True</td>
      <td>20.34</td>
    </tr>
  </tbody>
</table>
</div>




```python
print(df.columns.tolist())
print(customer_orders.columns.tolist())
```


```python
df = df.rename(columns={

    "invoiceno": "invoice_no",

    "stockcode": "stock_code",

    "invoicedate": "invoice_date",

    "unitprice": "unit_price",

    "customerid": "customer_id"

})

df.columns.tolist()
```




    ['invoice_no',
     'stock_code',
     'description',
     'quantity',
     'invoice_date',
     'unit_price',
     'customer_id',
     'country',
     'line_revenue_gross',
     'is_cancelled_invoice',
     'is_refund_or_return',
     'is_positive_purchase',
     'is_identified_customer',
     'exclusion_reason',
     'is_valid_order_line',
     'analytical_revenue']




```python
df["invoice_date"] = pd.to_datetime(df["invoice_date"])

customer_orders = (
    df.groupby(["customer_id", "invoice_no"])
    .agg(
        order_date=("invoice_date", "min"),
        order_revenue=("analytical_revenue", "sum")
    )
    .reset_index()
)

customer_metrics = (
    customer_orders.groupby("customer_id")
    .agg(
        total_orders=("invoice_no", "nunique"),
        revenue=("order_revenue", "sum"),
        first_purchase=("order_date", "min"),
        last_purchase=("order_date", "max")
    )
    .reset_index()
)

customer_metrics["aov"] = (
    customer_metrics["revenue"] / customer_metrics["total_orders"]
)

customer_metrics["active_days"] = (
    customer_metrics["last_purchase"] - customer_metrics["first_purchase"]
).dt.days

customer_metrics["is_repeat_customer"] = customer_metrics["total_orders"] > 1

customer_metrics.head()
```




<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>customer_id</th>
      <th>total_orders</th>
      <th>revenue</th>
      <th>first_purchase</th>
      <th>last_purchase</th>
      <th>aov</th>
      <th>active_days</th>
      <th>is_repeat_customer</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>12346</td>
      <td>2</td>
      <td>77183.60</td>
      <td>2011-01-18 10:01:00</td>
      <td>2011-01-18 10:17:00</td>
      <td>38591.800000</td>
      <td>0</td>
      <td>True</td>
    </tr>
    <tr>
      <th>1</th>
      <td>12347</td>
      <td>7</td>
      <td>4310.00</td>
      <td>2010-12-07 14:57:00</td>
      <td>2011-12-07 15:52:00</td>
      <td>615.714286</td>
      <td>365</td>
      <td>True</td>
    </tr>
    <tr>
      <th>2</th>
      <td>12348</td>
      <td>4</td>
      <td>1797.24</td>
      <td>2010-12-16 19:09:00</td>
      <td>2011-09-25 13:13:00</td>
      <td>449.310000</td>
      <td>282</td>
      <td>True</td>
    </tr>
    <tr>
      <th>3</th>
      <td>12349</td>
      <td>1</td>
      <td>1757.55</td>
      <td>2011-11-21 09:51:00</td>
      <td>2011-11-21 09:51:00</td>
      <td>1757.550000</td>
      <td>0</td>
      <td>False</td>
    </tr>
    <tr>
      <th>4</th>
      <td>12350</td>
      <td>1</td>
      <td>334.40</td>
      <td>2011-02-02 16:01:00</td>
      <td>2011-02-02 16:01:00</td>
      <td>334.400000</td>
      <td>0</td>
      <td>False</td>
    </tr>
  </tbody>
</table>
</div>




```python
customer_metrics.to_parquet(PROCESSED_DIR / "customer_metrics.parquet", index=False)
```


```python
customer_orders = customer_orders.sort_values(["customer_id", "order_date"])

customer_orders["order_rank"] = (
    customer_orders.groupby("customer_id").cumcount() + 1
)

customer_orders["is_first_order"] = customer_orders["order_rank"] == 1
customer_orders["is_repeat_order"] = customer_orders["order_rank"] > 1

customer_orders.head()
```




<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>customer_id</th>
      <th>invoice_no</th>
      <th>order_date</th>
      <th>order_revenue</th>
      <th>order_rank</th>
      <th>is_first_order</th>
      <th>is_repeat_order</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>12346</td>
      <td>541431</td>
      <td>2011-01-18 10:01:00</td>
      <td>77183.60</td>
      <td>1</td>
      <td>True</td>
      <td>False</td>
    </tr>
    <tr>
      <th>1</th>
      <td>12346</td>
      <td>C541433</td>
      <td>2011-01-18 10:17:00</td>
      <td>0.00</td>
      <td>2</td>
      <td>False</td>
      <td>True</td>
    </tr>
    <tr>
      <th>2</th>
      <td>12347</td>
      <td>537626</td>
      <td>2010-12-07 14:57:00</td>
      <td>711.79</td>
      <td>1</td>
      <td>True</td>
      <td>False</td>
    </tr>
    <tr>
      <th>3</th>
      <td>12347</td>
      <td>542237</td>
      <td>2011-01-26 14:30:00</td>
      <td>475.39</td>
      <td>2</td>
      <td>False</td>
      <td>True</td>
    </tr>
    <tr>
      <th>4</th>
      <td>12347</td>
      <td>549222</td>
      <td>2011-04-07 10:43:00</td>
      <td>636.25</td>
      <td>3</td>
      <td>False</td>
      <td>True</td>
    </tr>
  </tbody>
</table>
</div>




```python
first_order_revenue = customer_orders.loc[
    customer_orders["is_first_order"], "order_revenue"
].sum()

repeat_order_revenue = customer_orders.loc[
    customer_orders["is_repeat_order"], "order_revenue"
].sum()

one_time_customers = customer_metrics.loc[
    ~customer_metrics["is_repeat_customer"], "customer_id"
]

repeat_customers = customer_metrics.loc[
    customer_metrics["is_repeat_customer"], "customer_id"
]

one_time_revenue = customer_orders.loc[
    customer_orders["customer_id"].isin(one_time_customers),
    "order_revenue"
].sum()

repeat_customer_revenue = customer_orders.loc[
    customer_orders["customer_id"].isin(repeat_customers),
    "order_revenue"
].sum()
```


```python
lifecycle = pd.DataFrame({
    "metric": [
        "first_order_revenue",
        "repeat_order_revenue",
        "one_time_customer_revenue",
        "repeat_customer_revenue"
    ],
    "value": [
        first_order_revenue,
        repeat_order_revenue,
        one_time_revenue,
        repeat_customer_revenue
    ]
})

lifecycle.to_csv(PROCESSED_DIR / "customer_lifecycle_revenue_split.csv", index=False)
```


```python
second_orders = customer_orders[customer_orders["order_rank"] == 2]

conversion_rate = len(second_orders) / len(customer_metrics)

days_to_second = (
    second_orders.merge(customer_metrics[["customer_id", "first_purchase"]],
                        on="customer_id")
)

days_to_second["days_to_second"] = (
    days_to_second["order_date"] - days_to_second["first_purchase"]
).dt.days

median_days = days_to_second["days_to_second"].median()

print("Second purchase conversion:", conversion_rate)
print("Median days to second:", median_days)
```


```python
customer_metrics = customer_metrics.sort_values("revenue", ascending=False)

customer_metrics["cum_revenue"] = customer_metrics["revenue"].cumsum()
total_revenue = customer_metrics["revenue"].sum()

customer_metrics["cum_revenue_pct"] = customer_metrics["cum_revenue"] / total_revenue

customer_metrics["decile"] = pd.qcut(
    customer_metrics["revenue"],
    10,
    labels=False,
    duplicates="drop"
)

deciles = (
    customer_metrics.groupby("decile")
    .agg(
        customers=("customer_id", "count"),
        revenue=("revenue", "sum")
    )
    .reset_index()
)

deciles["revenue_pct"] = deciles["revenue"] / total_revenue

deciles.to_csv(PROCESSED_DIR / "customer_revenue_deciles.csv", index=False)
```


```python
customer_orders["order_month"] = customer_orders["order_date"].dt.to_period("M")

first_purchase = (
    customer_orders.groupby("customer_id")["order_month"]
    .min()
    .rename("cohort_month")
)

customer_orders = customer_orders.merge(first_purchase, on="customer_id")

customer_orders["month_index"] = (
    customer_orders["order_month"].astype(int) -
    customer_orders["cohort_month"].astype(int)
)

cohorts = (
    customer_orders.groupby(["cohort_month", "month_index"])
    .agg(customers=("customer_id", "nunique"))
    .reset_index()
)

cohorts.to_csv(PROCESSED_DIR / "retention_matrix.csv", index=False)
```


```python
import os
import sys
from datetime import datetime

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_filename = datetime.now().strftime("notebook_log_%Y%m%d_%H%M%S.txt")
log_path = os.path.join(LOG_DIR, log_filename)

class NotebookLogger:
    def __init__(self, filepath):
        self.terminal = sys.__stdout__
        self.log = open(filepath, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

sys.stdout = NotebookLogger(log_path)
sys.stderr = sys.stdout

print(f"Logging started: {log_path}")
```
