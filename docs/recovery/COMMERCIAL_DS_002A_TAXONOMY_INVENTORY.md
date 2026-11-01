# COMMERCIAL-DS-002A — Stock-code taxonomy inventory

**Status:** evidence proposal; no mapping in this document is owner-approved.<br>
**Sources:** SHA-asserted V1 and overlap-corrected V2 (`v2c`).<br>
**Machine-readable inventory:** [COMMERCIAL_DS_002A_STOCK_CODE_INVENTORY.csv](COMMERCIAL_DS_002A_STOCK_CODE_INVENTORY.csv)

## Executive finding

The union contains **5,132 normalized stock codes** (uppercase, preserving punctuation). V1 contains 3,958 and corrected V2 contains 5,132. A syntax rule is unsafe: numeric `23444` is “Next Day Carriage”, while alphanumeric `SP1002` is merchandise. The inventory therefore proposes explicit code mappings plus exact description exceptions and defaults every unseen or unsupported code to `unclassified`.

The evidence classifier proposes 4,452 merchandise codes, 299 merchandise codes needing description-level exceptions, and 351 unclassified codes. The unclassified set represents **357 corrected-V2 rows**. Most have no observed description and cannot defensibly be promoted to merchandise. This is not a failed investigation; it is the set that requires owner/data-steward resolution before a production mapping can pass.

## Inventory fields and counting rules

The CSV has one row per uppercase normalized code across V1 and corrected V2. It retains observed case variants and all observed descriptions separately by source. For each source it reports row count; positive, negative and zero line-value counts; identifiable valid-positive revenue; and all negative line revenue. Revenue is recomputed with `Decimal(str(quantity)) × Decimal(str(unit_price))`.

“Identifiable positive” applies the reviewed current rule: identified customer, quantity and price positive, and invoice not cancellation-prefixed. Negative revenue is descriptive and includes identified and unidentified lines. Categories are proposals, and `owner_approval_required` is deliberately broad where evidence is incomplete or an exception changes business treatment.

## Material and requested codes in corrected V2

| Code | Rows (+/−/0) | Identifiable positive | Negative revenue | Proposed category | Finding / approval |
| --- | ---: | ---: | ---: | --- | --- |
| `ADJUST` | 67 (36/31/0) | £3,538.520 | £−2,062.69 | manual adjustment | Explicit adjustment descriptions; owner approval required |
| `ADJUST2` | 3 (3/0/0) | £731.050 | £0 | manual adjustment | Owner approval required |
| `TEST001` | 15 (9/4/2) | £225.000 | £−22.50 | test | Exclude from product behaviour if approved |
| `TEST002` | 2 (1/0/1) | £1.000 | £0 | test | Exclude from product behaviour if approved |
| `23444` | 81 (79/1/1) | £1,200.000 | £−15.00 | shipping | Numeric exception: “Next Day Carriage”; owner approval required |
| `M` (includes observed `m`) | 1,403 (862/534/7) | £152,166.320 | £−422,939.08 | manual adjustment | Material mixed-sign exposure; owner decision required |
| `D` | 173 (5/168/0) | £397.890 | £−13,277.52 | discount | Owner decision required |
| `CRUK` | 16 (0/16/0) | £0 | £−7,933.43 | fee/commission | Owner decision required |
| `PADS` | 19 (17/1/1) | £0.017 | £−36.60 | merchandise | Description is a physical cushion accessory; conflicts with DS-002 exclusion list |
| `B` | 6 (1/5/0) | £0 | £−158,676.14 | bad debt | Owner decision required |
| `S` | 102 (3/99/0) | £0 | £−6,137.70 | sample | Owner decision required |
| `POST` | 2,086 (1,851/228/7) | £124,648.040 | £−15,252.01 | shipping | High-confidence non-merchandise |
| `DOT` | 1,425 (1,415/3/7) | £11,906.360 | £−10.01 | shipping | Dotcom postage |
| `C2` | 277 (267/7/3) | £12,546.000 | £−290.00 | shipping | Carriage |
| `BANK CHARGES` | 100 (34/66/0) | £450.001 | £−36,001.49 | fee | Also demonstrates three-decimal monetary precision |
| `AMAZONFEE` | 36 (3/33/0) | £0 | £−241,988.30 | fee | Owner approval required |
| `C3`, `GIFT` | 1 each (0/0/1) | £0 | £0 | unclassified | No description evidence; do not infer a category |
| `SP1002` | 3 (2/0/1) | £14.750 | £0 | merchandise | Description supports a physical product |

The five reviewer-identified omissions (`ADJUST*`, `TEST*`, `23444`) contribute **£5,695.57** identifiable positive revenue. Their small commercial share does not make a fail-open rule acceptable.

Gift-voucher codes `GIFT_0001_*` are proposed as `gift_voucher`; code `22016` is also a voucher by description. `DCGS*` descriptions mostly look like Dotcomgiftshop merchandise, but ambiguous or descriptionless family members remain owner-review items. No family prefix is treated as conclusive without evidence.

## Numeric-code investigation

Numeric syntax is not a category. The inventory identifies `23444` as shipping despite its numeric code. It also flags 213 numeric codes with at least one administrative description (for example “adjustment”, “damages”, “missing”, “sold as set”, or “Amazon Adjustment”) interleaved with ordinary product descriptions. These are proposed as `merchandise_with_description_exceptions`, not as wholly non-product codes. The exception list and exact descriptions are in the CSV.

This 213-code screen is deliberately sensitive and is a **review queue**, not an approved exclusion list. A description such as “damages” can explain a stock adjustment while the same code remains merchandise on normal sale lines. Exact description mappings must therefore override the code-level merchandise category only for matching rows.

## Proposed portable classification policy

1. Materialise a versioned UTF-8 mapping seed with `stock_code_normalized`, `category`, rationale, confidence, decision reference and effective version. Pandas, dbt and Spark consume the same seed; none reimplements category logic independently.
2. Normalize only documented representation differences (trim and uppercase). Do not infer merchandise from numeric or alphanumeric syntax.
3. Apply an explicit exact-description exception seed first, keyed by normalized code plus normalized description. This supports `23444` and administrative rows on otherwise merchandise codes.
4. Apply the explicit code mapping second.
5. Map every unmatched row to `unclassified`; never to merchandise by default.
6. Fail validation when `unclassified` row count is non-zero. Emit the unmatched code, description, counts and revenue for stewardship.
7. Preserve the raw code and description, mapping version and matched-rule identifier on classified outputs so decisions remain reviewable across engines.

The evidence script contains an unseen-code fixture and asserts that it maps to `unclassified`. The current evidence inventory itself is not production-ready because 357 corrected-V2 rows remain unclassified; owner/steward decisions are therefore a real gate.

## Owner decisions required

- Approve the category structure and precedence (description exception → code map → `unclassified`), including fail-closed validation.
- Decide treatment of `M`, `D`, `CRUK`, `PADS`, `B`, `S`, `ADJUST`, `ADJUST2`, `TEST001`, `TEST002`, `23444`, gift vouchers, fees and carriage.
- Review the 299 mixed-description codes and approve exact administrative-description exceptions rather than whole-code exclusions.
- Resolve or explicitly accept exclusion of the 351 unclassified codes / 357 corrected-V2 rows.
- Decide whether gift-voucher sales belong in commercial revenue, customer monetary value, neither, or a separately reported field.

Until those decisions are recorded, the taxonomy is **RECOMMENDED / BLOCKED FOR PRODUCTION**, not approved.
