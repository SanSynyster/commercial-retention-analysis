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
        with st.expander("Data Sources & Research Limitations"):
            st.markdown(
                "**UCI Online Retail II.** Chen, D. (2012), [UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/502/online%2Bretail%2Bii), "
                "[DOI 10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). "
                "The historical research uses a corrected dataset with duplicated overlap records removed; UCI and the author do not endorse this application."
            )
            st.markdown(
                "**UCI Online Retail, where used in the overlap correction.** Chen, D. (2015), "
                "[UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/352/online-retail), "
                "[DOI 10.24432/C5BW33](https://doi.org/10.24432/C5BW33), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)."
            )
            st.markdown(
                "**Hillstrom / MineThatData.** [E-Mail Analytics and Data Mining Challenge](https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html). "
                "The causal page reports aggregate results from a separate historical randomised experiment. The source CSV, row-level records, "
                "individual assignments and split files are not distributed. No formal redistribution licence for the source dataset has been established."
            )
            st.markdown(
                "**Research limits.** Historical description and historical prediction use old observational retail data; exploratory modelling is not live inference "
                "and model explanations are not causal. Retrospective targeting measures past purchase capture, not treatment response. Randomised experimental "
                "findings are historical Hillstrom assignment effects and are not assumed to transfer to UCI customers. Hypothetical CRM scenarios are assumptions, "
                "not observed outcomes. This is not a live customer-scoring or campaign-execution system."
            )
    navigation.run()


main()
