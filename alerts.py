"""
alerts.py - Price Alert Tool CLI & Evaluation Engine

Ingests daily financial prices from CSV and technical alert rules from JSON,
evaluates state transitions (level threshold crossings and moving average crossovers),
and outputs triggered alerts in strict deterministic order to standard output.

Usage:
    python alerts.py <prices.csv> <rules.json>

Zero third-party dependencies: Built strictly with Python standard library modules.
"""

import csv
import json
import math
import pathlib
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation


def format_level_val(val: Decimal) -> str:
    """Format numeric level value without redundant trailing zeroes if whole integer."""
    if val == val.to_integral():
        return str(val.to_integral())
    return str(val.normalize())


def parse_and_validate_rules(rules_path: pathlib.Path) -> list[dict]:
    """Parse JSON rules configuration and enforce schema validation."""
    try:
        with open(rules_path, "r", encoding="utf-8-sig") as f:
            rules_data = json.load(f)
    except Exception as exc:
        sys.stderr.write(f"Fatal: Failed to read or parse rules JSON file: {exc}\n")
        sys.exit(1)

    if not isinstance(rules_data, list) or len(rules_data) == 0:
        sys.stderr.write("Fatal: Rules configuration must be a non-empty JSON list of objects.\n")
        sys.exit(1)

    validated_rules = []
    for idx, rule in enumerate(rules_data):
        if not isinstance(rule, dict):
            sys.stderr.write(f"Fatal: Rule at index {idx} is not a JSON object.\n")
            sys.exit(1)

        for mandatory_key in ("id", "instrument", "type", "direction"):
            if mandatory_key not in rule:
                sys.stderr.write(
                    f"Fatal: Rule at index {idx} missing required field '{mandatory_key}': {rule}\n"
                )
                sys.exit(1)

        rule_id = str(rule["id"]).strip()
        instrument = str(rule["instrument"]).strip().upper()
        rule_type = str(rule["type"]).strip()
        direction = str(rule["direction"]).strip()

        if not rule_id or not instrument:
            sys.stderr.write(f"Fatal: Rule at index {idx} contains empty id or instrument.\n")
            sys.exit(1)

        if direction not in ("above", "below"):
            sys.stderr.write(
                f"Fatal: Rule '{rule_id}' has invalid direction '{direction}'. Must be 'above' or 'below'.\n"
            )
            sys.exit(1)

        if rule_type == "level":
            if "level" not in rule:
                sys.stderr.write(f"Fatal: Level rule '{rule_id}' missing 'level' field.\n")
                sys.exit(1)
            raw_level = rule["level"]
            if isinstance(raw_level, bool):
                sys.stderr.write(f"Fatal: Level value for rule '{rule_id}' cannot be boolean.\n")
                sys.exit(1)
            try:
                dec_level = Decimal(str(raw_level))
                if dec_level.is_nan() or dec_level.is_infinite():
                    raise ValueError()
            except (InvalidOperation, ValueError):
                sys.stderr.write(
                    f"Fatal: Level value for rule '{rule_id}' must be a finite number: {raw_level}\n"
                )
                sys.exit(1)

            validated_rules.append(
                {
                    "id": rule_id,
                    "instrument": instrument,
                    "type": "level",
                    "direction": direction,
                    "level": dec_level,
                }
            )

        elif rule_type == "ma_cross":
            if "short" not in rule or "long" not in rule:
                sys.stderr.write(
                    f"Fatal: ma_cross rule '{rule_id}' requires both 'short' and 'long' integer windows.\n"
                )
                sys.exit(1)

            s_val = rule["short"]
            l_val = rule["long"]
            if isinstance(s_val, bool) or not isinstance(s_val, int) or s_val <= 0:
                sys.stderr.write(
                    f"Fatal: 'short' window for rule '{rule_id}' must be a positive integer: {s_val}\n"
                )
                sys.exit(1)
            if isinstance(l_val, bool) or not isinstance(l_val, int) or l_val <= 0:
                sys.stderr.write(
                    f"Fatal: 'long' window for rule '{rule_id}' must be a positive integer: {l_val}\n"
                )
                sys.exit(1)
            if s_val >= l_val:
                sys.stderr.write(
                    f"Fatal: 'short' window ({s_val}) must be strictly less than 'long' window ({l_val}) in rule '{rule_id}'.\n"
                )
                sys.exit(1)

            validated_rules.append(
                {
                    "id": rule_id,
                    "instrument": instrument,
                    "type": "ma_cross",
                    "direction": direction,
                    "short": s_val,
                    "long": l_val,
                }
            )
        else:
            sys.stderr.write(f"Fatal: Unsupported rule type '{rule_type}' in rule '{rule_id}'.\n")
            sys.exit(1)

    return validated_rules


def parse_and_clean_prices(prices_path: pathlib.Path) -> dict[str, list[tuple[str, Decimal]]]:
    """
    Ingest CSV, normalize headers, drop poison values, resolve duplicates,
    and return chronologically sorted prices partitioned by instrument.
    """
    try:
        with open(prices_path, "r", encoding="utf-8-sig", errors="replace") as f:
            raw_content = f.read()
    except Exception as exc:
        sys.stderr.write(f"Fatal: Failed to read prices CSV file: {exc}\n")
        sys.exit(1)

    # Normalize line endings across CRLF, LF, and stray CR
    normalized_lines = raw_content.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    reader = csv.reader(normalized_lines)

    header_row = next(reader, None)
    if header_row is None:
        sys.stderr.write("Fatal: CSV prices file is completely empty.\n")
        sys.exit(1)

    header_indices = {col.strip().lower(): idx for idx, col in enumerate(header_row)}
    for required in ("date", "instrument", "close"):
        if required not in header_indices:
            sys.stderr.write(f"Fatal: Missing mandatory header column '{required}' in CSV.\n")
            sys.exit(1)

    date_idx = header_indices["date"]
    inst_idx = header_indices["instrument"]
    close_idx = header_indices["close"]
    max_req_idx = max(date_idx, inst_idx, close_idx)

    # Temporary storage: instrument -> {date_str: close_decimal}
    raw_series_by_inst: dict[str, dict[str, Decimal]] = {}

    for row_num, row in enumerate(reader, start=2):
        # Skip completely blank lines
        if not row or all(not cell.strip() for cell in row):
            continue

        # Skip ragged rows
        if len(row) <= max_req_idx:
            sys.stderr.write(f"Warning: Line {row_num}: Ragged row with insufficient columns dropped: {row}\n")
            continue

        raw_date = row[date_idx].strip()
        raw_inst = row[inst_idx].strip().upper()
        raw_close = row[close_idx].strip()

        if not raw_date or not raw_inst:
            sys.stderr.write(f"Warning: Line {row_num}: Missing date or instrument field. Row dropped.\n")
            continue

        # Validate date format (YYYY-MM-DD)
        try:
            parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            date_str = parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            sys.stderr.write(f"Warning: Line {row_num}: Invalid date format '{raw_date}'. Row dropped.\n")
            continue

        # Validate price token
        if not raw_close or raw_close.lower() in ("nan", "inf", "-inf", "null", "n/a"):
            sys.stderr.write(f"Warning: Line {row_num}: Poison or null price value '{raw_close}' dropped.\n")
            continue

        try:
            dec_close = Decimal(raw_close)
            if dec_close.is_nan() or dec_close.is_infinite():
                raise ValueError()
        except (InvalidOperation, ValueError):
            sys.stderr.write(f"Warning: Line {row_num}: Unparseable numeric price '{raw_close}' dropped.\n")
            continue

        if dec_close <= Decimal("0"):
            sys.stderr.write(f"Warning: Line {row_num}: Non-positive price '{raw_close}' dropped.\n")
            continue

        # Duplicate resolution
        if raw_inst not in raw_series_by_inst:
            raw_series_by_inst[raw_inst] = {}

        if date_str in raw_series_by_inst[raw_inst]:
            existing_val = raw_series_by_inst[raw_inst][date_str]
            if existing_val == dec_close:
                # Identical duplicate: silently deduplicate
                pass
            else:
                # Conflicting duplicate: last row wins, warn to stderr
                sys.stderr.write(
                    f"Warning: Conflicting price for {raw_inst} on {date_str} "
                    f"(existing: {existing_val}, new: {dec_close}). Overwriting with last row.\n"
                )
                raw_series_by_inst[raw_inst][date_str] = dec_close
        else:
            raw_series_by_inst[raw_inst][date_str] = dec_close

    # Sort each instrument's price series strictly by date ascending
    sorted_series: dict[str, list[tuple[str, Decimal]]] = {}
    for inst, date_dict in raw_series_by_inst.items():
        sorted_series[inst] = sorted(date_dict.items(), key=lambda item: item[0])

    return sorted_series


def evaluate_rules(
    rules: list[dict], series_by_inst: dict[str, list[tuple[str, Decimal]]]
) -> list[tuple[str, str, str]]:
    """
    Evaluate Level and MA Cross rules against chronologically sorted price series.
    Returns list of tuples: (date_str, rule_id, alert_line)
    """
    triggered_alerts: list[tuple[str, str, str]] = []

    for rule in rules:
        rule_id = rule["id"]
        inst = rule["instrument"]
        rule_type = rule["type"]
        direction = rule["direction"]

        if inst not in series_by_inst:
            continue

        series = series_by_inst[inst]
        n_days = len(series)
        if n_days == 0:
            continue

        if rule_type == "level":
            threshold = rule["level"]
            level_repr = format_level_val(threshold)
            detail = f"level {direction} {level_repr}"

            # Day 0 invariant: Day 0 cannot trigger because there is no prior day
            for t in range(1, n_days):
                prev_date, prev_close = series[t - 1]
                curr_date, curr_close = series[t]

                if direction == "below":
                    # Transition from >= threshold to < threshold
                    if prev_close >= threshold and curr_close < threshold:
                        line = f"{curr_date} {rule_id} {inst} {detail}"
                        triggered_alerts.append((curr_date, rule_id, line))
                elif direction == "above":
                    # Transition from <= threshold to > threshold
                    if prev_close <= threshold and curr_close > threshold:
                        line = f"{curr_date} {rule_id} {inst} {detail}"
                        triggered_alerts.append((curr_date, rule_id, line))

        elif rule_type == "ma_cross":
            short_w = rule["short"]
            long_w = rule["long"]
            detail = f"ma_cross {short_w}/{long_w} {direction}"

            # Earliest possible crossover alert is index long_w (day long_w + 1),
            # because day index long_w - 1 is the first day long SMA is defined,
            # providing the baseline relationship for day index long_w to cross.
            if n_days < long_w + 1:
                continue

            # Compute cross-multiplied SMA sums for exact precision:
            # short_ma > long_ma <=> (short_sum / short_w) > (long_sum / long_w)
            # <=> short_sum * long_w > long_sum * short_w
            for t in range(long_w, n_days):
                curr_date, _ = series[t]

                # Previous day (t-1) sums
                prev_short_sum = sum(p for _, p in series[t - short_w : t])
                prev_long_sum = sum(p for _, p in series[t - long_w : t])
                prev_short_prod = prev_short_sum * long_w
                prev_long_prod = prev_long_sum * short_w

                # Current day (t) sums
                curr_short_sum = sum(p for _, p in series[t - short_w + 1 : t + 1])
                curr_long_sum = sum(p for _, p in series[t - long_w + 1 : t + 1])
                curr_short_prod = curr_short_sum * long_w
                curr_long_prod = curr_long_sum * short_w

                if direction == "above":
                    # Golden Cross: from <= to >
                    if prev_short_prod <= prev_long_prod and curr_short_prod > curr_long_prod:
                        line = f"{curr_date} {rule_id} {inst} {detail}"
                        triggered_alerts.append((curr_date, rule_id, line))
                elif direction == "below":
                    # Death Cross: from >= to <
                    if prev_short_prod >= prev_long_prod and curr_short_prod < curr_long_prod:
                        line = f"{curr_date} {rule_id} {inst} {detail}"
                        triggered_alerts.append((curr_date, rule_id, line))

    return triggered_alerts


def main() -> None:
    """CLI orchestrator for Price Alert Tool."""
    if len(sys.argv) != 3:
        sys.stderr.write("Usage: python alerts.py <prices.csv> <rules.json>\n")
        sys.exit(1)

    prices_path = pathlib.Path(sys.argv[1])
    rules_path = pathlib.Path(sys.argv[2])

    if not prices_path.is_file():
        sys.stderr.write(f"Fatal: Prices file does not exist: {prices_path}\n")
        sys.exit(1)

    if not rules_path.is_file():
        sys.stderr.write(f"Fatal: Rules file does not exist: {rules_path}\n")
        sys.exit(1)

    rules = parse_and_validate_rules(rules_path)
    series_by_inst = parse_and_clean_prices(prices_path)

    alerts = evaluate_rules(rules, series_by_inst)

    # Sort deterministically: primary date ASC, secondary rule_id string ASC
    alerts.sort(key=lambda a: (a[0], str(a[1])))

    # Output to stdout; if no alerts triggered, prints nothing
    for _, _, alert_line in alerts:
        sys.stdout.write(f"{alert_line}\n")


if __name__ == "__main__":
    main()
