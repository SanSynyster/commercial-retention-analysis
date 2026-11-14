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

from page_registry import PAGES  # noqa: E402


def main() -> None:
    st.set_page_config(page_title="Customer Intelligence & Decision Support", layout="wide")
    navigation = st.navigation(PAGES)
    with st.sidebar:
        st.caption(
            "Research exhibit built on aggregate results from corrected UCI Online Retail II analysis and the separate Hillstrom randomised experiment. "
            "No customer-level data is loaded."
        )
    navigation.run()


main()
