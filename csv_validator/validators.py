import calendar
import os
import re
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def currency_to_float(s):
    if "," in s:
        return float(s.replace(",", ""))
    return s


def contains_invalid_characters(value):
    pattern = re.compile(r"[^a-zA-Z0-9\_\.\$]")
    return bool(pattern.search(str(value))) if isinstance(value, str) else False


def validate_filename_convention(filename, accepted_lbus):
    """True if filename matches a known pattern and the LBU is in accepted_lbus."""
    patterns = [
        r"^([A-Z]+)_monthly_perf_([a-zA-Z0-9\-]+)_(\d{8})\.csv$",  # manager can have hyphens
        r"^([A-Z]+)_FUM_flows_(\d{8})\.csv$",
        r"^([A-Z]+)_peer_rank_(\d{8})\.csv$",
        r"^([A-Z]+)_ms_peer_rank_(\d{8})\.csv$",
    ]
    for pattern in patterns:
        match = re.match(pattern, filename)
        if match:
            lbu = match.group(1)
            if lbu in accepted_lbus:
                return True
    return False


def validate_column_names(df, ref_columns):
    issues = {}
    for col in df.columns:
        if col not in ref_columns:
            issues[col] = "Column name not matching template"
    return True if not issues else issues


def date_check(date_str, filename_date_str=None):
    """Returns True if the date has an issue, False if it is a valid end-of-month."""
    try:
        if filename_date_str is not None and str(date_str) != filename_date_str:
            print(f"Valuation Period not expected: {date_str}")
            return False  # Change to True to fail when date differs from filename
        date_obj = datetime.strptime(str(date_str), "%Y%m%d")
        last_day = calendar.monthrange(date_obj.year, date_obj.month)[1]
        if date_obj.day == last_day:
            return False  # Valid end-of-month — no issue
        return True  # Not end-of-month — issue found
    except Exception as e:
        return f"Invalid date format: {e}"


def date_fix(date_str):
    """Return the last day of the same month as date_str."""
    try:
        date_obj = datetime.strptime(str(date_str), "%Y%m%d")
        last_day = calendar.monthrange(date_obj.year, date_obj.month)[1]
        date_obj = date_obj.replace(day=last_day)
        return date_obj.strftime("%Y%m%d")
    except Exception as e:
        return f"Invalid date format: {e}"


def validate_end_of_month_column(df, ref_columns, filename_date_str=None):
    issues = {}
    if ref_columns:
        df = df[[col for col in ref_columns if col in df.columns]]
    for col in df.columns:
        if filename_date_str is not None:
            invalid_rows = df[col].map(
                lambda x: date_check(x, filename_date_str=filename_date_str)
            )
        else:
            invalid_rows = df[col].map(date_check)
        if invalid_rows.any():
            issues[col] = invalid_rows[invalid_rows].index.tolist()
    return True if not issues else issues


def validate_string_lengths(df, max_length=120, ref_columns=None):
    if ref_columns:
        df = df[[col for col in ref_columns if col in df.columns]]
    string_cols = df.select_dtypes(include="object")
    issues = {}
    for col in string_cols.columns:
        invalid_rows = string_cols[col].map(
            lambda x: isinstance(x, str) and len(x) >= max_length
        )
        if invalid_rows.any():
            issues[col] = invalid_rows[invalid_rows].index.tolist()
    return True if not issues else issues


def validate_float_precision(df, precision=2, ref_columns=None):
    if ref_columns:
        df = df[[col for col in ref_columns if col in df.columns]]
    float_cols = df.select_dtypes(include="float64")
    issues = {}
    for col in float_cols.columns:
        invalid_rows = df[col].map(
            lambda x: not np.isclose(x, round(x, precision)) if not np.isnan(x) else False
        )
        if invalid_rows.any():
            issues[col] = invalid_rows[invalid_rows].index.tolist()
    return True if not issues else issues


def validate_special_characters(df, ref_columns=None):
    if ref_columns:
        df = df[[col for col in ref_columns if col in df.columns]]
    string_cols = df.select_dtypes(include="object")
    issues = {}
    for col in string_cols.columns:
        invalid_rows = string_cols[col].map(contains_invalid_characters)
        if invalid_rows.any():
            issues[col] = invalid_rows[invalid_rows].index.tolist()
    return True if not issues else issues


def _any_value_changed(merged, col):
    """
    Return True if at least one row shows a numeric change between _curr and _prev.
    Rows where both sides are NaN are treated as unchanged.
    """
    curr = merged[f"{col}_curr"]
    prev = merged[f"{col}_prev"]
    both_nan = curr.isna() & prev.isna()
    changed = ~(both_nan | (curr == prev))
    return changed.any()


def check_stale_data(filename, current_df, archive_path):
    """
    Check for stale data against the prior month's file on three dimensions:

    1. AUM unchanged    — fails if AUM column is present and no fund shows any change
    2. Returns unchanged — fails if returns column is present and no fund shows any change
    3. Fund universe changed — fails if the set of Fund Codes has grown or shrunk

    The prior-month file is looked up under archive_path/<year>/<filename>.

    Returns:
      (True,  issues_dict) — one or more stale checks failed; dict keys are
                             "aum", "returns", "fund_universe"
      (False, msg)         — all applicable checks passed
      (None,  msg)         — check could not be performed (no prior file, etc.)
    """
    date_match = re.search(r"(\d{8})", filename)
    if not date_match:
        return None, "Could not extract date from filename"

    date_str = date_match.group(1)
    try:
        date_obj = datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        return None, f"Invalid date in filename: {date_str}"

    prev_month_last = date_obj.replace(day=1) - timedelta(days=1)
    prev_filename = filename.replace(date_str, prev_month_last.strftime("%Y%m%d"))
    prev_filepath = os.path.join(archive_path, str(prev_month_last.year), prev_filename)

    if not os.path.exists(prev_filepath):
        return None, f"No prior month file found: {prev_filename}"

    try:
        prev_df = pd.read_csv(prev_filepath, dtype=str, skip_blank_lines=True)
    except Exception as e:
        return None, f"Could not read prior month file: {e}"

    issues = {}
    has_fund_code = (
        "Fund Code" in current_df.columns and "Fund Code" in prev_df.columns
    )

    # --- 1. AUM change check ---
    aum_col = next(
        (c for c in ["AUM in Base Currency (month-end)", "Closing FUM"]
         if c in current_df.columns and c in prev_df.columns),
        None,
    )
    if aum_col and has_fund_code:
        curr = current_df[["Fund Code", aum_col]].copy()
        prev = prev_df[["Fund Code", aum_col]].copy()
        curr[aum_col] = pd.to_numeric(curr[aum_col], errors="coerce")
        prev[aum_col] = pd.to_numeric(prev[aum_col], errors="coerce")
        merged = curr.merge(prev, on="Fund Code", suffixes=("_curr", "_prev"))
        if not merged.empty and not _any_value_changed(merged, aum_col):
            issues["aum"] = f"No change in '{aum_col}' for any fund"

    # --- 2. Returns change check ---
    returns_col = next(
        (c for c in ["Monthly performance"]
         if c in current_df.columns and c in prev_df.columns),
        None,
    )
    if returns_col and has_fund_code:
        curr = current_df[["Fund Code", returns_col]].copy()
        prev = prev_df[["Fund Code", returns_col]].copy()
        curr[returns_col] = pd.to_numeric(curr[returns_col], errors="coerce")
        prev[returns_col] = pd.to_numeric(prev[returns_col], errors="coerce")
        merged = curr.merge(prev, on="Fund Code", suffixes=("_curr", "_prev"))
        if not merged.empty and not _any_value_changed(merged, returns_col):
            issues["returns"] = f"No change in '{returns_col}' for any fund"

    # --- 3. Fund universe change check ---
    if has_fund_code:
        curr_funds = set(current_df["Fund Code"].dropna().astype(str))
        prev_funds = set(prev_df["Fund Code"].dropna().astype(str))
        if curr_funds != prev_funds:
            added   = sorted(curr_funds - prev_funds)
            removed = sorted(prev_funds - curr_funds)
            parts = []
            if added:
                parts.append(f"{len(added)} added: {added}")
            if removed:
                parts.append(f"{len(removed)} removed: {removed}")
            issues["fund_universe"] = f"Fund universe changed — {'; '.join(parts)}"

    if issues:
        return True, issues
    return False, f"Stale checks passed against {prev_filename}"


def check_aum_variance(filename, current_df, archive_path, threshold=0.05):
    """
    Compare per-fund AUM against the prior month's file.

    Fails if any fund's AUM changes by more than `threshold` (default 5%).
    Returns True if all funds are within range, or a dict of offending funds.
    Returns True (pass) if the prior month file is absent — benefit of the doubt.

    The prior-month file is looked up under archive_path/<year>/<filename>.
    AUM column checked: first of "AUM in Base Currency (month-end)" or "Closing FUM"
    that is present in the file. Files with neither column are skipped.
    Funds that are new (absent from prior file) are skipped.
    """
    # Identify which AUM column this file carries
    aum_col = next(
        (c for c in ["AUM in Base Currency (month-end)", "Closing FUM"] if c in current_df.columns),
        None,
    )
    if aum_col is None or "Fund Code" not in current_df.columns:
        return True  # File type has no comparable AUM column — skip

    # Locate prior month file
    date_match = re.search(r"(\d{8})", filename)
    if not date_match:
        return True

    date_str = date_match.group(1)
    try:
        date_obj = datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        return True

    prev_month_last = date_obj.replace(day=1) - timedelta(days=1)
    prev_filepath = os.path.join(
        archive_path,
        str(prev_month_last.year),
        filename.replace(date_str, prev_month_last.strftime("%Y%m%d")),
    )

    if not os.path.exists(prev_filepath):
        return True  # No prior file — cannot compare, pass

    try:
        prev_df = pd.read_csv(prev_filepath, dtype=str, skip_blank_lines=True)
    except Exception:
        return True

    if aum_col not in prev_df.columns or "Fund Code" not in prev_df.columns:
        return True

    curr_aum = current_df[["Fund Code", aum_col]].copy()
    prev_aum = prev_df[["Fund Code", aum_col]].copy()

    curr_aum[aum_col] = pd.to_numeric(curr_aum[aum_col], errors="coerce")
    prev_aum[aum_col] = pd.to_numeric(prev_aum[aum_col], errors="coerce")

    merged = curr_aum.merge(prev_aum, on="Fund Code", suffixes=("_curr", "_prev"))

    issues = {}
    for _, row in merged.iterrows():
        curr_val = row[f"{aum_col}_curr"]
        prev_val = row[f"{aum_col}_prev"]

        if pd.isna(curr_val) or pd.isna(prev_val) or prev_val == 0:
            continue

        change_pct = (curr_val - prev_val) / abs(prev_val)
        if abs(change_pct) > threshold:
            issues[row["Fund Code"]] = {
                "prev_aum": round(float(prev_val), 2),
                "curr_aum": round(float(curr_val), 2),
                "change_pct": round(change_pct * 100, 2),
            }

    return True if not issues else issues
