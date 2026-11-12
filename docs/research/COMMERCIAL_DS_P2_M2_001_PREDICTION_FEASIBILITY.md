# M2-001 — Next Prediction Problem Feasibility

## Recommendation

**Direction A, established-customer monthly snapshots, is better supported by the existing data.** A candidate 365-day-active / 90-day-forward snapshot design yields 42,850 mature customer-month observations across ten anchors, including 21,243 labels available for a July 1, 2011 training cutoff and 12,964 later mature test observations. These are repeated observations on customers, not independent rows; the split includes substantial customer overlap and only three test months.

Direction B can add a few mechanically valid first-basket summaries, but its population and temporal support remain exactly the M1-009 size (304 training; 208 test). It cannot resolve the small-sample or seasonal-shift limitations, and the approved transaction taxonomy does not provide product categories. The prior M1-009 result remains unchanged and is not retested here.

## Source and contract coverage

The verified corrected V2 source covers `2009-12-01` through the partial final date `2011-12-09 12:50:00`. Its manifest records corrected V2 SHA-256 `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9`, V1 SHA-256 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`, and the canonical taxonomy seed hash. The corrected source has 1,044,848 rows, 788,127 qualifying merchandise lines, 36,594 customer × invoice qualifying occasions, and 5,852 identifiable customers. Counts in this report were derived in memory through `docs/recovery/COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py` (`load_validated_purchase_input`, `build_purchase_occasions`); no source data or customer-level output was written.

The controlling definitions are recorded in `docs/recovery/COMMERCIAL_DS_001_DECISION_LOG.md` §3A and `docs/recovery/COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md`: corrected V2 and the line taxonomy; customer × invoice occasion; same-day invoices collapse to one date-level purchase day for primary repeat outcomes; trailing 365-day activity is eligible only with a complete look-back; features are strictly before anchor `T`; future windows are half-open; and immature no-event observations are not negatives. `docs/recovery/COMMERCIAL_DS_001_DATA_CONTRACTS.md` describes C-SNAP, C-ACTIVE, C-LAPSE and C-VALUE-F. Existing `src/customer_metrics.py` aggregates whole observed customer histories and should not be applied directly to point-in-time snapshots without first restricting source rows to `< T`.

The source has no independent system-uptime calendar. No inactivity is inferred outside the documented source interval. The approved UCI coverage itself is contiguous after the corrected overlap treatment, but historical behavior before source start remains unobserved.

## Direction A — Established-customer prediction

### Candidate question and population

At each month-start anchor `T`, predict whether a currently active customer makes at least one additional qualifying purchase in `[T, T + 90 days)`. Define the eligible population as identifiable customers with at least one qualifying purchase day in the complete trailing window `[T − 365 days, T)`. This is a customer-base snapshot, not an acquisition cohort; it does not require the 12-month acquisition proxy or claim that a customer is new.

For feasibility counts, positives are customers with at least one canonical qualifying purchase day in the forward 90-day interval. Mature negatives have no such day and the full interval is covered. Any observed event before the source ends can establish a positive in a partially observed interval; otherwise the label is unknown. The primary comparison below uses fully mature rows only. This positive orientation is the complement of the proposed `no_purchase_next_90d` / C-LAPSE outcome; the owner should select the formal primary label name and direction before implementation.

### Actual monthly counts and maturity

All ten anchors from December 2010 through September 2011 have complete 90-day follow-up under the existing date-level maturity rule. October and November 2011 anchors have incomplete follow-up and are not assigned negative labels.

| Anchor | Active snapshots | Mature? | Mature positive | Mature negative | If immature: observed positive | Unknown, not negative |
| --- | ---: |:---:| ---: | ---: | ---: | ---: |
| 2010-12 | 4,239 | Yes | 1,407 | 2,832 | — | — |
| 2011-01 | 4,205 | Yes | 1,390 | 2,815 | — | — |
| 2011-02 | 4,221 | Yes | 1,460 | 2,761 | — | — |
| 2011-03 | 4,260 | Yes | 1,571 | 2,689 | — | — |
| 2011-04 | 4,318 | Yes | 1,630 | 2,688 | — | — |
| 2011-05 | 4,319 | Yes | 1,670 | 2,649 | — | — |
| 2011-06 | 4,324 | Yes | 1,584 | 2,740 | — | — |
| 2011-07 | 4,314 | Yes | 1,666 | 2,648 | — | — |
| 2011-08 | 4,326 | Yes | 1,865 | 2,461 | — | — |
| 2011-09 | 4,324 | Yes | 2,142 | 2,182 | — | — |
| 2011-10 | 4,364 | No | — | — | 2,010 | 2,354 |
| 2011-11 | 4,344 | No | — | — | 1,603 | 2,741 |

Across the 12 candidate anchors, `51,558 = 42,850 mature + 8,708 incomplete`. Mature rows reconcile to **16,385 positives + 26,465 negatives**. The incomplete group has 3,613 observed positives and 5,095 unknown outcomes; it contains **no mature negatives**. December 2011 and later anchors are not counted because their forward horizon cannot mature in this source.

### One strict chronological feasibility split

Using the same July 1, 2011 as-of cutoff as a concrete example, training snapshots must have `T < 2011-07-01` and their full label interval available by the cutoff. Test snapshots must have `T ≥ 2011-07-01` and mature follow-up by the source end. May and June anchors are pre-cutoff but their labels were not yet available on July 1; they are excluded from both sets.

| Disposition | Anchors | Snapshot rows | Positive | Negative | Positive prevalence |
| --- | --- | ---: | ---: | ---: | ---: |
| Training labels available at cutoff | Dec-2010–Apr-2011 (5 anchors) | 21,243 | 7,458 | 13,785 | 35.1% |
| Pre-cutoff labels unavailable at cutoff (eventually mature) | May–Jun-2011 (2 anchors) | 8,643 | 3,254* | 5,389* | 37.6%* |
| Mature later test | Jul–Sep-2011 (3 anchors) | 12,964 | 5,673 | 7,291 | 43.8% |

`42,850 mature rows = 21,243 available training + 8,643 unavailable-at-cutoff + 12,964 test.` Asterisks are retrospective label counts only; the May/June labels are not available to a July 1 model. Test prevalence is 8.7 percentage points above training and rises from 38.6% in July to 49.5% in September, so calendar drift remains material.

The panel has repeated customers: the five training anchors contain 4,691 unique customers, the three test anchors 4,551, and **4,018 customers occur in both**. This overlap is operationally natural when scoring an existing base monthly, but row-level uncertainty would be wrong. Evaluation should cluster resampling by customer and report anchor-month results. A customer-disjoint test would answer a different question and reduce support. The available data gives only one short later-season window, not multiple annual cycles or a robust seasonality stress test. A formal power/MDE calculation is not reported: it would require a predeclared minimum useful effect and an effective-sample assumption for repeated, overlapping customer windows. The unique-customer counts are more informative than the 21k/13k row counts, but still do not create independent seasonal origins.

A March 1 cutoff is also technically possible but leaves only the December anchor (4,239 rows; 1,407 positive / 2,832 negative) with labels available for training. An August cutoff adds May to training but narrows the mature test to August–September (8,650 rows). July is the more balanced single split of those examined, though not a substitute for a multi-origin backtest.

### Point-in-time feature support

Features can be computed from qualifying source rows with date `< T`, preferably within the complete trailing 365 days: recency since last qualifying purchase; counts of purchase days and invoices; trailing gross product value and average occasion value; unique StockCode/product diversity; basket quantity/value/diversity summaries; and gaps between observed qualifying purchase days where at least two exist. Keep lifetime totals out of the initial snapshot because source history is left-censored. Existing `src/customer_metrics.py` outputs include whole observed histories; reuse its definitions only after restricting inputs at `T`.

The source taxonomy reliably separates merchandise from returns and non-merchandise, but returns are not linked to original invoices and the approved contract leaves their treatment for later value analysis. Exclude return/cancellation features from the first baseline. Country is present on line records, but a customer-level historical mode/tie rule is proposed rather than fully approved; a first-invoice country can be considered after a stable aggregation contract. Do not include full-history or post-anchor values.

## Direction B — Enriched Day-21 acquisition-proxy prediction

The approved 12-month qualifying-history proxy, first qualifying purchase `t0`, Day-21 decision, and second purchase in `(T_decision, T_decision + 90 days]` remain unchanged. Eligibility and source end are fixed by M1-007; no new exclusions or label changes are considered.

The available sample remains **1,324 Day-21 eligible customers**, of whom **838 have mature labels (312 positive, 526 negative)**. The approved July split remains **304 training (90/214) and 208 test (97/111)**; 326 pre-cutoff labels matured only after the training cutoff, while 486 eligible outcomes have incomplete horizon (168 observed positives and 318 unknown). Adding features cannot enlarge these partitions or remove the observed train/test prevalence shift.

There is some low-dimensional first-basket enrichment potential. In the 1,324 eligible customers, all had qualifying first-day lines; first-day qualifying prices and item codes vary for most customers (1,259 have at least two distinct line prices; 1,270 have at least two StockCodes). First-day country is present for all in this group, with one country per first purchase day; 28 countries occur. Such fields are observable before Day 21 and could support a few predeclared aggregates or a categorical country feature. Existing M1 features already cover first-day gross, quantity and product diversity.

However, the canonical taxonomy is a **transaction-type** taxonomy: all qualifying lines are simply `merchandise`. It does not supply product-category labels. StockCode one-hot encoding or Description-derived categories would be high-dimensional and/or require a new, reviewed product taxonomy; with 304 training customers they are not a sound first enrichment. Unit-price dispersion, first-day occasion mix or basket summaries are computationally possible but correlated with current features and should be kept to a small number. Returns in the 21-day pre-decision period remain unattributed and definition-sensitive. Any feature from the Day 0–21 interval must be cut off at the exact Day-21 timestamp, excluding all subsequent events.

Direction B retains the same three-month test and seasonal shift as M1-009. M1-010 also records that M1-008 had inspected test prevalence overall, by month, and by first-day-spend third before the M1-009 protocol was frozen. Independent review found no test-driven tuning or model selection, but the holdout was not entirely unseen. A few added summaries may be interpretable, but there is no evidence they would overcome the sample-size constraint or the already weak M1-009 result. A new SKU/category representation increases overfit and review burden without increasing the number of independent eligible customers. The 208-customer test and 304-customer training sample do not support a meaningful standalone power calculation without specifying a minimum effect; the predeclared AUC interval was broad and included chance.

## Side-by-side assessment

| Dimension | A. Established-customer snapshots | B. Enriched Day-21 |
| --- | --- | --- |
| Commercial use | Near-term purchase propensity among active customers; relevant to CRM prioritisation, but not intervention uplift | Early second-purchase propensity for the acquisition-proxy population |
| Scientific interpretation | Familiar RFM/recency outcome; explicit active-base estimand | Clear early-life estimand, but acquisition remains a 12-month proxy |
| Population/support | 21,243 available train snapshots / 12,964 mature test snapshots; 4,691 / 4,551 unique customers, with 4,018 overlapping | 304 train / 208 test customers; 838 mature eligible labels overall |
| Label quality | 42,850 mature rows across Dec–Sep; 8,708 later immature rows kept out of negative counts | 838 mature, plus 168 partial positives and 318 unknown among 1,324 eligible |
| Feature richness | High, low-dimensional point-in-time recency/frequency/value/diversity/basket history | Modest safe first-basket enrichment; no approved product-category taxonomy |
| Temporal evaluation | July split has useful counts but only 5 train and 3 test anchors; repeat rows require customer-clustered uncertainty | Fixed split is valid but limited to a small test and one short seasonal period |
| Main risk | Repeated snapshots and overlapping 90-day windows; customer/season dependence; one short test season | Small acquisition sample, seasonal shift, sparse/high-dimensional features, left-censoring |
| Effort | Moderate: point-in-time monthly aggregations, maturity, clustered temporal evaluation | Low–moderate for a few aggregates; substantially higher if inventing/validating product categories |

## Decisions needed before implementation

1. Confirm Direction A as the next research question and whether its primary label is `purchase_within_next_90d` or the complementary `no_purchase_next_90d` (the latter aligns with the lapse-risk framing).
2. Confirm the monthly start-of-month anchor and the complete trailing-365-day active definition for this prediction task. D-002-08 supports the 365-day window; C-SNAP describes monthly anchors, but the predictive snapshot implementation is not yet encoded.
3. Confirm that the primary temporal estimand allows a customer to appear in both training and later test months, with customer-clustered uncertainty. A customer-disjoint test is a different estimand.
4. Keep country and returns/cancellation features out of the first version unless their point-in-time aggregation and treatment are separately approved. No product-category taxonomy should be inferred from transaction-type labels.

## Recommended next research question and next action

**Recommended question:** among customers active in a complete trailing 365-day window at a monthly anchor, how well do point-in-time RFM and purchase-history features rank whether another qualifying purchase occurs in the next 90 days, evaluated on later mature customer-months?

**Next action:** obtain owner approval for the outcome orientation, monthly anchor, and repeated-customer evaluation estimand in items 1–3; then scope a minimal point-in-time snapshot table and customer-clustered temporal evaluation. Preserve M1-009 as completed and unchanged.
