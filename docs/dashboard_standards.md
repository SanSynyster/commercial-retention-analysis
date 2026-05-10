

# Tableau Dashboard Standards

## Purpose

This document defines the visual and formatting standards for the Tableau Executive Retention & Commercial Health Dashboard.

The dashboard should function as a leadership-facing decision-support product, not an exploratory analysis workspace.

Primary design goals:
- clarity
- trust
- executive readability
- visual restraint
- KPI consistency
- fast interpretation

---

## Dashboard Scope

V1 focuses only on the executive overview layer.

The dashboard should help stakeholders answer four questions quickly:

1. Are customers coming back?
2. How commercially important are repeat customers?
3. Is revenue concentration a risk?
4. Where is the clearest lifecycle opportunity?

Anything that does not support these questions should remain outside the V1 executive dashboard.

---

## Layout Principles

The dashboard should follow a simple narrative structure:

1. What matters?
2. Why is it happening?
3. What should we do?

Recommended executive page flow:

```text
Header and executive takeaway
KPI card row
Revenue mechanics
Retention and lifecycle timing
Customer concentration
CRM opportunity annotation
```

---

## KPI Card Standards

Use a maximum of five dominant KPI cards on the executive page.

Primary KPI cards:

1. Repeat-Order Revenue %
2. Second Purchase Conversion %
3. Median Days to Second Purchase
4. Top 10% Revenue Share
5. Identifiable Revenue Coverage

These cards should be the most visually dominant elements on the dashboard.

Secondary metrics such as refund/cancellation revenue, analytical lifecycle revenue, valid customers, and valid orders should appear only in supporting visuals, tooltips, or secondary sections.

---

## KPI Card Wording

Use short executive-readable labels.

| KPI | Display Label | Supporting Text |
|---|---|---|
| repeat_order_revenue_pct | Repeat-Order Revenue % | Revenue after first purchase |
| second_purchase_conversion_pct | Second Purchase Conversion % | Customers completing a repeat purchase |
| median_days_to_second_purchase | Median Days to Second Purchase | Typical repeat timing |
| top_10_revenue_share_pct | Top 10% Revenue Share | Customer concentration |
| identifiable_revenue_coverage_pct | Identifiable Revenue Coverage | Revenue linked to customer IDs |

---

## Typography Hierarchy

Use a clear text hierarchy.

### Dashboard Title
- Largest text on the dashboard
- Bold
- High contrast
- Used once only

### KPI Values
- Second-largest text
- Strong visual dominance
- Larger than KPI labels

### KPI Labels
- Medium weight
- Clear and concise

### Section Headers
- Consistent size and weight
- Used to separate dashboard sections

### Annotations
- Smaller than section headers
- Subtle visual treatment
- Short and interpretation-focused

---

## Number Formatting Rules

### Percentages
- Use one decimal place
- Example: `79.3%`

### Currency
- Use compact executive formatting
- Example: `£8.9M` or `£896.8K`

### Timing
- Use whole numbers
- Example: `50 days`

### Counts
- Use comma separators
- Example: `4,338`

Avoid excessive decimal precision in the dashboard interface.

---

## Colour Philosophy

Use colour sparingly and intentionally.

Recommended approach:
- neutral background
- dark text for readability
- one primary emphasis colour
- limited use of warning colours

Avoid:
- rainbow palettes
- unnecessary gradients
- excessive red/green formatting
- decorative colours without meaning

Colour should guide attention, not decorate the dashboard.

---

## Whitespace and Spacing Rules

Whitespace is part of the dashboard structure.

Use whitespace to:
- separate sections
- protect KPI readability
- reduce cognitive load
- reinforce visual hierarchy

Avoid:
- tightly packed charts
- overly compressed KPI cards
- crowded annotations
- excessive borders

A simpler dashboard that is easy to scan is preferable to a dense dashboard that contains every insight.

---

## Annotation Standards

Annotations should behave like executive subtitles.

They should:
- reinforce interpretation
- be short
- be non-technical
- guide action

Recommended annotation examples:

> Repeat revenue is strong but concentrated.

> Customers appear willing to return naturally, but later than optimal.

> Earlier lifecycle engagement may accelerate repeat behaviour.

Avoid long methodology explanations in the dashboard body.

---

## Data Scope Note

The dashboard should include a subtle but visible scope note:

> Lifecycle metrics are based on identifiable customers representing ~84% of analytical purchase revenue.

Purpose:
- improve transparency
- pre-empt Finance questions
- reduce KPI interpretation risk

---

## Visual Priority Rules

The dashboard should visually prioritise:

1. Repeat-order revenue
2. Second purchase conversion
3. Median days to second purchase
4. Top 10% revenue share
5. Identifiable revenue coverage

Supporting visuals should not compete with these primary KPI cards.

---

## Charts to Prioritise in V1

Recommended V1 visuals:

- KPI card row
- repeat vs first-order revenue chart
- simplified revenue reconciliation visual
- customer revenue decile chart
- simplified retention or timing visual

Charts should be included only if they support the executive narrative.

---

## Charts to Avoid or Defer in V1

Avoid or defer:

- dense cohort heatmaps on the executive landing page
- detailed customer-level tables
- acquisition-source analysis
- campaign monitoring widgets
- advanced predictive metrics
- excessive filters or drilldowns

These may be useful later but are not required for the executive V1.

---

## Interactivity Standards

V1 should be mostly static.

Allow only minimal interactivity if it improves interpretation.

Avoid:
- complex filters
- dynamic revenue-definition toggles
- excessive dashboard actions
- drilldowns that create multiple versions of the truth

The first build should prioritise a strong static executive story.

---

## Revenue Definition Guidance

Revenue metrics must be clearly labelled.

Important distinction:

- Gross positive purchase revenue: all positive purchase revenue before refunds/cancellations
- Refund/cancellation revenue: negative value from refunds and cancelled invoices
- Net transactional revenue: gross positive revenue after refunds/cancellations
- Analytical lifecycle revenue: gross positive revenue used for behavioural lifecycle analysis
- Identifiable customer revenue: analytical revenue linked to customer IDs

Do not allow Tableau users to freely toggle between definitions in V1.

Instead, show revenue definitions side by side in a fixed reconciliation view.

---

## Usability Principles

The dashboard should be designed for scanning, not studying.

A senior stakeholder should be able to understand the core story within approximately two minutes.

The dashboard should feel:
- calm
- deliberate
- trustworthy
- commercially focused

Avoid anything that makes the dashboard feel like an exploratory notebook or technical analysis dump.

---

## V1 Design Principle

The purpose of Tableau V1 is not analytical completeness.

The purpose is to provide a believable, executive-usable dashboard that communicates:

> Repeat revenue is commercially strong, but concentrated, with slower-than-optimal repeat timing.

This is the strategic narrative the dashboard should protect.