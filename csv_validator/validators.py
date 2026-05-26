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


def check_stale_data(filename, current_df, input_folder):
    """
    Compare current file against the equivalent file from the previous calendar month.

    The prior-month file is expected to have the same name with the YYYYMMDD portion
    replaced by the last day of the previous month.

    Returns a tuple (is_stale, message):
      (True,  msg) — all comparable data is identical to prior month (potentially stale)
      (False, msg) — data differs from prior month (looks fresh)
      (None,  msg) — check could not be performed (no prior file found, etc.)
    """
    date_match = re.search(r"(\d{8})", filename)
    if not date_match:
        return None, "Could not extract date from filename"

    date_str = date_match.group(1)
    try:
        date_obj = datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        return None, f"Invalid date in filename: {date_str}"

    # Last day of previous month
    prev_month_last = date_obj.replace(day=1) - timedelta(days=1)
    prev_date_str = prev_month_last.strftime("%Y%m%d")

    prev_filename = filename.replace(date_str, prev_date_str)
    prev_filepath = os.path.join(input_folder, prev_filename)

    if not os.path.exists(prev_filepath):
        return None, f"No prior month file found: {prev_filename}"

    try:
        prev_df = pd.read_csv(prev_filepath, dtype=str, skip_blank_lines=True)
    except Exception as e:
        return None, f"Could not read prior month file: {e}"

    # Exclude Valuation Period — it is expected to differ every month
    compare_cols = [
        c for c in current_df.columns
        if c in prev_df.columns and c != "Valuation Period"
    ]
    if not compare_cols:
        return None, "No comparable columns found"

    curr_subset = current_df[compare_cols].reset_index(drop=True).astype(str)
    prev_subset = prev_df[compare_cols].reset_index(drop=True).astype(str)

    if curr_subset.equals(prev_subset):
        return True, f"All data values identical to prior month file ({prev_filename})"
    return False, f"Data differs from prior month file ({prev_filename})"
