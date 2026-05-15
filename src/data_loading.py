from __future__ import annotations

from pathlib import Path

import pandas as pd


CANONICAL_COLUMNS = {
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
}

COLUMN_ALIASES = {
    "Invoice": "InvoiceNo",
    "Price": "UnitPrice",
    "Customer ID": "CustomerID",
}


def load_raw_transactions(raw_path: str | Path) -> pd.DataFrame:
    """Load a supported raw retail dataset and return canonical source columns."""

    path = Path(raw_path)
    if not path.exists():
        raise FileNotFoundError(f"Raw source file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        transactions = pd.read_excel(path)
    elif suffix == ".csv":
        transactions = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported raw file extension: {path.suffix}")

    transactions = transactions.rename(
        columns={source: target for source, target in COLUMN_ALIASES.items() if source in transactions.columns}
    )
    validate_raw_schema(transactions)
    return transactions


def validate_raw_schema(transactions: pd.DataFrame) -> None:
    """Validate the raw dataset contains the canonical source columns."""

    missing_columns = sorted(CANONICAL_COLUMNS - set(transactions.columns))
    if missing_columns:
        raise ValueError(f"Raw file is missing required columns: {missing_columns}")
