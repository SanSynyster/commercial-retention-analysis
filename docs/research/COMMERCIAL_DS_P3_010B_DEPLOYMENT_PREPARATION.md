# P3-010B — Streamlit Deployment Preparation

**Repository revision reviewed:** `fb69d67b29f1c2eb1e56d635f43229d77ff36c1b`
**Status:** technically prepared for a Community Cloud deployment review; not deployed or published.

## Deployment dependencies and configuration

The application uses Python 3.11, matching `.python-version`. Its direct runtime dependencies are pinned in [`app/requirements.txt`](../../app/requirements.txt):

| Dependency | Version |
|---|---:|
| Streamlit | 1.66.1 |
| Altair | 6.3.0 |
| pandas | 3.0.2 |

The runtime imports Streamlit, Altair and pandas directly. Streamlit brings its required runtime dependencies, including NumPy and PyArrow. Research packages such as scikit-learn, XGBoost, LightGBM, SHAP and PySpark are not direct app dependencies. `requirements-app.txt` points local app installs to the same lean dependency file. The repository's root `requirements.txt` remains the broader research environment.

The app dependency file is beside `app/streamlit_app.py`, which is the location Community Cloud checks before the repository root. Select that entrypoint and Python 3.11 when configuring Community Cloud. The root `.streamlit/config.toml` sets headless operation, disables usage statistics and leaves CORS/XSRF protections enabled. It does not set a host address, hardcode a secret, or override the default server port; local Streamlit uses its normal port and the hosted runtime controls its process binding.

This follows Streamlit's current [Community Cloud dependency-file guidance](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies), [entrypoint/configuration layout](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization), [Python selection guidance](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), and [configuration reference](https://docs.streamlit.io/develop/api-reference/configuration/config.toml). Community Cloud is suitable for this app: it is a standard Streamlit multipage app with local aggregate JSON assets and no external service dependency.

## Bundle compatibility and boundaries

All six repository-relative bundles load through their validated loaders. Their content hashes remain unchanged:

| Bundle | Content SHA-256 |
|---|---|
| `customer_overview_v1.json` | `5bd05077dd03d8a053150c752bd9610431c96b35e5b269b045eebf065d006c4c` |
| `propensity_summary_v1.json` | `a4fcc6d60cac7ddc2de3a5c62c457c9f706237792b42b1bdffa1715d09535562` |
| `p3_predictive_v1.json` | `40dba007ed5c76ba595413ecdf3ab7f0e24245f13a11d7de9d23a6f8fe57ddfd` |
| `p3_segmentation_v1.json` | `590328678dcb144d94d5d8c54a79d767f0590a22554e9e4bd9dabbbad3f522a8` |
| `p3_causal_v1.json` | `720a35d13c1de8d5f6db62bacf64bf7945b072a606c3b5ec19d5ea5015c2da4b` |
| `targeting_v1.json` | `44bcf66762056a8746333239e731e6d79809d2a0a29904924dd9b8c858a7c6f9` |

The app uses no private source dataset, local research output directory, model training, or model inference at startup. Runtime pages load only committed aggregate bundles and calculate the documented hypothetical feasibility scenarios. A privacy scan of bundle JSON found no identifier, row-level prediction, assignment, split membership, secret, or absolute private path material. Research builders and their optional private input trees are not required to launch the app.

UCI-derived bundles require CC BY 4.0 attribution and an indication of the corrected-V2 transformation; attribution details are recorded in [`docs/DATA_PROVENANCE.md`](../DATA_PROVENANCE.md) and the [P3-010A publication eligibility assessment](COMMERCIAL_DS_P3_010A_PUBLICATION_ELIGIBILITY.md). The Hillstrom causal bundle contains original aggregate findings only. The underlying CSV is not included. Its public availability and invitation to share findings do not establish permission to redistribute the source dataset. P3-010A recommends attributing the challenge for aggregate findings while keeping the source CSV out of the release. This technical preparation does not itself resolve or grant publication permission.

## Local verification

Verification performed against the existing Python 3.11.14 app environment:

- In a newly created Python 3.11 virtual environment, installation from `app/requirements.txt` completed; `pip check` reported no broken requirements.
- Direct runtime package versions matched the pins above.
- The focused application suite ran 80 tests successfully with 1 expected skip for unavailable private rebuild inputs.
- An AppTest in the clean deployment environment rendered Customer Overview and confirmed all seven pages were registered.
- App import and rendering checks showed all seven registered pages; all committed bundles loaded through their validation paths.
- Bundle content hashes above were checked without rebuilding any research output.
- Startup/page tests used committed bundles, with no private research inputs or model fitting.
- The source/artifact scan found no tracked raw retail or Hillstrom source data, customer-level research rows, assignment files, row-level predictions, or secrets.
- The local Streamlit server started in headless mode; `/_stcore/health` returned `ok` and `/` returned HTTP 200.

Compilation and `git diff --check` passed. A clean hosted build and Community Cloud health check remain outstanding because this task does not deploy the app.

## Publication decision still outstanding

Technical deployment readiness is separate from publication eligibility. The UCI source datasets have explicit CC BY 4.0 terms and require documented attribution and transformation notices. For Hillstrom, P3-010A found a public download and an express invitation to share findings, but no explicit source-dataset licence or blanket redistribution grant. The causal aggregate bundle is recommended for consideration as original findings with attribution; the raw dataset must remain excluded. If the release owner requires formal rights confirmation even for aggregate interpretations, obtain it or temporarily omit the causal page/bundle. No permission is inferred or granted by this report.

## Remaining steps for P3-010C

1. Have the release owner resolve and record whether the documented Hillstrom challenge invitation is sufficient for publishing the aggregate-only causal page; seek rights-holder clarification if required by policy.
2. Finalise the public-facing attribution/third-party notice for UCI and MineThatData, including transformation disclosures and no-endorsement language.
3. Review the exact release branch and deployment artifact allowlist for ignored source data, credentials, private paths and research-only files; repeat the privacy scan on that exact tree.
4. Configure the Community Cloud repository/branch, `app/streamlit_app.py` entrypoint and Python 3.11, then deploy and smoke-test only after publication eligibility is resolved.

No research results or bundles were modified, and no deployment, publication, push, or commit was performed.
