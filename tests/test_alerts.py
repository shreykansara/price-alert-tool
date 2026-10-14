"""
tests/test_alerts.py - Production-grade test suite for Price Alert Tool.

Standard library only: unittest, io, tempfile, sys, json, csv, pathlib.
Tests cover file structure & encoding, data sequence & isolation,
price sanitization & numerical precision, level crossing semantics,
moving average cross window invariants, and CLI output determinism.
"""

import csv
import io
import json
import pathlib
import sys
import tempfile
import unittest

# Ensure project root is in sys.path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def run_pipeline(prices_content=None, rules_content=None, custom_args=None):
    """
    Execute alerts.py in-process with isolated I/O and CLI arguments.
    Returns:
        tuple: (exit_code: int, stdout_str: str, stderr_str: str)
    """
    created_files = []
    try:
        if custom_args is not None:
            cmd_args = list(custom_args)
        else:
            cmd_args = []
            if prices_content is not None:
                is_bytes = isinstance(prices_content, bytes)
                mode = "wb" if is_bytes else "w"
                encoding = None if is_bytes else "utf-8"
                tf_p = tempfile.NamedTemporaryFile(
                    mode, delete=False, suffix=".csv", encoding=encoding
                )
                tf_p.write(prices_content)
                tf_p.close()
                created_files.append(tf_p.name)
                cmd_args.append(tf_p.name)

            if rules_content is not None:
                if isinstance(rules_content, (dict, list)):
                    payload = json.dumps(rules_content)
                    mode = "w"
                    encoding = "utf-8"
                elif isinstance(rules_content, bytes):
                    payload = rules_content
                    mode = "wb"
                    encoding = None
                else:
                    payload = str(rules_content)
                    mode = "w"
                    encoding = "utf-8"

                tf_r = tempfile.NamedTemporaryFile(
                    mode, delete=False, suffix=".json", encoding=encoding
                )
                tf_r.write(payload)
                tf_r.close()
                created_files.append(tf_r.name)
                cmd_args.append(tf_r.name)

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        old_argv = sys.argv

        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        sys.argv = ["alerts.py"] + cmd_args

        exit_code = 0
        try:
            # Clear cached module to ensure isolated execution per run
            sys.modules.pop("alerts", None)
            import alerts

            if hasattr(alerts, "main"):
                alerts.main()
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else (1 if exc.code else 0)
        except Exception as exc:
            exit_code = 1
            stderr_capture.write(f"Unhandled Exception: {exc}\n")
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            sys.argv = old_argv

        return exit_code, stdout_capture.getvalue(), stderr_capture.getvalue()
    finally:
        for fpath in created_files:
            try:
                pathlib.Path(fpath).unlink(missing_ok=True)
            except OSError:
                pass


# =====================================================================
# TASK 1: File Structure, Encoding & Header Robustness
# =====================================================================
class TestFileStructureAndEncoding(unittest.TestCase):
    """Verifies file ingestion resilience across encodings, separators, and headers."""

    def test_utf8_bom_handling(self):
        """
        - Edge Case Covered: Prices CSV prefixed with UTF-8 Byte Order Mark (\ufeff).
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Common export artifact from Microsoft Excel on Windows.
        """
        bom_csv = (
            "\ufeffdate,instrument,close\n"
            "2026-09-01,INFY,1520.50\n"
            "2026-09-02,INFY,1490.00\n"
        ).encode("utf-8")
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=bom_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        self.assertIn("2026-09-02 r1 INFY level below 1500", stdout.strip())

    def test_mixed_line_endings(self):
        """
        - Edge Case Covered: Ingestion of mixed CRLF, LF, and CR line endings within a single CSV.
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Cross-platform pipelines and heterogeneous data sources.
        """
        mixed_csv = (
            "date,instrument,close\r\n"
            "2026-09-01,INFY,1520.50\r"
            "2026-09-02,INFY,1490.00\n"
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=mixed_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        self.assertNotIn("\r", stdout)
        self.assertIn("2026-09-02 r1 INFY level below 1500", stdout.strip())

    def test_header_variations_and_extra_columns(self):
        """
        - Edge Case Covered: CSV headers with surrounding whitespace, mixed casing, and superfluous columns.
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Unstandardized external market vendor formats.
        """
        varied_csv = (
            " Date , CLOSE ,instrument,volume,extra \n"
            "2026-09-01,1520.50,INFY,10000,foo\n"
            "2026-09-02,1490.00,INFY,20000,bar\n"
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=varied_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        self.assertIn("2026-09-02 r1 INFY level below 1500", stdout.strip())

    def test_missing_required_headers(self):
        """
        - Edge Case Covered: CSV input missing essential columns (e.g., missing 'close' or 'date').
        - Pipeline Handling: Fatal (exit != 0)
        - Production Likelihood: Medium - Truncated, schema-mutated, or corrupted input feeds.
        """
        bad_csv = (
            "date,instrument\n"
            "2026-09-01,INFY\n"
            "2026-09-02,INFY\n"
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=bad_csv, rules_content=rules)
        self.assertNotEqual(exit_code, 0)
        self.assertTrue(len(stderr.strip()) > 0, "Expected descriptive error on stderr")

    def test_ragged_and_blank_rows(self):
        """
        - Edge Case Covered: Completely blank rows, trailing whitespace rows, and ragged rows with missing fields.
        - Pipeline Handling: Skip + Warn (stderr)
        - Production Likelihood: High - Corrupted transmission buffers, network drops, and blank line artifacts.
        """
        ragged_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.50\n"
            "\n"
            "   \n"
            "2026-09-02,INFY\n"
            "2026-09-03,INFY,1490.00\n"
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=ragged_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Expected successful execution despite ragged rows: {stderr}")
        self.assertIn("2026-09-03 r1 INFY level below 1500", stdout.strip())
        self.assertTrue(len(stderr.strip()) > 0, "Expected warning for ragged rows on stderr")


# =====================================================================
# TASK 2: Ingestion, Chronology & Instrument Isolation
# =====================================================================
class TestDateAndSequenceEdgeCases(unittest.TestCase):
    """Verifies chronological reordering, multi-instrument segregation, and trading day rules."""

    def test_chronological_disarray(self):
        """
        - Edge Case Covered: Input rows supplied in random or reverse chronological order.
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Distributed databases and multi-threaded feed collectors.
        """
        shuffled_csv = (
            "date,instrument,close\n"
            "2026-09-03,INFY,1480.00\n"
            "2026-09-01,INFY,1520.00\n"
            "2026-09-02,INFY,1490.00\n"
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=shuffled_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        lines = [line.strip() for line in stdout.strip().splitlines() if line.strip()]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "2026-09-02 r1 INFY level below 1500")

    def test_interleaved_instruments(self):
        """
        - Edge Case Covered: Alternating rows for multiple tickers without cross-talk between state machines.
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Multi-asset consolidated market feeds.
        """
        interleaved_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.00\n"
            "2026-09-01,TCS,3900.00\n"
            "2026-09-02,INFY,1490.00\n"
            "2026-09-02,TCS,3910.00\n"
            "2026-09-03,INFY,1480.00\n"
            "2026-09-03,TCS,3890.00\n"
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500},
            {"id": "r2", "instrument": "TCS", "type": "level", "direction": "below", "level": 3800},
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=interleaved_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        lines = [line.strip() for line in stdout.strip().splitlines() if line.strip()]
        self.assertEqual(lines, ["2026-09-02 r1 INFY level below 1500"])

    def test_trading_day_gaps(self):
        """
        - Edge Case Covered: Irregular calendar gaps (weekends and extended holidays) between trading rows.
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Standard financial calendar operating reality.
        """
        gapped_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.00\n"
            "2026-09-18,INFY,1490.00\n"
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=gapped_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        self.assertEqual(stdout.strip(), "2026-09-18 r1 INFY level below 1500")

    def test_duplicate_date_instrument_rows(self):
        """
        - Edge Case Covered: Multiple entries for identical ticker and date (identical deduplicated, conflicting last-wins).
        - Pipeline Handling: Decide & Document
        - Production Likelihood: Medium - Re-transmissions, message retries, and data provider corrections.
        """
        duplicate_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.00\n"
            "2026-09-01,INFY,1520.00\n"  # Identical duplicate -> silent deduplication
            "2026-09-02,INFY,1510.00\n"
            "2026-09-02,INFY,1490.00\n"  # Conflicting duplicate -> last row wins (1490.00), warn stderr
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=duplicate_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        self.assertIn("2026-09-02 r1 INFY level below 1500", stdout.strip())
        self.assertTrue(len(stderr.strip()) > 0, "Expected warning for conflicting duplicate row on stderr")


# =====================================================================
# TASK 3: Price Field Sanitization & Numerical Precision
# =====================================================================
class TestPriceCleaningAndPrecision(unittest.TestCase):
    """Verifies numeric parsing, poison token dropping, and float precision stability."""

    def test_non_numeric_and_poison_values(self):
        """
        - Edge Case Covered: Non-numeric, null, infinite, and empty price tokens (NaN, inf, null, N/A).
        - Pipeline Handling: Skip + Warn (stderr)
        - Production Likelihood: High - Corrupted data stream tokens and unhandled database null values.
        """
        poison_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.00\n"
            "2026-09-02,INFY,NaN\n"
            "2026-09-03,INFY,inf\n"
            "2026-09-04,INFY,null\n"
            "2026-09-05,INFY,N/A\n"
            "2026-09-06,INFY,\n"
            "2026-09-07,INFY,1490.00\n"
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=poison_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        self.assertIn("2026-09-07 r1 INFY level below 1500", stdout.strip())
        self.assertTrue(len(stderr.strip()) > 0, "Expected warnings for poison price tokens on stderr")

    def test_zero_and_negative_prices(self):
        """
        - Edge Case Covered: Non-positive price values (close <= 0.0).
        - Pipeline Handling: Skip + Warn (stderr)
        - Production Likelihood: Low - Extreme anomalies or erroneous negative quote adjustments.
        """
        non_positive_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.00\n"
            "2026-09-02,INFY,0.0\n"
            "2026-09-03,INFY,-150.00\n"
            "2026-09-04,INFY,1490.00\n"
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=non_positive_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        self.assertIn("2026-09-04 r1 INFY level below 1500", stdout.strip())
        self.assertTrue(len(stderr.strip()) > 0, "Expected warnings for non-positive prices on stderr")

    def test_floating_point_drift_on_identical_prices(self):
        """
        - Edge Case Covered: 25 consecutive rows with identical price to test resistance to IEEE 754 precision drift.
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Floating-point round-off accumulation in moving average sums.
        """
        rows = ["date,instrument,close"]
        for day in range(1, 26):
            rows.append(f"2026-09-{day:02d},INFY,100.00")
        identical_csv = "\n".join(rows) + "\n"

        rules = [
            {"id": "r1", "instrument": "INFY", "type": "ma_cross", "short": 5, "long": 20, "direction": "above"},
            {"id": "r2", "instrument": "INFY", "type": "ma_cross", "short": 5, "long": 20, "direction": "below"},
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=identical_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        self.assertEqual(stdout.strip(), "", "Flat price series must never trigger false moving average cross")


# =====================================================================
# TASK 4: Level Rule Semantics & Boundary Invariants
# =====================================================================
class TestLevelRuleSemantics(unittest.TestCase):
    """Verifies price level threshold crossings, boundary contacts, and state persistence."""

    def test_day_zero_invariant(self):
        """
        - Edge Case Covered: Instrument begins day 1 already below threshold level.
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Assets starting below target value upon system initialization.
        """
        day_zero_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1480.00\n"
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=day_zero_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        self.assertEqual(stdout.strip(), "", "Day 1 cannot cross because no prior day exists")

    def test_sustained_state_fires_once(self):
        """
        - Edge Case Covered: Price crosses below level and remains below for consecutive subsequent days.
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Persistent directional market movements and trending conditions.
        """
        trending_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.00\n"
            "2026-09-02,INFY,1490.00\n"  # Crosses below 1500 -> Alert fires
            "2026-09-03,INFY,1480.00\n"  # Stays below -> No alert
            "2026-09-04,INFY,1470.00\n"  # Stays below -> No alert
            "2026-09-05,INFY,1460.00\n"  # Stays below -> No alert
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=trending_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        lines = [line.strip() for line in stdout.strip().splitlines() if line.strip()]
        self.assertEqual(lines, ["2026-09-02 r1 INFY level below 1500"])

    def test_boundary_touch_versus_strict_cross(self):
        """
        - Edge Case Covered: Price landing precisely on the threshold level (touching vs strict directional crossing).
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Prices pinning to psychological round numbers and strike thresholds.
        """
        # Case A: 1510 -> 1500 -> 1490. Cross below fires on Day 3 (from >= 1500 to < 1500).
        touch_and_cross_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1510.00\n"
            "2026-09-02,INFY,1500.00\n"  # Touches level, not strictly below
            "2026-09-03,INFY,1490.00\n"  # Strictly crosses below
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=touch_and_cross_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        self.assertEqual(stdout.strip(), "2026-09-03 r1 INFY level below 1500")

        # Case B: 1510 -> 1500 -> 1510. Touches level then rebounds. Never crosses below.
        touch_and_rebound_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1510.00\n"
            "2026-09-02,INFY,1500.00\n"
            "2026-09-03,INFY,1510.00\n"
        )
        exit_code, stdout, stderr = run_pipeline(prices_content=touch_and_rebound_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        self.assertEqual(stdout.strip(), "")

    def test_oscillating_crossings(self):
        """
        - Edge Case Covered: Price oscillating back and forth across threshold multiple times.
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Choppy range-bound trading behavior around key levels.
        """
        oscillating_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1510.00\n"
            "2026-09-02,INFY,1490.00\n"  # Cross 1 below
            "2026-09-03,INFY,1520.00\n"  # Cross above
            "2026-09-04,INFY,1485.00\n"  # Cross 2 below
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=oscillating_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        lines = [line.strip() for line in stdout.strip().splitlines() if line.strip()]
        self.assertEqual(lines, [
            "2026-09-02 r1 INFY level below 1500",
            "2026-09-04 r1 INFY level below 1500"
        ])


# =====================================================================
# TASK 5: Moving Average Cross Semantics & Window Invariants
# =====================================================================
class TestMACrossSemantics(unittest.TestCase):
    """Verifies SMA calculation, window warm-up, day L vs L+1 boundaries, and bilateral crosses."""

    def test_insufficient_warmup_window(self):
        """
        - Edge Case Covered: Data history has 19 trading days when long window requires 20 days.
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Newly listed ticker or limited history observation window.
        """
        rows = ["date,instrument,close"]
        for day in range(1, 20):  # 19 rows
            rows.append(f"2026-09-{day:02d},TCS,3800.00")
        short_csv = "\n".join(rows) + "\n"

        rules = [
            {"id": "r1", "instrument": "TCS", "type": "ma_cross", "short": 5, "long": 20, "direction": "above"}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=short_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        self.assertEqual(stdout.strip(), "")

    def test_exact_boundary_off_by_one(self):
        """
        - Edge Case Covered: Earliest valid MA cross evaluation day (Day 20 baseline vs Day 21 cross).
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Core algorithmic off-by-one trap in moving average window warming.
        """
        rows = ["date,instrument,close"]
        # Days 1 through 20: Price is 100.0 (short_ma = 100.0, long_ma = 100.0)
        for day in range(1, 21):
            rows.append(f"2026-09-{day:02d},TCS,100.00")
        # Day 21: Price surges to 200.0
        # Day 20: short_ma = 100.0, long_ma = 100.0 (baseline established)
        # Day 21: short_ma = (100*4 + 200)/5 = 120.0, long_ma = (100*19 + 200)/20 = 105.0
        # Transition: Day 20 (short <= long) -> Day 21 (short > long). Alert MUST fire on Day 21, NOT Day 20.
        rows.append("2026-09-21,TCS,200.00")
        warmup_csv = "\n".join(rows) + "\n"

        rules = [
            {"id": "r1", "instrument": "TCS", "type": "ma_cross", "short": 5, "long": 20, "direction": "above"}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=warmup_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        lines = [line.strip() for line in stdout.strip().splitlines() if line.strip()]
        self.assertEqual(lines, ["2026-09-21 r1 TCS ma_cross 5/20 above"])

    def test_both_directions(self):
        """
        - Edge Case Covered: Verification of both 'above' (Golden Cross) and 'below' (Death Cross) rule logic.
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Bilateral trend detection setups in quant trading.
        """
        rows = ["date,instrument,close"]
        # Days 1 to 20: Price is 100.0
        for day in range(1, 21):
            rows.append(f"2026-09-{day:02d},TCS,100.00")
        # Day 21: Drops sharply to 50.0
        # Day 20: short = 100, long = 100
        # Day 21: short = 90.0, long = 97.5 (short crosses below long)
        rows.append("2026-09-21,TCS,50.00")
        death_cross_csv = "\n".join(rows) + "\n"

        rules = [
            {"id": "r_below", "instrument": "TCS", "type": "ma_cross", "short": 5, "long": 20, "direction": "below"}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=death_cross_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        self.assertEqual(stdout.strip(), "2026-09-21 r_below TCS ma_cross 5/20 below")

    def test_invalid_window_configuration(self):
        """
        - Edge Case Covered: Configuration error where short window >= long window, or windows are non-positive.
        - Pipeline Handling: Fatal (exit != 0)
        - Production Likelihood: Medium - Misconfigured or inverted parameters in rules configuration.
        """
        prices_csv = (
            "date,instrument,close\n"
            "2026-09-01,TCS,3800.00\n"
            "2026-09-02,TCS,3850.00\n"
        )
        invalid_rules = [
            {"id": "r1", "instrument": "TCS", "type": "ma_cross", "short": 20, "long": 5, "direction": "above"}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=prices_csv, rules_content=invalid_rules)
        self.assertNotEqual(exit_code, 0)
        self.assertTrue(len(stderr.strip()) > 0, "Expected error on stderr for short >= long")


# =====================================================================
# TASK 6: Rule Parsing, Exit Codes & Deterministic CLI Output
# =====================================================================
class TestRuleValidationAndCLIOutput(unittest.TestCase):
    """Verifies rule validation, deterministic multi-alert sorting, and CLI formatting compliance."""

    def test_invalid_rules_json(self):
        """
        - Edge Case Covered: Empty JSON, non-list root structure, or missing mandatory rule schema fields.
        - Pipeline Handling: Fatal (exit != 0)
        - Production Likelihood: Medium - Corrupted or unparseable configuration deployment.
        """
        prices_csv = "date,instrument,close\n2026-09-01,INFY,1500.00\n"

        # Case 1: Non-list root
        exit_code, stdout, stderr = run_pipeline(prices_content=prices_csv, rules_content={"not": "a list"})
        self.assertNotEqual(exit_code, 0)

        # Case 2: Missing required field 'direction'
        bad_rule = [{"id": "r1", "instrument": "INFY", "type": "level", "level": 1500}]
        exit_code, stdout, stderr = run_pipeline(prices_content=prices_csv, rules_content=bad_rule)
        self.assertNotEqual(exit_code, 0)

    def test_deterministic_sort_ordering(self):
        """
        - Edge Case Covered: Multiple alerts firing on the same day must sort by date ASC, then rule_id string ASC.
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - High-volatility market days triggering multiple concurrent signals.
        """
        prices_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.00\n"
            "2026-09-02,INFY,1480.00\n"
        )
        # Two rules triggering on 2026-09-02: 'r10' and 'r2'.
        # Lexicographical sort on rule_id string means 'r10' precedes 'r2'.
        rules = [
            {"id": "r2", "instrument": "INFY", "type": "level", "direction": "below", "level": 1490},
            {"id": "r10", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500},
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=prices_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        lines = [line.strip() for line in stdout.strip().splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "2026-09-02 r10 INFY level below 1500")
        self.assertEqual(lines[1], "2026-09-02 r2 INFY level below 1490")

    def test_silent_output_on_no_triggers(self):
        """
        - Edge Case Covered: Ingestion of valid price data where zero alert rules are satisfied.
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Quiet trading days with range-bound prices.
        """
        prices_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.00\n"
            "2026-09-02,INFY,1530.00\n"
        )
        rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=prices_csv, rules_content=rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        self.assertEqual(stdout.strip(), "", "Must output nothing when no rules fire")

    def test_exact_cli_line_format(self):
        """
        - Edge Case Covered: Strict conformance to output format specified in the assessment build brief.
        - Pipeline Handling: Decide & Document
        - Production Likelihood: High - Automated downstream consumer parsing contracts.
        """
        # Exactly reproduce the sample scenario from the problem brief
        sample_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.50\n"
            "2026-09-01,TCS,3890.00\n"
            "2026-09-02,INFY,1534.10\n"
            "2026-09-02,TCS,3902.25\n"
            "2026-09-03,INFY,1498.00\n"
        )
        sample_rules = [
            {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500}
        ]
        exit_code, stdout, stderr = run_pipeline(prices_content=sample_csv, rules_content=sample_rules)
        self.assertEqual(exit_code, 0, f"Failed with stderr: {stderr}")
        expected_line = "2026-09-03 r1 INFY level below 1500"
        self.assertEqual(stdout.strip(), expected_line)


if __name__ == "__main__":
    unittest.main()
