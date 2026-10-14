# Prompts Log & Assistant Usage Summary
## Wissen Technology: Price Alert Tool

> **Context:** This document maintains an ongoing, chronological record of all prompts provided by the user during the development of the Price Alert Tool. It directly supports the assessment submission requirement:
> *"Include a README of at most one page: how to run it, how you used the assistant (the prompts in brief), what the assistant got wrong, and what you changed and why."*

---

### Prompt History & Audit Log

#### Prompt #1: Problem Interpretation & Agent Guidelines
- **Timestamp:** 2026-10-14 14:50 IST
- **User Prompt (Summary):**
  Analyze the attached assessment brief PDF ("Wissen Technology Campus Assessment – Price Alert Tool") and generate two comprehensive documentation files: [Problem.md](file:///c:/Users/Shrey/Projects/Wissen%20Technology/Problem.md) and [agents.md](file:///c:/Users/Shrey/Projects/Wissen%20Technology/agents.md) containing all relevant specifications, technical interpretations, architecture, and edge cases.
- **Key Deliverables Produced:**
  1. `Problem.md`: Full decomposition of inputs (CSV/JSON), mathematical crossing definitions (Level and MA Cross), output format specifications, and a catalog of unseen edge cases.
  2. `agents.md`: Architectural blueprint (Standard Library, zero-dependency), known AI traps/hallucinations (e.g., false MA crosses on Day $L$), test matrix, and the 6-minute presentation script.
- **Review & Validation Notes:**
  - Verified exact match of alert format strings with the brief sample.
  - Highlighted critical mathematical boundary definitions (e.g. Day $L$ vs Day $L+1$ for MA cross).

---

#### Prompt #2: Prompt Summary Logging Protocol
- **Timestamp:** 2026-10-14 15:06 IST
- **User Prompt (Summary):**
  Create a dedicated Markdown file to store summaries of all prompts given to the assistant by the user, and maintain/update this file continuously after each subsequent prompt.
- **Key Deliverables Produced:**
  - Created [prompts.md](file:///c:/Users/Shrey/Projects/Wissen%20Technology/prompts.md) to serve as the live audit log for prompts, assistant outputs, and evaluation notes.
- **Review & Validation Notes:**
  - Logged Prompts #1 and #2.
  - Established rule to append to this document on all future user turns.

---

#### Prompt #3: Repository Skeleton & Starter Stubs Setup
- **Timestamp:** 2026-10-14 15:18 IST
- **User Prompt (Summary):**
  Initialize only the lightweight base repository structure and empty starter files without implementation, algorithms, dummy data, or external tooling. Enforce standard library constraints and minimal design ("Volume of code earns nothing").
- **Key Deliverables Produced:**
  1. `.gitignore`: Standard Python and test ignore patterns (`__pycache__`, `.pytest_cache`, virtualenvs).
  2. `README.md`: Structured skeleton with mandatory evaluation sections (*How to run it*, *How you used the assistant*, *What the assistant got wrong*, *What was changed and why*).
  3. `alerts.py`: Clean executable CLI stub with module docstring specifying signature and scope.
  4. `tests/test_alerts.py`: Clean test suite stub with module docstring outlining planned test coverage categories.
- **Review & Validation Notes:**
  - Kept zero third-party dependencies.
  - Refrained from generating premature algorithms, dummy data, or build bloat.

---

#### Prompt #4: Production-Grade Test Suite Implementation (TDD Phase 1)
- **Timestamp:** 2026-10-14 20:16 IST
- **User Prompt (Summary):**
  Act as Principal Software Engineer in Test and write the complete, production-grade test suite in `tests/test_alerts.py` using Python's built-in `unittest` framework across 6 atomic tasks. Enforce zero third-party dependencies, purely decoupled execution via in-memory/tempfile helpers, and mandatory structured docstrings (`Edge Case Covered`, `Pipeline Handling`, `Production Likelihood`) for every single test method. Do not touch `alerts.py` business logic.
- **Key Deliverables Produced:**
  - Implemented 24 comprehensive test methods across 6 test classes in [tests/test_alerts.py](file:///c:/Users/Shrey/Projects/Wissen%20Technology/tests/test_alerts.py):
    1. `TestFileStructureAndEncoding` (UTF-8 BOM, mixed line endings, header variations, missing headers, ragged/blank rows).
    2. `TestDateAndSequenceEdgeCases` (chronological disarray, multi-ticker isolation, trading day gaps, duplicate rows).
    3. `TestPriceCleaningAndPrecision` (poison tokens/nulls, zero/negative prices, float precision drift on flat prices).
    4. `TestLevelRuleSemantics` (Day 0 invariant, sustained state firing once, boundary touch vs strict cross, oscillating crossings).
    5. `TestMACrossSemantics` (insufficient warm-up window, exact off-by-one Day 20 vs Day 21 boundary, golden/death cross directions, invalid window configuration).
    6. `TestRuleValidationAndCLIOutput` (invalid rules JSON, deterministic date ASC / rule_id ASC ordering, silent output on no triggers, exact CLI output format).
  - Executed test discovery: `Ran 24 tests in 0.055s`.
- **Review & Validation Notes:**
  - Verified 100% adherence to standard library only (`unittest`, `io`, `tempfile`, `sys`, `json`, `csv`, `pathlib`).
  - Strict compliance with TDD "Red" phase: tests execute cleanly and fail predictably against the empty CLI stub.

---

#### Prompt #5: Engine Implementation & Final Documentation (TDD Phase 2)
- **Timestamp:** 2026-10-14 20:24 IST
- **User Prompt (Summary):**
  Act as Senior Python Systems Engineer and implement `alerts.py` to make all 24 unit tests in `tests/test_alerts.py` pass cleanly. Enforce zero third-party dependencies, exact CLI contract, strict stream separation (`stdout` for triggers, `stderr` for warnings, non-zero exit for fatal errors), and single-file design without bloat. Complete `README.md` under 1 page with required sections and update `prompts.md`.
- **Key Deliverables Produced:**
  1. [alerts.py](file:///c:/Users/Shrey/Projects/Wissen%20Technology/alerts.py): Complete single-file implementation with:
     - `parse_and_validate_rules`: JSON schema enforcement, mandatory keys, positive windows, and `short < long` validation.
     - `parse_and_clean_prices`: UTF-8 BOM stripping, universal newline normalization (CRLF/LF/CR), ragged row handling, poison token filtering (`NaN`, `inf`, `null`), duplicate date resolution (identical deduped, conflicting last-wins), and chronological sorting per ticker.
     - `evaluate_rules`: Stateful Level crossing evaluation (`prev >= level` to `curr < level`) and exact-precision Moving Average crossover engine using integer cross-multiplication with day $L+1$ boundary gating.
     - `main`: Deterministic collation and sorting (`date` ASC, `rule_id` ASC) and clean CLI stream handling.
  2. [README.md](file:///c:/Users/Shrey/Projects/Wissen%20Technology/README.md): Populated strictly under 1 page covering execution, prompts used, AI errors (MA warmup off-by-one, IEEE 754 float drift, newline parsing), and rationale for changes.
  3. [prompts.md](file:///c:/Users/Shrey/Projects/Wissen%20Technology/prompts.md): Updated audit log for Prompt #5.
- **Review & Validation Notes:**
  - Ran test suite: `Ran 24 tests in 0.075s - OK`. All 24 tests pass cleanly with 0 failures and 0 errors.

---

#### Prompt #6: Comprehensive Test Specification & Anomaly Matrix
- **Timestamp:** 2026-10-14 20:47 IST
- **User Prompt (Summary):**
  Act as Principal QA Architect and Documentation Engineer to generate `TEST_CASES.md` mapping all 24 unit tests across the 6 canonical test classes from `tests/test_alerts.py`. Provide a top-level summary matrix and detailed test case subsections specifying edge cases covered, test fixtures, pipeline handling behavior, likelihood ratings, and real-world financial market context. Update `prompts.md`.
- **Key Deliverables Produced:**
  - Created [TEST_CASES.md](file:///c:/Users/Shrey/Projects/Wissen%20Technology/TEST_CASES.md):
    - Master Test Matrix mapping all 24 unit tests to their pipeline policy and production likelihood.
    - Uniformly structured test specifications across Part 1 (`TestFileStructureAndEncoding`), Part 2 (`TestDateAndSequenceEdgeCases`), Part 3 (`TestPriceCleaningAndPrecision`), Part 4 (`TestLevelRuleSemantics`), Part 5 (`TestMACrossSemantics`), and Part 6 (`TestRuleValidationAndCLIOutput`).
  - Updated [prompts.md](file:///c:/Users/Shrey/Projects/Wissen%20Technology/prompts.md) with Prompt #6 log entry.
- **Review & Validation Notes:**
  - Verified 1:1 mapping with test implementations in `tests/test_alerts.py`.
  - Confirmed inclusion of all fixtures, failure modes, and architectural justifications.

---
