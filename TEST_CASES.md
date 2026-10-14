# TEST_CASES.md — Price Alert Tool Test Specification & Anomaly Matrix

This document provides the complete, production-grade test catalog for the **Price Alert Tool**. It details all 24 unit, boundary, and hostile edge-case tests implemented in [tests/test_alerts.py](file:///c:/Users/Shrey/Projects/Wissen%20Technology/tests/test_alerts.py).

---

## Master Test Matrix & Pipeline Policies

| Test Class | Test Name | Anomaly / Edge Case | Pipeline Policy | Production Likelihood |
| :--- | :--- | :--- | :--- | :--- |
| **`TestFileStructureAndEncoding`** | `test_utf8_bom_handling` | UTF-8 Byte Order Mark (`\ufeff`) prefix | Decide & Document (stdout/exit 0) | High |
| | `test_mixed_line_endings` | Mixed `\r\n`, `\n`, and stray `\r` | Decide & Document (stdout/exit 0) | High |
| | `test_header_variations_and_extra_columns` | Whitespace padding, mixed casing, extra columns | Decide & Document (stdout/exit 0) | High |
| | `test_missing_required_headers` | Missing mandatory `close` or `date` columns | Fatal (exit != 0) | Medium |
| | `test_ragged_and_blank_rows` | Blank lines and truncated ragged rows | Skip + Warn (stderr) | High |
| **`TestDateAndSequenceEdgeCases`** | `test_chronological_disarray` | Shuffled or reverse-chronological CSV rows | Decide & Document (stdout/exit 0) | High |
| | `test_interleaved_instruments` | Alternating rows across different tickers | Decide & Document (stdout/exit 0) | High |
| | `test_trading_day_gaps` | Irregular calendar gaps (weekends, holidays) | Decide & Document (stdout/exit 0) | High |
| | `test_duplicate_date_instrument_rows` | Duplicate dates (identical deduped; conflicting last-wins) | Decide & Document (stdout/exit 0) | Medium |
| **`TestPriceCleaningAndPrecision`** | `test_non_numeric_and_poison_values` | Non-numeric tokens (`NaN`, `inf`, `null`, `N/A`) | Skip + Warn (stderr) | High |
| | `test_zero_and_negative_prices` | Non-positive prices (`<= 0.0`) | Skip + Warn (stderr) | Low |
| | `test_floating_point_drift_on_identical_prices` | IEEE 754 precision noise on constant price series | Decide & Document (stdout/exit 0) | High |
| **`TestLevelRuleSemantics`** | `test_day_zero_invariant` | Price starting below target on first observation day | Decide & Document (stdout/exit 0) | High |
| | `test_sustained_state_fires_once` | Price remaining below threshold over multiple days | Decide & Document (stdout/exit 0) | High |
| | `test_boundary_touch_versus_strict_cross` | Touching threshold level vs strict penetration | Decide & Document (stdout/exit 0) | High |
| | `test_oscillating_crossings` | Price repeatedly whipsawing across threshold | Decide & Document (stdout/exit 0) | High |
| **`TestMACrossSemantics`** | `test_insufficient_warmup_window` | Price history shorter than long window | Decide & Document (stdout/exit 0) | High |
| | `test_exact_boundary_off_by_one` | Day index $L-1$ baseline vs Day index $L$ cross | Decide & Document (stdout/exit 0) | High |
| | `test_both_directions` | Golden Cross (`above`) and Death Cross (`below`) | Decide & Document (stdout/exit 0) | High |
| | `test_invalid_window_configuration` | Inverted (`short >= long`) or non-positive windows | Fatal (exit != 0) | Medium |
| **`TestRuleValidationAndCLIOutput`** | `test_invalid_rules_json` | Non-list root, empty JSON, or missing schema fields | Fatal (exit != 0) | Medium |
| | `test_deterministic_sort_ordering` | Compound sorting: `date` ASC, then `rule_id` string ASC | Decide & Document (stdout/exit 0) | High |
| | `test_silent_output_on_no_triggers` | Zero output when no conditions fire | Decide & Document (stdout/exit 0) | High |
| | `test_exact_cli_line_format` | Strict format and whitespace conformance | Decide & Document (stdout/exit 0) | High |

---

## Part 1: File Structure, Encoding & Header Robustness (`TestFileStructureAndEncoding`)

### `test_utf8_bom_handling`
- **Edge Case Covered:** Prices CSV file prefixed with a UTF-8 Byte Order Mark (`\ufeff` / `0xEF, 0xBB, 0xBF`).
- **Test Fixture / Input:**
  ```csv
  \ufeffdate,instrument,close
  2026-09-01,INFY,1520.50
  2026-09-02,INFY,1490.00
  ```
  Rule: `[{"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}]`
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). BOM is stripped silently; column headers parse correctly; alert triggers on `stdout`:
  `2026-09-02 r1 INFY level below 1500`
- **Production Likelihood:** High
- **Real-World Production Context:** Microsoft Excel on Windows routinely prefixes exported CSV files with a 3-byte UTF-8 BOM. Standard Python file readers using basic `'utf-8'` treat `\ufeffdate` as the first column name, causing silent header mismatch crashes unless decoded with `'utf-8-sig'`.

---

### `test_mixed_line_endings`
- **Edge Case Covered:** Ingestion of mixed line terminators (`\r\n` Windows CRLF, `\n` Unix LF, and stray `\r` classic Mac CR) within a single CSV file.
- **Test Fixture / Input:**
  ```text
  "date,instrument,close\r\n2026-09-01,INFY,1520.50\r2026-09-02,INFY,1490.00\n"
  ```
  Rule: `level below 1500`
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Normalized into standard universal newlines; no `\r` carriage returns pollute output tokens; alert triggers on `stdout`:
  `2026-09-02 r1 INFY level below 1500`
- **Production Likelihood:** High
- **Real-World Production Context:** Heterogeneous data engineering pipelines aggregate files across Windows task runners, Linux container workers, and cloud object stores (S3/GCS). Unsanitized lines containing stray `\r` characters trigger Python `_csv.Error: new-line character seen in unquoted field` exceptions.

---

### `test_header_variations_and_extra_columns`
- **Edge Case Covered:** CSV headers formatted with surrounding whitespace, mixed casing, and superfluous metadata columns.
- **Test Fixture / Input:**
  ```csv
   Date , CLOSE ,instrument,volume,extra 
  2026-09-01,1520.50,INFY,10000,foo
  2026-09-02,1490.00,INFY,20000,bar
  ```
  Rule: `level below 1500`
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Headers are normalized via lowercase and whitespace trimming; unneeded columns (`volume`, `extra`) are safely ignored; alert triggers on `stdout`:
  `2026-09-02 r1 INFY level below 1500`
- **Production Likelihood:** High
- **Real-World Production Context:** Upstream market data vendors frequently add diagnostic fields or alter column casing across minor schema revisions. Brittle index-based parsers fail when extra columns shift the position of target fields.

---

### `test_missing_required_headers`
- **Edge Case Covered:** CSV price input missing one or more essential columns (e.g., missing `close` or `date`).
- **Test Fixture / Input:**
  ```csv
  date,instrument
  2026-09-01,INFY
  2026-09-02,INFY
  ```
  Rule: `level below 1500`
- **Expected Outcome & Pipeline Handling:** Fatal (exit != 0). Tool halts with exit code 1 and writes an explicit error message to `stderr` specifying the missing required header.
- **Production Likelihood:** Medium
- **Real-World Production Context:** Upstream extract jobs can produce truncated or schema-corrupted exports due to upstream database view migrations. The tool must fail fast rather than attempting undefined price inference.

---

### `test_ragged_and_blank_rows`
- **Edge Case Covered:** CSV containing completely blank lines, whitespace-only rows, and ragged rows with missing columns.
- **Test Fixture / Input:**
  ```csv
  date,instrument,close
  2026-09-01,INFY,1520.50

     
  2026-09-02,INFY
  2026-09-03,INFY,1490.00
  ```
  Rule: `level below 1500`
- **Expected Outcome & Pipeline Handling:** Skip + Warn (stderr). Blank lines are skipped silently; ragged rows emit warnings to `stderr`; valid rows are evaluated cleanly, outputting to `stdout`:
  `2026-09-03 r1 INFY level below 1500`
- **Production Likelihood:** High
- **Real-World Production Context:** Append-only loggers and streaming file dumps frequently flush trailing blank lines or partial network buffers. Dropping incomplete records while logging warnings ensures high availability for downstream consumers.

---

## Part 2: Ingestion, Chronology & Instrument Isolation (`TestDateAndSequenceEdgeCases`)

### `test_chronological_disarray`
- **Edge Case Covered:** Input CSV rows delivered in scrambled or reverse chronological sequence.
- **Test Fixture / Input:**
  ```csv
  date,instrument,close
  2026-09-03,INFY,1480.00
  2026-09-01,INFY,1520.00
  2026-09-02,INFY,1490.00
  ```
  Rule: `level below 1500`
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Ingestion engine sorts prices chronologically per ticker prior to evaluation; alert fires strictly on Day 2 (`2026-09-02`) and remains silent on Day 3 (`2026-09-03`):
  `2026-09-02 r1 INFY level below 1500`
- **Production Likelihood:** High
- **Real-World Production Context:** Distributed NoSQL datastores (e.g., Apache Cassandra, DynamoDB) and parallel Kafka partition consumers do not guarantee total chronological ordering during export. Evaluating out-of-order rows causes false-positive and inverted state crossing detections.

---

### `test_interleaved_instruments`
- **Edge Case Covered:** Input rows alternating between multiple tickers (`INFY`, `TCS`) across dates.
- **Test Fixture / Input:**
  ```csv
  date,instrument,close
  2026-09-01,INFY,1520.00
  2026-09-01,TCS,3900.00
  2026-09-02,INFY,1490.00
  2026-09-02,TCS,3910.00
  2026-09-03,INFY,1480.00
  2026-09-03,TCS,3890.00
  ```
  Rules: `r1` for `INFY` below 1500; `r2` for `TCS` below 3800
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Time series are strictly partitioned per ticker symbol; only `INFY` fires; `TCS` generates zero alerts:
  `2026-09-02 r1 INFY level below 1500`
- **Production Likelihood:** High
- **Real-World Production Context:** Financial market data feeds multiplex trades and quotes for thousands of symbols into a single consolidated tape. Price state machines and rolling moving average buffers must remain completely isolated to prevent cross-ticker data pollution.

---

### `test_trading_day_gaps`
- **Edge Case Covered:** Calendar gaps across weekends and extended market holidays.
- **Test Fixture / Input:**
  ```csv
  date,instrument,close
  2026-09-01,INFY,1520.00
  2026-09-18,INFY,1490.00
  ```
  Rule: `level below 1500`
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Consecutive CSV rows are evaluated as consecutive trading days; alert triggers on `stdout`:
  `2026-09-18 r1 INFY level below 1500`
- **Production Likelihood:** High
- **Real-World Production Context:** Financial exchanges close on weekends, national holidays, and unexpected market halts. Alert models evaluate sequential trading sessions; attempting calendar-day date math or forward-filling corrupts window durations.

---

### `test_duplicate_date_instrument_rows`
- **Edge Case Covered:** Multiple CSV entries for the same instrument and date, covering both identical and conflicting close prices.
- **Test Fixture / Input:**
  ```csv
  date,instrument,close
  2026-09-01,INFY,1520.00
  2026-09-01,INFY,1520.00
  2026-09-02,INFY,1510.00
  2026-09-02,INFY,1490.00
  ```
  Rule: `level below 1500`
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Identical rows are deduplicated silently; conflicting rows apply last-row-wins with a warning to `stderr`; alert fires on Day 2:
  `2026-09-02 r1 INFY level below 1500`
- **Production Likelihood:** Medium
- **Real-World Production Context:** Network retries, message re-deliveries, and exchange end-of-day price restatements regularly inject duplicate timestamps into data pipelines. The system must establish a deterministic resolution policy with audit logging.

---

## Part 3: Price Field Sanitization & Numerical Precision (`TestPriceCleaningAndPrecision`)

### `test_non_numeric_and_poison_values`
- **Edge Case Covered:** Price close tokens containing invalid tokens: `"NaN"`, `"inf"`, `"-inf"`, `""`, `"null"`, and `"N/A"`.
- **Test Fixture / Input:**
  ```csv
  date,instrument,close
  2026-09-01,INFY,1520.00
  2026-09-02,INFY,NaN
  2026-09-03,INFY,inf
  2026-09-04,INFY,null
  2026-09-05,INFY,N/A
  2026-09-06,INFY,
  2026-09-07,INFY,1490.00
  ```
  Rule: `level below 1500`
- **Expected Outcome & Pipeline Handling:** Skip + Warn (stderr). Poison rows are discarded with descriptive warnings written to `stderr`; valid rows are evaluated, triggering on `stdout`:
  `2026-09-07 r1 INFY level below 1500`
- **Production Likelihood:** High
- **Real-World Production Context:** Corrupted feed lines, unpopulated database columns, or unhandled serialization nulls can inject non-numeric tokens into pricing feeds. Allowing `NaN` into rolling moving average sums permanently contaminates subsequent calculations.

---

### `test_zero_and_negative_prices`
- **Edge Case Covered:** Non-positive close prices (`close <= 0.0`).
- **Test Fixture / Input:**
  ```csv
  date,instrument,close
  2026-09-01,INFY,1520.00
  2026-09-02,INFY,0.0
  2026-09-03,INFY,-150.00
  2026-09-04,INFY,1490.00
  ```
  Rule: `level below 1500`
- **Expected Outcome & Pipeline Handling:** Skip + Warn (stderr). Negative and zero prices are rejected with warnings logged to `stderr`; valid series triggers on `stdout`:
  `2026-09-04 r1 INFY level below 1500`
- **Production Likelihood:** Low
- **Real-World Production Context:** Equities, standard commodities, and FX rates cannot trade at or below zero under normal market operations (barring extraordinary historical anomalies like WTI Crude futures in April 2020). Negative quotes in equity feeds indicate upstream data transmission corruption.

---

### `test_floating_point_drift_on_identical_prices`
- **Edge Case Covered:** 25 consecutive trading days of identical close price (`100.00`) evaluated against `short: 5, long: 20` for both `above` and `below`.
- **Test Fixture / Input:** 25 consecutive rows of `2026-09-XX,INFY,100.00`. Rules: `ma_cross 5/20 above` and `ma_cross 5/20 below`.
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Exact decimal cross-multiplication guarantees zero floating-point drift; stdout remains completely silent (0 alerts).
- **Production Likelihood:** High
- **Real-World Production Context:** Standard IEEE 754 float division `sum / window` introduces micro-precision divergence (`100.00000000000001 != 100.0`). In flat markets, this causes AI-generated models to fire spurious false-positive crossover alerts on zero volatility.

---

## Part 4: Level Rule Semantics & Boundary Invariants (`TestLevelRuleSemantics`)

### `test_day_zero_invariant`
- **Edge Case Covered:** Instrument starts on Day 1 with a price already below the alert threshold level.
- **Test Fixture / Input:**
  ```csv
  date,instrument,close
  2026-09-01,INFY,1480.00
  ```
  Rule: `[{"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}]`
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Day 1 cannot trigger an alert because no preceding day exists to verify a crossing transition; stdout remains silent.
- **Production Likelihood:** High
- **Real-World Production Context:** Financial instruments frequently trade below a target price when a monitoring engine boots up. An alert rule requires a confirmed directional crossing event; entering the system in an already-breached state must not trigger a phantom alert.

---

### `test_sustained_state_fires_once`
- **Edge Case Covered:** Price crosses below threshold on Day 2 and remains below for Days 3, 4, and 5.
- **Test Fixture / Input:**
  ```csv
  date,instrument,close
  2026-09-01,INFY,1520.00
  2026-09-02,INFY,1490.00
  2026-09-03,INFY,1480.00
  2026-09-04,INFY,1470.00
  2026-09-05,INFY,1460.00
  ```
  Rule: `level below 1500`
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). The alert fires strictly on the day of the crossing (Day 2) and remains silent on all subsequent sustained days:
  `2026-09-02 r1 INFY level below 1500`
- **Production Likelihood:** High
- **Real-World Production Context:** In persistent trending markets, prices stay beyond thresholds for extended periods. A properly engineered alert engine fires once upon boundary penetration, avoiding noisy repeated alerts on every subsequent tick.

---

### `test_boundary_touch_versus_strict_cross`
- **Edge Case Covered:** Price landing exactly on the threshold level (`1500.00`) before penetrating vs rebounding.
- **Test Fixture / Input:**
  - Case A (Touch & Cross): `1510.00 -> 1500.00 -> 1490.00`
  - Case B (Touch & Rebound): `1510.00 -> 1500.00 -> 1510.00`
  Rule: `level below 1500`
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). In Case A, the alert triggers on Day 3 (transitioning from `>= 1500` to `< 1500`), NOT Day 2. In Case B, zero alerts trigger.
- **Production Likelihood:** High
- **Real-World Production Context:** Market prices often pin to round numbers or strike prices. Touching a level without crossing below it does not satisfy a `below` crossing condition.

---

### `test_oscillating_crossings`
- **Edge Case Covered:** Price oscillating back and forth across the threshold across multiple sessions.
- **Test Fixture / Input:**
  ```csv
  date,instrument,close
  2026-09-01,INFY,1510.00
  2026-09-02,INFY,1490.00
  2026-09-03,INFY,1520.00
  2026-09-04,INFY,1485.00
  ```
  Rule: `level below 1500`
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Alert engine re-arms upon crossing back above, firing on every valid downward crossing:
  `2026-09-02 r1 INFY level below 1500`
  `2026-09-04 r1 INFY level below 1500`
- **Production Likelihood:** High
- **Real-World Production Context:** Range-bound markets produce mean-reverting price action where prices repeatedly cross key psychological barriers. The engine state machine must accurately reset and capture each discrete crossing.

---

## Part 5: Moving Average Cross Semantics & Window Invariants (`TestMACrossSemantics`)

### `test_insufficient_warmup_window`
- **Edge Case Covered:** Price history containing fewer trading days than required by the long window (19 days of data for `long: 20`).
- **Test Fixture / Input:** 19 trading days of price rows. Rule: `[{"id": "r1", "instrument": "TCS", "type": "ma_cross", "short": 5, "long": 20, "direction": "above"}]`.
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Moving average evaluation safely defers without raising `IndexError`; stdout remains silent.
- **Production Likelihood:** High
- **Real-World Production Context:** Recently listed instruments (IPOs) or short observation intervals do not have sufficient historical depth to compute rolling indicators. Calculations must defer gracefully until full sample sizes are acquired.

---

### `test_exact_boundary_off_by_one`
- **Edge Case Covered:** Earliest mathematically valid crossover evaluation day (Day index $L-1$ baseline vs Day index $L$ cross).
- **Test Fixture / Input:** 20 trading days of flat price 100.00, followed by Day 21 jumping to 200.00 for `short: 5, long: 20, direction: "above"`.
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Day 20 (index 19) establishes the first valid long SMA baseline; Day 21 (index 20) is the first day capable of observing a transition from Day 20. Alert fires on Day 21:
  `2026-09-21 r1 TCS ma_cross 5/20 above`
- **Production Likelihood:** High
- **Real-World Production Context:** The classic AI failure mode on moving averages is attempting to evaluate crossover conditions on day index $L-1$ by assuming day $L-2$ had an SMA of 0. Day $L-1$ only establishes the initial baseline; Day $L$ (the $L+1$-th session) is the earliest possible crossing day.

---

### `test_both_directions`
- **Edge Case Covered:** Bilateral verification of both Golden Cross (`above`) and Death Cross (`below`) crossing rules.
- **Test Fixture / Input:** 20 trading days of price 100.00 followed by Day 21 dropping to 50.00 for `direction: "below"`.
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Short moving average crosses cleanly below long moving average on Day 21, firing to `stdout`:
  `2026-09-21 r_below TCS ma_cross 5/20 below`
- **Production Likelihood:** High
- **Real-World Production Context:** Quantitative trend-following models rely on Golden Crosses for momentum entry and Death Crosses for protective liquidation. Symmetrical mathematical handling across both directions is mandatory.

---

### `test_invalid_window_configuration`
- **Edge Case Covered:** Invalid window parameters where `short >= long` (e.g. `short: 20, long: 5` or `short: 5, long: 5`) or non-positive window values.
- **Test Fixture / Input:** `[{"id": "r1", "instrument": "TCS", "type": "ma_cross", "short": 20, "long": 5, "direction": "above"}]`.
- **Expected Outcome & Pipeline Handling:** Fatal (exit != 0). Tool rejects misconfigured rules immediately with exit code 1 and writes diagnostic errors to `stderr`.
- **Production Likelihood:** Medium
- **Real-World Production Context:** Inverted configuration parameters are common human errors in quant configurations. Executing an inverted crossover rule produces opposite market signals, risking major financial misallocations.

---

## Part 6: Rule Parsing, Exit Codes & Deterministic CLI Output (`TestRuleValidationAndCLIOutput`)

### `test_invalid_rules_json`
- **Edge Case Covered:** Malformed rules files: non-list root structure (`{}`), empty JSON file, or missing schema fields (`direction`).
- **Test Fixture / Input:**
  - Case 1: Root object `{"not": "a list"}`
  - Case 2: Missing field `[{"id": "r1", "instrument": "INFY", "type": "level", "level": 1500}]`
- **Expected Outcome & Pipeline Handling:** Fatal (exit != 0). Tool halts with non-zero exit code and writes clear diagnostic errors to `stderr`.
- **Production Likelihood:** Medium
- **Real-World Production Context:** Configuration deployment failures or syntax corruption during automated CI/CD pipeline rollout can deliver malformed rule definitions. The engine must reject invalid configurations decisively.

---

### `test_deterministic_sort_ordering`
- **Edge Case Covered:** Multiple alerts triggering on the same date across different rule IDs (`r10` and `r2`).
- **Test Fixture / Input:** Rules `r2` (level 1490) and `r10` (level 1500) both crossing below on `2026-09-02`.
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Primary sort orders by date ascending; secondary sort orders by rule ID string ascending (`r10` before `r2`):
  `2026-09-02 r10 INFY level below 1500`
  `2026-09-02 r2 INFY level below 1490`
- **Production Likelihood:** High
- **Real-World Production Context:** Large market dislocations trigger multiple alert rules simultaneously. Without deterministic compound sorting (date ASC, rule_id ASC), output ordering depends on arbitrary hash table iteration, breaking regression comparisons.

---

### `test_silent_output_on_no_triggers`
- **Edge Case Covered:** Valid price data where zero alerting conditions are satisfied.
- **Test Fixture / Input:** Price series trending upwards (`1520.00 -> 1530.00`) against rule `below 1500`.
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Tool exits with code 0 and writes zero bytes to `stdout`.
- **Production Likelihood:** High
- **Real-World Production Context:** Standard Unix CLI tools follow the Rule of Silence: when a tool has nothing to say, it should say nothing. Downstream monitoring scripts treat unexpected stdout text as actionable alert events.

---

### `test_exact_cli_line_format`
- **Edge Case Covered:** Character-for-character conformance with the assessment build brief sample output.
- **Test Fixture / Input:**
  ```csv
  date,instrument,close
  2026-09-01,INFY,1520.50
  2026-09-01,TCS,3890.00
  2026-09-02,INFY,1534.10
  2026-09-02,TCS,3902.25
  2026-09-03,INFY,1498.00
  ```
  Rule: `[{"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}]`
- **Expected Outcome & Pipeline Handling:** Decide & Document (exit 0). Produces exact string match:
  `2026-09-03 r1 INFY level below 1500`
- **Production Likelihood:** High
- **Real-World Production Context:** Downstream automated execution gateways, alerting bots, and regex scrapers depend on strict token formatting. Minor whitespace or casing discrepancies break automated downstream consumers.
