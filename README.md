# Price Alert Tool

A standalone, zero-dependency command-line utility for technical market monitoring. Ingests daily price series from CSV, evaluates stateful `level` and `ma_cross` alert rules from JSON, and outputs triggered events in strict deterministic order.

---

## How to run it

**Prerequisites:** Python 3.8+ (Standard Library only; no third-party packages needed).

```bash
# Execute CLI with bundled sample dataset
python alerts.py sample_data/sample_prices.csv sample_data/sample_rules.json

# Execute CLI with custom files
python alerts.py <prices.csv> <rules.json>

# Execute Test Suite (24 production-grade unit & edge-case tests)
python -m unittest discover -s tests -p "test_*.py"
```

---

## How you used the assistant (the prompts in brief)

1. **Problem Modeling & Trap Mapping:** Analyzed the build brief to define data structures, crossing semantics, and catalog unseen market data anomalies into `Problem.md` and `agents.md`.
2. **Minimal Architecture Scaffolding:** Set up a clean, zero-bloat repository stub without premature algorithms or third-party libraries.
3. **Hostile TDD Test Suite Generation:** Instructed the assistant to author 24 comprehensive unit tests in `tests/test_alerts.py` covering encodings (UTF-8 BOM), corrupt feeds (poison NaNs, ragged rows), boundary touches, and SMA warm-up invariants.
4. **Engine Implementation & Stream Isolation:** Guided the assistant to build `alerts.py` enforcing strict streams separation (clean alert lines on `stdout`, telemetry/warnings on `stderr`, fatal error codes on corrupt configs).
5. **Realistic Sample Fixture Synthesis:** Created reproducible sample fixtures with embedded real-world anomalies (out-of-order dates, interleaved tickers, duplicate timestamps, poison nulls).

---

## What the assistant got wrong

1. **The Moving Average Warm-Up Off-By-One Trap:**
   The assistant initially attempted to evaluate crossover conditions on day index `long - 1` (the very first day the long window completes), assuming `prev_long_ma = 0` or uninitialized. This triggered a **false-positive alert on the first window-completion day**. A true crossover requires a valid historical transition; day index `long - 1` only establishes the baseline, making day index `long` (the `long + 1`-th trading day) the earliest mathematically evaluatable crossing day.
2. **IEEE 754 Floating-Point Drift:**
   Evaluating moving averages via `sum / window` caused micro-precision rounding noise (`100.00000000000001` vs `100.0`) on flat, 25-day identical price series, falsely triggering crossover signals on zero volatility.
3. **CSV Line-Ending Fragility:**
   Standard `csv.reader` raised `_csv.Error: new-line character seen in unquoted field` when processing feeds containing isolated carriage returns (`\r`).

---

## What was changed and why

1. **Exact Cross-Multiplication & Decimal Ingestion:**
   Parsed prices as `Decimal` and replaced division with integer cross-multiplication (`short_sum * long` vs `long_sum * short`). This completely eliminated floating-point drift on constant series while retaining $O(1)$ rolling comparisons.
2. **Explicit Warm-Up Boundary Guard (`t >= long`):**
   Gated the MA loop to start strictly at index `long`. Day $t-1$ and day $t$ both possess complete windows, guaranteeing only legitimate historical transitions trigger alerts.
3. **Two-Tier Resilience Strategy:**
   Partitioned errors into:
   - *Fatal (Exit Code 1):* Unparseable JSON, missing required headers (`date`, `close`), or invalid parameters (`short >= long`).
   - *Recoverable (Skip + Warn to STDERR):* Poison tokens (`NaN`, `null`), ragged rows, non-positive prices (`<= 0.0`), and conflicting duplicate dates (resolved via last-row-wins).
4. **Strict Boundary Penetration Invariant:**
   Defined level crossing as transitioning from `>= level` to `< level` (for `below`), ensuring prices that merely touch a threshold without penetrating it do not emit false alerts.
