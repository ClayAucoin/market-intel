# Exact-signal within-sector research-readiness audit

Snapshot: **2026-09-22 22:09:15.673100 UTC**. PostgreSQL repeatable-read,
read-only transaction (`transaction_read_only=on`). Repository HEAD at inspection:
`c7fdc822a09cc2b2acb41fdf8f4a3d7adfb90381`.

Evidence: [event-level JSON](sector_readiness_2026-09-22_220915.json).
Reproduction: `python -m src.backtesting.audit_sector_readiness` creates a new
timestamped JSON snapshot; it never updates database rows. The script bounds
the sample to 2,000 matches, each SQL statement to 15 seconds, and checks a
120-second elapsed limit between events. This run audited 194 matches.
The companion Markdown is an interpretation of this saved snapshot.

## Scope and definitions

Existing `historical_sp500` events only: membership must cover event entry date.
An EXISTS membership filter preserves one observation per event; no audited
event has multiple matching membership intervals, so this does not change the
research reader's counts. Signal: revenue acceleration >=20, operating-margin
change >0, pre-entry 20-day excess return versus SPY >0. Training entry dates
through 2023-12-31; testing entry dates from 2024-01-01.

No events, financial facts, prices, classifications, thresholds or methodology
were repaired or replaced. Prior `expanded_200` saved research does not measure
this exact-signal historical sample and was not substituted for it.

**Horizon warning:** stored `30d` means 30 calendar days after entry, followed
by the first available closing price, not 30 trading sessions. The audit retains
this existing definition. Forward excess is stock adjusted-open-to-adjusted-close
return minus SPY's corresponding return, in percentage points. Summed excess
below is an additive attribution of equally weighted event outcomes, NOT a
compounded portfolio return or dollar P&L. Shares of net sums can be unstable
because losses offset gains. JSON also includes shares of positive excess.

## Measured facts: sector coverage

The membership-qualified source contains 14,741 events.

| Measure | Training | Testing |
|---|---:|---:|
| Exact-signal events | 146 | 48 |
| Unique security IDs | 106 | 37 |
| Completed 30d outcomes | 146 | 47 |
| Labeled events / unique securities | 144 / 104 | 48 / 37 |
| Unlabeled events / unique securities | 2 / 2 | 0 / 0 |
| Mean completed excess | +1.4279 pp | +4.8189 pp |
| Sum completed excess | +208.47 pp | +226.49 pp |

Unlabeled training events: security 7468 (current ticker GOOG), 2021-07-28,
+1.92 pp; security 10433 (FLT), 2021-08-10, -0.22 pp. Their combined +1.70 pp
is 0.82% of training's net sum. Unknowns remain in aggregate calculations.

Sector labels are **not point-in-time**: they are undated universe metadata,
selected by MAX(sector) as in the historical research reader, with blank/missing
labels classified UNKNOWN for this audit. No historical sector timeline is
available in the inspected schema. Labels can reflect later classifications.

| Sector | Train events / securities | Test events / securities | Test completed | Test mean excess pp |
|---|---:|---:|---:|---:|
| Communication Services | 4 / 3 | 2 / 2 | 2 | +6.3400 |
| Consumer Discretionary | 26 / 18 | 2 / 1 | 2 | +0.0500 |
| Consumer Staples | 3 / 3 | 0 / 0 | 0 | — |
| Energy | 5 / 5 | 6 / 5 | 6 | +10.1800 |
| Financials | 4 / 3 | 0 / 0 | 0 | — |
| Healthcare | 22 / 17 | 2 / 2 | 2 | -4.7950 |
| Industrials | 31 / 24 | 6 / 5 | 6 | -1.4833 |
| Materials | 13 / 6 | 2 / 2 | 2 | +0.9450 |
| Real Estate | 6 / 6 | 3 / 3 | 3 | -0.8167 |
| Technology | 20 / 10 | 21 / 13 | 20 | +8.9175 |
| Utilities | 10 / 9 | 4 / 4 | 4 | -1.6675 |
| UNKNOWN | 2 / 2 | 0 / 0 | 0 | — |

Technology is 43.75% of testing matches and contributes +178.35 pp, or 78.75%
of testing's net sum. Energy contributes +61.08 pp. Together these two current
sector groups contribute +239.43 pp; the other 21 completed outcomes sum to
**-12.94 pp (mean -0.6162 pp)**. This is a descriptive concentration finding,
not permission to select or exclude sectors using testing outcomes.

## Measured facts: security/company concentration

The JSON `summary.*.companies` contains every security's event count, event
share, completed count, net excess contribution, positive-excess contribution,
and performance excluding that security. Grouping uses security_id, never ticker
alone. These are security-level statistics; distinct share classes and corporate
relationships are not consolidated into economic company groups.

Largest event frequencies: training NVDA and AMD each 5/146 (3.42%); testing
SNDK, WDC and MU each 3/48 (6.25%). Frequency concentration alone is modest.

| Split | Largest net contributors: ticker (security ID), summed excess pp |
|---|---|
| Train | AMD (13) +51.76; LRCX (29) +25.99; CF (645) +24.38; CEG (179) +22.73; PWR (163) +21.02 |
| Test | FSLR (573) +48.06; SNDK (60) +44.53; WDC (93) +39.48; STX (77) +34.47; MPC (162) +24.73 |

Training AMD contributes 24.83% of the net sum. Top three contribute 48.99%;
top five contribute **69.98%** from 11 outcomes. Removing top five leaves 135
outcomes, +62.59 pp total, mean **+0.4636 pp**.

Testing FSLR contributes 21.22% of the net sum. Top three contribute 58.31%;
top five contribute **84.45%** from 9 outcomes (19.15% of completed observations).
Removing top three leaves 40 completed outcomes, mean +2.3605 pp; removing
top five leaves 38, +35.22 pp total, mean **+0.9268 pp**. No single company
alone explains all excess performance, but a small group materially dominates
its magnitude. These ex-post exclusions are stress tests, not independent tests.

## Measured facts: prices, horizons and split boundary

Across all **193 completed** exact-signal outcomes:

- Stock/SPY first-available exit-date mismatches: **0**; maximum absolute date
  difference **0 days** (146 training and 47 testing aligned).
- Missing exits: **0** completed; invalid/nonpositive/nonfinite exit prices: **0**.
- Missing, duplicated or invalid entry adjusted opens: **0**, including the
  incomplete event. Stored stock exit versus current lookup mismatches: **0**.
- One incomplete testing observation: NVDA, event 380581, entry 2026-08-27.
  Its calendar target is 2026-09-26, later than the snapshot. Neither exit is
  available yet. This is right-censoring, not an observed mature price gap.
- All 194 pre-entry stock/SPY windows contain 21 finite positive closes; stock
  and SPY date sequences match for every window. Reconstructed momentum equals
  stored pre_excess_20d for all 194. Every selected price precedes entry date.

Across the full membership-qualified event population, **36 training events**
have a stored stock 30d exit after 2023-12-31. Among exact-signal training
observations the count is **0** using either stock or SPY exit. Boundary-crossing
exact-signal contribution is 0 pp; all 146 completed training observations are
contained and contribute +208.47 pp (mean +1.4279 pp).

Price alignment establishes consistency of current stored data, not historical
vendor publication times, original adjustment vintages, uninterrupted exchange
calendar coverage, or correctness of every underlying corporate-action series.
No prices were silently repaired. Forward stored returns were used unchanged;
this is an alignment audit, not a complete return recalculation.

## Measured facts: input availability / provenance

Decision cutoff is **09:30 America/New_York on historical entry date**, matching
the backtest's entry open, NOT today's prospective commitment time. Revenue
acceleration dependencies are current revenue, its prior-year comparator,
previous-quarter revenue, and that quarter's prior-year comparator. Margin-change
dependencies are current/prior-year operating income and current/prior-year
revenue, selected by the existing calculation helpers.

For all selected dependencies, stored accession joins are present, issuer IDs
match, acceptance timestamps are available, and no selected filing acceptance
or fact filed date is after the entry cutoff. No duplicate metric/period choice
was encountered. No dependency set mixes company IDs. Reconstructed acceleration and margin change match all 194
stored signal values. This verifies current database consistency, not original
snapshot provenance.

| Evidence classification, event counts | Train | Test |
|---|---:|---:|
| Revenue: direct, uniquely linked dependencies accepted by cutoff | 84 | 25 |
| Revenue: at least one derived dependency with unpreserved component lineage | 62 | 23 |
| Margin: direct, uniquely linked dependencies accepted by cutoff | 132 | 37 |
| Margin: at least one derived dependency with unpreserved component lineage | 14 | 11 |
| Either component: missing filing/issuer/timestamp evidence | 0 | 0 |
| Either component: recorded source appears after cutoff | 0 | 0 |
| Both financial components supported by direct source metadata | 84 | 25 |

Derived-quarter construction subtracts three quarters from an annual value and
retains the annual accession/date (`financial_history.py`). The financial-facts
table does not preserve those component source identities. Consequently **85/194
events** cannot have full input availability established solely from the stored
lineage, even though their retained source timestamps are timely. The database
contains 146 distinct derived dependencies used by training events and 65 by
testing events (counts are within split, not necessarily disjoint across splits).
Derived does NOT prove lookahead; it means the proof is incomplete.

Momentum has no future-dated closes in any of 194 windows and all windows align,
so event-date availability is supported at the trading-date level. All 194 lack
historical vendor-vintage/publication evidence in this audit. Adjusted prices
stored now are not proof of exactly what the system knew at the time.

Direct financial availability here means **stored source metadata supports it**.
The audit does not independently re-read SEC filings or prove that a value and
concept belong to the linked accession. Facts are mutable upserts rather than
immutable historical vintages; event rows lack frozen dependency IDs. This
limits even the direct-source classification's evidentiary strength.

## Measured facts: identity

All 194 events resolve to stable security IDs. The standard research reader's
omission of security_id prevents its output alone from proving stable identity,
but does not block this audit. No qualifying event's current ticker is shared
by multiple securities in the current securities table; no duplicate membership
join or multiple active dated ticker-history rows were encountered.

Active dated ticker history is absent for **143/146 training events (104 unique
securities)** and **46/48 testing events (36 unique securities)**. Absence is not
proof of a ticker change, but historical ticker identity is unverified for these.

One explicit discrepancy: security **686**, current ticker **GEN**, event 376352
on 2020-08-07. Its dated ticker history says **NLOK** (2019-11-05 through
2022-11-07). Its stored excess is -1.39 pp. Audit price lookups deliberately
followed the existing current-ticker implementation. A provider's backfilled
GEN series might legitimately cover NLOK, but that mapping was not proven here.
The current label is a reporting issue; price-series identity remains an audit
limitation until verified. No historical prices or identity mappings were changed.

## Interpretation and recommended next actions (not implemented)

**Material to broad within-sector conclusions:**

1. No point-in-time sectors: obtain dated sector evidence for a historical claim,
   or explicitly restrict the next study to exploratory current-label groups.
2. Strong net-return dependence on Technology/Energy and five securities; very
   small sector samples (and zero testing matches in two sectors) do not establish
   broad efficacy. Predefine within-sector comparators, company-clustered
   uncertainty and concentration sensitivity; do not optimize on testing results.
3. Verify the 85 events' derived component provenance before treating all inputs
   as proven available. Prefer archived source evidence; do not repair stored
   facts merely to pass this audit. Freeze lineage/vintages in a separately
   approved future design if needed.
4. Resolve the intended horizon explicitly: existing 30 calendar days versus
   requested 30 trading sessions. No relabeling or silent calculation change.
5. Audit historical price-symbol continuity, beginning with GEN/NLOK and missing
   ticker-history coverage; stable IDs solve grouping but not price provenance.

**Minor or presently non-impacting:** two unlabeled training observations have
small measured aggregate contribution; retain UNKNOWN. The one immature NVDA
outcome should remain excluded from completed-return denominators. Missing IDs
in the shared reader are avoidable by direct stable-ID reads. General boundary
overlap exists but affects zero exact-signal training outcomes in this snapshot.
No completed exit mismatch, invalid sampled price or recorded late source was
found; none needs a data correction based on this audit.

Next: review these limitations and approve a descriptive within-sector study
only under an explicit sector-label/horizon convention, with source-lineage and
identity validation ahead of claims of historical point-in-time validity. Preserve
the existing signal, train/test split, production and benchmark calculations.

## Validation and operational scope

Six focused offline tests passed (dependency selection, direct/late/missing/derived
availability, issuer mismatch, stable-ID completed-only statistics, invalid
prices). Both new Python files compiled. No external API, import, event rebuild,
paper trading, daily orchestrator, migration or notification ran. Only the audit
script, offline tests, and these JSON/Markdown reports were created. Concurrent
SEC cache changes observed in the workspace were not made or altered by this
audit; repeatable-read kept the database evidence internally consistent.
