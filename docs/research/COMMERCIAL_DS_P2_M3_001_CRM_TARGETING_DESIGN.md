# M3-001 — CRM Targeting Policy and Incremental Value Design

## Purpose and separation of questions

M2 established that historical purchasing behaviour can rank future purchasers: Model C ROC-AUC was 0.766, RFM ROC-AUC was 0.760, and Model C top-decile precision/lift were 69.3%/2.95× on the July–November 2011 holdout. M2-012 found a modest improvement in Brier score after a lagged intercept update, with seasonal underprediction remaining.

These findings concern **purchase propensity under the historical operating environment**. The dataset has no randomized campaign assignment or reliable treatment exposure. It cannot establish which customers are more responsive to marketing, estimate incremental campaign purchases, or support an uplift claim. Keep retrospective ranking evaluation separate from causal campaign evaluation.

## A. Retrospective targeting-policy comparison

Use only the frozen M2-004 customer snapshots, existing M2-008 holdout predictions, and the fully mature July–November 2011 test outcomes. Do not fit or recalibrate models. M2-008/M2-009 already examined this test period, so this comparison is descriptive and exploratory, not a new holdout validation.

Compare four policies at **5%, 10% and 20% capacity within each month**:

1. **Full-model propensity:** rank by frozen `probability_C_full_11`.
2. **RFM propensity:** rank by frozen `probability_B_rfm`.
3. **Recent-frequency rule:** rank by `qualifying_purchase_occasions_90d`, a pre-decision feature already present in `src/monthly_customer_snapshots.py`. This gives a transparent behavioural benchmark without inventing a new feature definition.
4. **Random targeting:** use the analytic random-selection expectation as the reference: precision equals monthly prevalence, expected capture equals capacity, and lift equals 1. A seeded random list may be produced only if a concrete overlap comparison requires one.

Select `ceil(capacity × eligible mature monthly snapshots)` customers for each ranked policy. The existing model scores are continuous, but the frequency rule has many ties. Break ties with a predeclared pseudorandom key derived from the internal customer key and month, independent of the outcome, and keep keys out of reports. Record the realized selected count. Do not let all tied customers exceed the stipulated campaign capacity.

For each policy, month and capacity, report:

- **Purchase precision:** selected customers with a qualifying purchase in the next 30 days divided by selected customers.
- **Purchase capture:** selected purchasers divided by all purchasers in that month's eligible test population.
- **Lift:** policy precision divided by that month's observed prevalence.
- **Policy overlap:** pairwise intersection count, intersection as a share of each selected list, and Jaccard similarity. Report each policy's unique selections and captured purchasers as well.
- **Contact concentration:** how often a customer would be selected in multiple months under the month-by-month simulation, and unique customers contacted at least once.

Report monthly results first, then pooled snapshot-weighted summaries as secondary descriptions. Use paired customer-cluster resampling for uncertainty on policy metric differences if intervals are reported; preserve each customer's repeated months and bootstrap all policies on the same resampled clusters. These intervals describe customer resampling within this fixed period, not uncertainty across future seasons. Avoid row-independent significance tests and do not infer causality from precision, capture, lift, or policy overlap.

For this retrospective comparison, evaluate each month as a separate capacity decision and also disclose repeated selections across months. Do not impose a new contact-frequency rule after observing results. A real campaign policy must define suppression and contact caps before the campaign list is selected.

## B. Commercial decision framework

Keep these quantities distinct:

| Quantity | Meaning | Status with current evidence |
| --- | --- | --- |
| Baseline purchase probability, `p0(X)` | Probability of a qualifying purchase under the historical mixture of business-as-usual practices | Modelled by M2; not necessarily an untreated probability because exposure is unknown |
| Incremental treatment effect, `tau(X)` | `P(purchase | contact, X) − P(purchase | no contact, X)` | Unknown; must be estimated by random assignment |
| Incremental contribution margin | Expected margin difference between assigned campaign and control | Unknown; requires order economics and experimental outcomes |
| Contact and incentive costs | Variable cost of sending and any incremental discount/promotion | Unknown or hypothetical until campaign and cost data are supplied |
| Capacity and contact limits | Available sends and suppression/frequency constraints | Operational inputs requiring CRM-owner approval |

Do not assume high `p0(X)` implies positive or high `tau(X)`. Customers already likely to purchase may be less persuadable, equally persuadable, or more persuadable; the observational data cannot distinguish these cases.

Define contribution margin before campaign-specific contact and incentive costs as net sales less product cost, returns/refunds, and agreed variable fulfilment/payment costs. Then a customer-level net incremental value can be written:

`expected net incremental value(X) = E[CM(1) − CM(0) | X] − incremental contact cost(X) − incremental incentive cost(X)`

If margin already includes redeemed discounts, do not subtract discount cost a second time. A simpler proxy, `tau(X) × expected contribution per incremental purchase − campaign costs`, requires an assumption that treatment changes purchase probability without changing basket size, timing, returns, or margin; validate that assumption before using it for allocation.

For a future policy, maximize expected net incremental value subject to send capacity, customer eligibility, contact-frequency limits and any minimum-value guardrail. If reliable incremental value is unavailable, use the pilot to learn it; do not optimize on propensity alone and label the result incremental value.

## C. Customer-randomized CRM pilot

### Initial estimand and population

After the retrospective policy comparison, select **one** policy and capacity for a pilot. A practical initial default is a predeclared 10% target list under the selected policy, subject to CRM owner approval. The pilot estimates the intention-to-treat effect of one specified campaign among customers selected by that policy; it does not compare all candidate policies causally.

Eligibility should be set before scoring and randomization: identifiable, established customers with the required historical data; current permission for the chosen channel; not opted out, suppressed, in a service/recovery workflow, or contacted inside the approved exclusion period; and eligible for the same offer and market. Use a single enrollment decision per customer during the pilot. If household/account links exist and sharing could cause contamination, randomize or suppress at the linked household level and power for that unit; otherwise use stable customer-level assignment.

### Assignment and conditions

- Build the eligible target list once from information available before assignment and freeze the policy, capacity, campaign, and analysis plan.
- Randomize customers 1:1 within predeclared strata such as score band and market/channel. Persist assignment so repeated monthly snapshots cannot cause a customer to switch arms or be re-randomized.
- **Treatment:** one specified message/channel and offer, if any, delivered under a documented schedule.
- **Control:** suppress the study campaign for the same follow-up period while continuing documented business-as-usual activity.
- Keep the study contact inside the approved send capacity; holdout assignment reduces actual treatment sends. Record assignment regardless of delivery.

### Outcomes and analysis

Use **any canonical qualifying purchase in the 30 days after randomization** as the primary behavioural outcome, matching M2's horizon. The analysis population is every randomized eligible customer; analyze by assigned group (intention to treat), regardless of delivery, open, click, redemption, or later contact. Estimate absolute conversion-rate difference with a confidence interval and report arm counts and follow-up completeness.

Key secondary outcomes: contribution margin per randomized customer over the same 30 days; merchandise value; number of qualifying purchases; discount/redemption; returns/cancellations; delivery; unsubscribe, complaint and other agreed customer-harm indicators. Specify net margin accounting before launch. Use a fixed outcome window and complete follow-up for both arms; do not turn missing order linkage into a negative.

Customer-level randomization avoids cross-month assignment switching. Analyze one row per enrolled customer for the primary endpoint. If multiple campaign contacts or enrollment waves are later introduced, preserve assignment and use customer-level dependence in analysis. Record concurrent campaigns and cross-channel contact. Spillover from shared accounts, forwarding, household members, or control leakage can dilute the ITT contrast; measure and limit it where possible.

### Power and commercial guardrails

Calculate sample size before launch from a current eligible-population baseline, a business-relevant minimum detectable effect, two-sided type-I error (recommend 5%), desired power (recommend at least 80%), allocation ratio, expected follow-up loss, and any clustering. For a binary outcome with equal arms, a rough planning approximation is:

`n per arm ≈ 2 × (z[1−alpha/2] + z[power])² × p̄(1−p̄) / delta²`

Using the historical holdout prevalence of 23.5% only as an illustration (not an untreated rate or a current forecast), this is about 3,140 customers per arm for a 3 percentage-point absolute difference and 7,060 per arm for a 2-point difference, under independent customer assignment and no attrition. The actual campaign calculation must use current eligible data. Contribution-margin power may require more customers because margin is variable; estimate its variance from appropriate recent finance-linked data. A 10% targeting policy also requires a sufficiently large eligible base to populate both treatment and holdout arms.

Predefine guardrails for campaign spend, maximum discount, contact frequency, deliverability, complaints/unsubscribes, and minimum expected net value. Pause or stop rules should be based on customer harm, compliance, or budget limits—not interim outcome peeking. A positive purchase effect alone does not establish profitability.

### How experiment data can support uplift research

Random assignment makes treatment/control outcome differences causal on average. With sufficient randomized observations across relevant customer histories, future work can estimate conditional treatment effects and compare prespecified uplift policies on held-out experimental data. Preserve assignment probability, treatment delivery, pre-contact features, outcomes, and cost data. A pilot restricted only to the highest-propensity segment supports effects for that segment, not reliable uplift ranking across the full customer base. Do not train an uplift model from historical purchase propensity alone.

## Minimum additional business data

The M2 dataset and aggregate reports are sufficient for the retrospective propensity-policy comparison, but not for causal or profitability analysis. A real pilot requires, at minimum:

1. Stable customer key and pre-contact feature snapshot with decision/assignment timestamp.
2. Campaign eligibility, suppression reason, randomized assignment, assignment probability/stratum, channel, content/offer, send/delivery timestamps, and other campaign contacts during follow-up.
3. Permission/opt-out status and contact-frequency history at enrollment.
4. Linked order outcomes with qualifying-purchase definition, timestamp, merchandise value, discounts, returns/refunds, product cost and variable fulfilment/payment costs.
5. Contact/send cost and incentive/redemption cost, with an agreed margin calculation.
6. Enough post-assignment observation to mature the 30-day outcome and capture all eligible transactions for both arms.

The current UCI data provides historical transactions and gross-merchandise features, but no verified campaign assignment/exposure, consent, contact cost, or complete contribution-margin accounting. Those are genuine blockers to estimating campaign incrementality and net commercial value.

## Assumptions, decisions and limitations

- The existing July–November test holdout is already examined; new policy summaries are retrospective and exploratory.
- The baseline score estimates purchasing under an unknown historical exposure mix. No historical CRM treatment field is assumed.
- The 90-day occasion count is available before each snapshot decision and is used only as a transparent policy rule.
- A first randomized pilot tests one selected policy against a contemporaneous control; it does not causally rank all policies.
- Before launch, the owner must approve the campaign/offer/channel, chosen targeting policy and capacity, customer eligibility/suppression rules, contact-frequency cap, outcome/margin definitions, and business-relevant minimum detectable effect.

## Recommended next implementation task

Implement **M3-002: retrospective targeting-policy comparison** using the frozen M2-004 snapshots and M2-008 predictions only. For each mature test month, compare Model C, Model B, the existing 90-day qualifying-occasion rule, and the random expectation at 5%, 10% and 20%. Report precision, capture, lift, pairwise policy overlap, repeated-customer contact concentration, and monthly distributions as aggregate results. Add focused tests for capacity selection/ties, metric accounting, overlap and customer clustering. Do not fit models, estimate causal effects, create a campaign list, or modify the M2 baseline artifacts. Use M3-002 results to let the owner choose one policy and capacity before a pilot protocol is prepared.
