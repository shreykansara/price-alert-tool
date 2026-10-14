# Wissen Technology - Campus Assessment: Price Alert Tool
## Problem Statement & Technical Interpretation

---

### 1. Executive Summary

- **Organization:** Wissen Technology
- **Assessment Track:** Campus Assessment – Build Brief (Shortlisted Candidates)
- **Project Name:** Price Alert Tool
- **Submission Deadline:** 14:00 tomorrow (Hard deadline; late submissions are disqualified)
- **Submission Format:** Zip archive or Git repository link delivered to the Wissen coordinator
- **Core Directive:** Build a standalone, robust command-line interface (CLI) tool that ingests historical daily prices for multiple financial instruments from a CSV file, applies configurable alerting rules from a JSON file, and outputs detected alert events to standard output (`stdout`) in a strictly ordered, deterministic format.
- **Evaluation Philosophy:**
  > *"A polished tool you cannot explain scores below a rough one you understand completely. Volume of code earns nothing. What we evaluate is how you verified the result and how well you understand what you submit."*

---

### 2. System Inputs Specification

The application accepts two mandatory input files via command-line arguments:

```bash
python alerts.py <prices.csv> <rules.json>
```

#### 2.1 Prices File (`prices.csv`)
- **Format:** Comma-Separated Values (CSV).
- **Header:** `date,instrument,close`
- **Granularity:** One record per instrument per trading day.
- **Crucial Ingestion Characteristics:**
  1. **Unordered Dates:** Dates in the CSV may be out of chronological order (globally across instruments, or even locally for a single instrument).
  2. **Interleaved Instruments:** Multiple tickers (e.g., `INFY`, `TCS`, `RELIANCE`) are interleaved within the same file.
  3. **Trading Day Semantics:** Data only exists for active trading days. Weekends, public holidays, and unscheduled exchange closures are omitted. Calculations must operate on sequential *trading days*, never calendar days.

**Sample `prices.csv`:**
```csv
date,instrument,close
2026-09-01,INFY,1520.50
2026-09-01,TCS,3890.00
2026-09-02,INFY,1534.10
2026-09-02,TCS,3902.25
2026-09-03,INFY,1498.00
```

#### 2.2 Rules File (`rules.json`)
- **Format:** JSON array containing zero or more rule definitions.
- **Structure:**
  - Common attributes:
    - `id` (`string`): Unique rule identifier (e.g., `"r1"`, `"r2"`).
    - `instrument` (`string`): Target ticker symbol matching the CSV entries (e.g., `"INFY"`).
    - `type` (`string`): Type of alert (`"level"` or `"ma_cross"`).
    - `direction` (`string`): Crossing trajectory (`"above"` or `"below"`).
  - Type-specific attributes:
    - For `type == "level"`:
      - `level` (`number`): Numerical price threshold.
    - For `type == "ma_cross"`:
      - `short` (`integer`): Window size for the short moving average ($S$).
      - `long` (`integer`): Window size for the long moving average ($L$, where $L > S$).

**Sample `rules.json`:**
```json
[
  {
    "id": "r1",
    "instrument": "INFY",
    "type": "level",
    "direction": "below",
    "level": 1500
  },
  {
    "id": "r2",
    "instrument": "TCS",
    "type": "ma_cross",
    "short": 5,
    "long": 20,
    "direction": "above"
  }
]
```

---

### 3. Mathematical & Algorithmic Semantics of Alert Rules

#### 3.1 Rule Type: `level` (Price Level Crossing)
- **Definition from Brief:**
  > *"A level rule fires on the first day the close crosses the level in the given direction (it was on the other side the previous day)."*
- **Mathematical Formulation:**
  Let $P_t$ be the close price of instrument $I$ on trading day $t$ ($t \ge 1$), and let $K$ be the threshold `level`.
  
  - **Direction: `below`:**
    - Firing Condition:
      $$P_{t-1} > K \quad \text{and} \quad P_t < K$$
      *(Alternative boundary consideration: $P_{t-1} \ge K$ and $P_t < K$, or $P_{t-1} > K$ and $P_t \le K$ — see Edge Cases).*
    - **Key Behavioral Property:** If $P_t < K$ and on subsequent days $P_{t+1} < K$, the rule does **not** fire again. It only fires on the *transition day* (crossing from the other side).
  
  - **Direction: `above`:**
    - Firing Condition:
      $$P_{t-1} < K \quad \text{and} \quad P_t > K$$
      *(Or $P_{t-1} \le K$ and $P_t > K$).*
  
  - **Initial Day ($t = 0$):**
    On the very first available trading day for an instrument, there is no $P_{t-1}$. Therefore, an instrument **cannot cross** a level on day 0, because it was not verified to be "on the other side the previous day".

#### 3.2 Rule Type: `ma_cross` (Moving Average Crossover)
- **Definition from Brief:**
  > *"An ma_cross rule fires on the day the short moving average crosses the long one in the given direction. Moving averages need a full window of days before they are defined."*
- **Mathematical Formulation:**
  - Let $S$ = `short` window, $L$ = `long` window (with $1 \le S < L$).
  - Simple Moving Average (SMA) on trading day $t$:
    $$SMA_k(t) = \frac{1}{k} \sum_{i=0}^{k-1} P_{t-i}$$
  - **Window Prerequisite:**
    - $SMA_S(t)$ is defined only when $t \ge S$ trading days exist.
    - $SMA_L(t)$ is defined only when $t \ge L$ trading days exist.
    - Both MAs are defined simultaneously if and only if $t \ge L$.
  
  - **Crossover Semantics & First Firing Day:**
    - To determine if a crossover occurred on trading day $t$, we must observe the relative positioning on day $t$ compared to the prior day $t-1$:
      - **Direction: `above` (Golden Cross):**
        $$SMA_S(t-1) \le SMA_L(t-1) \quad \text{and} \quad SMA_S(t) > SMA_L(t)$$
      - **Direction: `below` (Death Cross):**
        $$SMA_S(t-1) \ge SMA_L(t-1) \quad \text{and} \quad SMA_S(t) < SMA_L(t)$$
    - **Critical Timing Edge Case:**
      On day $L$ (the first day the long window is satisfied), $SMA_L(L)$ is defined, but $SMA_L(L-1)$ was **undefined** because day $L-1$ had only $L-1$ data points. Therefore, day $L+1$ is the first day where both day $t$ and day $t-1$ have defined values for both moving averages!

---

### 4. Output Specification & Determinism

#### 4.1 Output Syntax
Output must be printed to `stdout` with exactly one line per triggered alert.

| Rule Type | Output Template | Example |
| :--- | :--- | :--- |
| **`level`** | `<date> <rule_id> <instrument> level <direction> <level>` | `2026-09-03 r1 INFY level below 1500` |
| **`ma_cross`** | `<date> <rule_id> <instrument> ma_cross <short>/<long> <direction>` | `2026-09-24 r2 TCS ma_cross 5/20 above` |

*(Note: In `ma_cross`, window sizes are represented as `<short>/<long>` without spaces around the slash, followed by `<direction>`)*.

#### 4.2 Ordering & Sorting Constraints
- **Primary Sort:** Ascending chronological order by `date` (`YYYY-MM-DD`).
- **Secondary Sort (Tie-breaking):** Ascending alphanumeric order by `rule_id` (e.g., `r1` before `r2`).
- **Silent Days:** If on any given trading day no rules fire, the tool prints **nothing** for that day (no empty lines, no headers, no log messages).

---

### 5. Assessment Constraints & Evaluation Criteria

#### 5.1 Operating Rules
1. **Clean Download & Single Command Run:**
   - Must run directly from a fresh clone/download:
     `python alerts.py prices.csv rules.json`
   - Must document explicit runtime requirements and installation commands (if any).
   - Zero external third-party dependencies (relying exclusively on the Python Standard Library) is strongly advised to prevent environment mismatches.
2. **Test-First Evaluation:**
   - The Wissen evaluation panel will **read the test suite before looking at the implementation code**.
   - Tests must cover realistic financial market anomalies and edge cases.
3. **One-Page README:**
   - Strict length limit: at most one page.
   - Mandatory sections:
     1. How to run the tool.
     2. How the AI assistant was utilized (prompts summarized).
     3. What the AI assistant got wrong.
     4. What modifications were implemented, along with technical rationale.
4. **Candidate Presentation Structure:**
   - **6 Minutes Presentation:**
     - Overview of system design and functionality.
     - Verification methodology and test coverage.
     - Deep dive into one specific error/misconception produced by the AI assistant.
   - **6 Minutes Interactive Evaluation:**
     - The panel executes the candidate's tool against their own secret, unseen dataset containing hostile edge cases.

---

### 6. Catalog of Unseen Edge Cases (Evaluator Trap Scenarios)

The evaluation brief explicitly states:
> *"Whether the tool runs correctly on a prices file we bring, which will contain conditions you have not seen."*

Below is the exhaustive matrix of edge cases that must be anticipated and tested:

| Category | Specific Scenario | Expected Behavior |
| :--- | :--- | :--- |
| **Temporal / Ordering** | CSV rows sorted reverse-chronologically or randomly shuffled | Ingest and sort chronologically per instrument before processing. |
| **Temporal / Ordering** | Gaps in trading days (weekends, 4-day market holiday, year boundaries) | Treat consecutive rows as consecutive trading days for MA windows; do not interpolate missing dates. |
| **Data Partitioning** | Multiple instruments interleaved in random sequence | Segregate prices by instrument; state/moving averages for `INFY` must not bleed into `TCS`. |
| **Boundary Conditions** | Price touches level exactly ($P_t = \text{level}$) | Define exact inequality semantics ($<$ vs $\le$). Level crossing requires crossing from one strict side to the other. |
| **Boundary Conditions** | Moving averages touch exactly ($SMA_S = SMA_L$) before separating | Explicitly handle equality transitions so no phantom alerts fire. |
| **Data Sufficiency** | Total trading days for an instrument $< L$ (long MA window) | No `ma_cross` rules fire; no crashes, index out of bounds, or division by zero. |
| **Data Sufficiency** | Empty CSV file, or CSV containing only headers | Silent exit with code 0 (or clean handled error), producing no alerts. |
| **Rules Edge Cases** | Rules file defines an instrument not present in the CSV | Silently ignore or safely skip without crashing. |
| **Rules Edge Cases** | Multiple rules targeting the same instrument fire on the same date | Collate all fired alerts and sort strictly by `rule_id`. |
| **Rules Edge Cases** | Multiple rules targeting different instruments fire on the same date | Group by date, sort by `rule_id` regardless of instrument. |
| **Floating-Point Precision** | Differences like `1500.0000000000002` vs `1500.0` causing false crossovers | Use strict decimal rounding or epsilon tolerance (`1e-9`) on SMA comparisons. |
| **Data Hygiene** | Leading/trailing whitespace in CSV headers or values | Strip whitespace during parsing. |
| **Malformed Data** | Negative prices, zero prices, scientific notation | Handle valid numeric values smoothly; fail gracefully on non-numeric close values. |
