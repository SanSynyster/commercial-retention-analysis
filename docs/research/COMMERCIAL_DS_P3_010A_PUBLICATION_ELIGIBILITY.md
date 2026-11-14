# P3-010A — Public Release Eligibility

**Assessment date:** 14 November 2026
**Repository revision reviewed:** `fb69d67b29f1c2eb1e56d635f43229d77ff36c1b`

## Decision summary

The six committed application bundles are small aggregate JSON products. Five are derived from UCI Online Retail II (with Online Retail V1 also used to correct the documented overlap); the sixth contains aggregate Hillstrom experiment research findings. No bundle contains customer-level rows, customer identifiers, row-level predictions, assignment records, or private absolute paths.

The UCI source pages explicitly identify CC BY 4.0, which permits sharing and adaptation with attribution and the other licence conditions. The Hillstrom challenge page makes the source CSV publicly downloadable and expressly invites analysis and sharing findings, but the reviewed evidence does not provide an explicit dataset licence or blanket permission to redistribute that CSV. Accordingly, do not include the raw Hillstrom dataset. The causal bundle can be considered for release as original, non-identifying aggregate research findings with direct attribution to the challenge, with that rationale clearly distinguished from a formal dataset licence.

This is an evidence-based release assessment, not legal advice. “Eligible” below applies to the described application bundle, not to redistribution of the underlying row-level source datasets.

## Bundle inventory and recommendation

Content hashes below are the canonical `content_sha256` values validated against each bundle’s canonical content. File sizes are the committed JSON sizes.

| Committed bundle | Size | Content SHA-256 | Source evidence | Publication recommendation |
|---|---:|---|---|---|
| `app_data/customer_overview_v1.json` | 207,917 B | `5bd05077dd03d8a053150c752bd9610431c96b35e5b269b045eebf065d006c4c` | Corrected V2 Online Retail II aggregates; V1 Online Retail is also an input to the documented overlap correction. Provenance and input hashes are in `docs/DATA_PROVENANCE.md`. | **Eligible for publication with documented attribution.** Attribute both UCI datasets and disclose the correction/transformation. |
| `app_data/propensity_summary_v1.json` | 14,190 B | `a4fcc6d60cac7ddc2de3a5c62c457c9f706237792b42b1bdffa1715d09535562` | Corrected V2 Online Retail II aggregate research; provenance records the M1/M2 aggregate sources and source dataset hashes. | **Eligible for publication with documented attribution.** |
| `app_data/p3_predictive_v1.json` | 33,426 B | `40dba007ed5c76ba595413ecdf3ab7f0e24245f13a11d7de9d23a6f8fe57ddfd` | P3 predictive aggregates derived from corrected V2 Online Retail II M2 snapshots; bundle provenance names the relative source reports/files and dataset hash. | **Eligible for publication with documented attribution.** |
| `app_data/p3_segmentation_v1.json` | 18,168 B | `590328678dcb144d94d5d8c54a79d767f0590a22554e9e4bd9dabbbad3f522a8` | P3-007 aggregate outputs derived from corrected V2 Online Retail II; explicit source mapping and manifest are recorded in the segmentation integration provenance. | **Eligible for publication with documented attribution.** |
| `app_data/targeting_v1.json` | 14,276 B | `44bcf66762056a8746333239e731e6d79809d2a0a29904924dd9b8c858a7c6f9` | P2 M3 retrospective targeting aggregates based on corrected V2 Online Retail II M2 snapshot data; no individual predictions are bundled. | **Eligible for publication with documented attribution.** |
| `app_data/p3_causal_v1.json` | 11,022 B | `720a35d13c1de8d5f6db62bacf64bf7945b072a606c3b5ec19d5ea5015c2da4b` | P3-008A design aggregates, P3-008B development aggregates from `p3_008b_outputs`, P3-008C locked-test aggregate JSON, and documented P3-008D synthesis. The private Hillstrom source CSV is not bundled. | **Eligible for publication with documented attribution, limited to original aggregate findings.** Do not redistribute Hillstrom source data. If release policy requires an explicit dataset licence for every cited source, obtain written clarification before publishing this page. |

All six bundles use schema version 1 and their committed content hashes validated. Application code’s MIT licence is separate from rights in third-party datasets; it does not grant rights to those datasets.

## UCI Online Retail licensing and attribution

### Verified licence text

The [UCI Online Retail II page](https://archive.ics.uci.edu/dataset/502/online%2Bretail%2Bii) identifies the dataset as CC BY 4.0 and gives the citation Chen, D. (2012), *Online Retail II*, UCI Machine Learning Repository, DOI [10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D). The [UCI Online Retail page](https://archive.ics.uci.edu/dataset/352/online-retail) likewise identifies CC BY 4.0 and cites Chen, D. (2015), *Online Retail*, DOI [10.24432/C5BW33](https://doi.org/10.24432/C5BW33).

The [CC BY 4.0 deed](https://creativecommons.org/licenses/by/4.0/) and [legal code](https://creativecommons.org/licenses/by/4.0/legalcode) permit sharing and adaptation, including commercial use, subject to attribution, a licence link, indication of changes, and no suggestion of endorsement. The licence applies only to rights the licensor can grant; other rights may still apply.

The repository’s `docs/DATA_PROVENANCE.md` records the UCI datasets under CC BY 4.0, their source hashes, and the overlap-correction process. It describes a corrected V2 Online Retail II dataset created by removing the reviewed 22,523-row overlap block, using V1 Online Retail as a comparison/input. It also records that the exact XLSX-to-CSV conversion command was not preserved. Public release notes should disclose the corrected-V2 transformation and avoid implying that UCI or the retailer endorses this application.

### Suggested attribution

> Online Retail II, Chen, D. (2012), UCI Machine Learning Repository, DOI: [10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D), and Online Retail, Chen, D. (2015), UCI Machine Learning Repository, DOI: [10.24432/C5BW33](https://doi.org/10.24432/C5BW33). Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). This application uses aggregate analyses of a corrected V2 Online Retail II dataset; the documented overlap correction and other transformations are described in the project provenance documentation. UCI and the original data contributors do not endorse this application.

For an artifact using Online Retail II only, the Online Retail V1 citation may be omitted if its use in the correction process is not relevant to that artifact’s provenance; for a general application notice, retaining both citations is clearer.

## Hillstrom evidence and rights distinction

| Question | Verified evidence | Assessment |
|---|---|---|
| Is the source publicly available? | Kevin Hillstrom’s [2008 MineThatData challenge page](https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html) directly links the CSV and describes the 64,000-row, three-arm experiment and two-week outcomes. | **Yes, public access is evidenced.** Public download availability alone does not establish a redistribution licence. |
| Is redistribution of the source CSV permitted? | The challenge page reviewed provides no explicit dataset licence or blanket redistribution grant. The committed P3-008A report records the same finding. CausalML’s [dataset documentation](https://causalml.readthedocs.io/en/stable/datasets.html) also says it has no license file; this is corroboration, not a rights grant. | **Not verified.** Do not package, mirror, or otherwise redistribute the raw CSV or row-level extracts without permission. |
| May derived aggregate statistics be published? | In the challenge post dated 20 March 2008, Hillstrom asked participants to quantify campaign outcomes, “tell the world” whether the campaign worked, and share findings in comments or a paper. Entries were due by 11:59 p.m. on 30 April 2008. | **The historical post supports sharing findings in that 2008 challenge context.** The contest deadline has passed; this invitation is not an explicit open-data licence, a continuing redistribution grant, or blanket permission for any reuse of the underlying data. |
| May original analytical interpretations be published? | The 20 March 2008 challenge invited papers and public discussion of analyses and targeting suggestions, with responses due 30 April 2008. The P3-008 research reports document original analysis rather than reproducing source records. | **The post evidences an invitation to publish/share original findings as part of the 2008 challenge**, not an explicit dataset licence or perpetual grant. Do not represent it as permission to redistribute source records or imply Hillstrom endorsement. |

The original data’s public availability, the right to redistribute the dataset, the ability to publish derived aggregate results, and authorship of original interpretations are distinct questions. The application bundle contains aggregate statistical evidence, not source rows. Release should cite the MineThatData challenge and state that the underlying dataset is not included. If the intended release expands beyond this analytical challenge context, request written permission or clarification from the rights holder.

## Causal bundle content and privacy inspection

The causal bundle contains only the experiment design arm totals, aggregate arm denominators and event counts, aggregate effect estimates and confidence intervals, Holm-adjusted secondary comparisons, development policy-value summaries, interpretive text, and source provenance. It is approximately 11 KB. Inspection found no 64,000-row table, row-level outcome or prediction, customer identifier, assignment record, split-membership record, customer cross-tabulation, or private absolute source path. These summaries cannot reproduce substantial portions of the original row-level dataset.

Across the six committed bundles, a bounded scan found no customer/row identifier or individual prediction/assignment fields and no absolute private path patterns. The tracked repository contains no raw UCI source files, Hillstrom CSV, row-level Parquet, private split-assignment CSV, or secret-like credential files. The two tracked recovery CSVs are stock-code/taxonomy support tables, not customer records. The application bundles are aggregate outputs; this finding does not itself grant rights to any external source file.

## Release strategy and outstanding decisions

1. Release the five UCI-derived bundles with the attribution above, a link to CC BY 4.0, and a concise notice of the corrected-V2 overlap removal and other material transformations.
2. Release the causal bundle/page as original aggregate research findings only, with a direct citation to the MineThatData challenge and an explicit statement that Hillstrom’s source dataset is not included. Do not include raw data, row-level excerpts, assignment files, or individual predictions.
3. If organizational release policy requires an explicit licence covering every data source even for original aggregate findings, seek written clarification before exposing the causal page. This is the only identified permission question that could justify temporarily withholding a bundle; the least disruptive alternative is to ship the five UCI-backed pages while that question is resolved.
4. In P3-010B, prepare the public release package: add a third-party attribution notice, verify the deployment artifact allowlist excludes local/private source paths and ignored research files, and repeat the tracked-file/privacy scan on the exact release tree. Keep software and dataset licensing notices distinct.

No deployment, publication, push, bundle modification, or research-result change was made as part of this assessment.
