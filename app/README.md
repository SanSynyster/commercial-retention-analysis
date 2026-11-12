# Customer Intelligence & Decision Support (local Streamlit app)

A four-page research exhibit. In this version only **Customer Overview** is implemented; the other pages are placeholders.

## Run

From the repository root (Python 3.11):

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-app.txt
.venv/bin/streamlit run app/streamlit_app.py
```

The app reads only the tracked aggregate bundle `app_data/customer_overview_v1.json`. It needs no raw UCI files, `data/processed/` outputs or customer-level data. If the bundle is missing or fails validation, the page shows an error instead of figures.

## Tests

```sh
.venv/bin/python -m unittest tests.test_customer_overview_bundle tests.test_dashboard_app -v
```

## Rebuilding the bundle (one-time research step, maintainers only)

This step needs the accepted corrected-V2 aggregate outputs in the ignored `data/processed/corrected_v2_customer_analytics/` directory. It is not part of normal app use.

```sh
.venv/bin/python src/customer_overview_bundle.py --output app_data/customer_overview_v1.json
```

Before writing, the builder re-applies the accepted 007D contract checks. It keeps only allowlisted aggregate fields and records source hashes and a content hash. The four small post-entry cohort cells are null in this dashboard as a display convention only; they are recoverable from the already tracked accepted corrected-V2 Figure 2 SVG, so this is not a disclosure guarantee.

The loader checks the data-section hash against an independently pinned approved application-bundle hash. This detects changes relative to that approved bundle; it is not a cryptographic authenticity guarantee if both the bundle and application source are changed.
