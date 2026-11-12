"""Customer Intelligence & Decision Support — Streamlit entry point.

Run from the repository root:  streamlit run app/streamlit_app.py
"""
from __future__ import annotations

from pathlib import Path
import sys

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
for path in (APP_DIR, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from views.customer_overview import render as render_customer_overview  # noqa: E402
from views.purchase_propensity import render as render_purchase_propensity  # noqa: E402
from views.placeholders import (  # noqa: E402
    render_experiment_feasibility,
    render_targeting_explorer,
)

PAGES = [
    st.Page(render_customer_overview, title="Customer Overview", url_path="customer-overview", default=True),
    st.Page(render_purchase_propensity, title="Purchase Propensity", url_path="purchase-propensity"),
    st.Page(render_targeting_explorer, title="Targeting Explorer", url_path="targeting-explorer"),
    st.Page(render_experiment_feasibility, title="Experiment Feasibility", url_path="experiment-feasibility"),
]


def main() -> None:
    st.set_page_config(page_title="Customer Intelligence & Decision Support", layout="wide")
    navigation = st.navigation(PAGES)
    with st.sidebar:
        st.caption(
            "Research exhibit built on aggregate results from the corrected UCI Online Retail II analysis. "
            "No customer-level data is loaded."
        )
    navigation.run()


main()
