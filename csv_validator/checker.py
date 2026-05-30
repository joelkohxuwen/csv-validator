import logging
import re

import config
from .validators import (
    check_aum_variance,
    check_stale_data,
    date_check,
    date_fix,
    validate_column_names,
    validate_end_of_month_column,
    validate_filename_convention,
    validate_float_precision,
    validate_special_characters,
)

logger = logging.getLogger(__name__)


def _ref_columns_for(filename):
    """Return the expected column list for this filename, or None if unrecognised."""
    if "FUM_flow" in filename:
        return config.FUM_COLS
    if "monthly_perf" in filename:
        return config.PERF_COLS
    if "peer_rank" in filename:
        return config.PEER_COLS
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_auto_corrections(filename, df):
    """
    Apply date and Valuation Period corrections without running any validation checks.

    Two corrections are made:
      1. If the 8-digit date in the filename is not an end-of-month date it is
         replaced with the last day of that month.
      2. Any rows in the 'Valuation Period' column that do not match the
         (possibly corrected) filename date are overwritten with that date.

    Returns:
        (corrected_filename, corrected_df)

    The returned df is a copy — the original is never mutated.
    If no date can be found in the filename the inputs are returned unchanged.
    """
    date_match = re.search(r"(\d{8})", filename)
    if not date_match:
        logger.warning("apply_auto_corrections: no date found in '%s', skipping.", filename)
        return filename, df.copy()

    filename_date_str = date_match.group(1)
    corrected_df = df.copy()

    # 1. Fix date in filename if not end-of-month
    if date_check(filename_date_str):          # True → has an issue
        new_date = date_fix(filename_date_str)
        filename = filename.replace(filename_date_str, new_date)
        filename_date_str = new_date
        logger.info("Auto-correction: date in filename fixed → %s", filename)

    # 2. Fix Valuation Period column values
    if "Valuation Period" in corrected_df.columns:
        val_issues = validate_end_of_month_column(corrected_df, ["Valuation Period"])
        if val_issues is not True:
            logger.info(
                "Auto-correction: replacing Valuation Period values in %s with %s",
                filename, filename_date_str,
            )
            for col, row_indices in val_issues.items():
                for idx in row_indices:
                    corrected_df.at[idx, col] = filename_date_str

    return filename, corrected_df


def file_check(df_dict, lbu_list, archive_path):
    """
    Validate every DataFrame in df_dict.

    Returns:
        valid_files   (dict) — files that passed all checks, keyed by filename
        invalid_files (dict) — files that failed, keyed by filename; value is a dict
                               of {check_name: issue_detail}
    """
    logger.info("Checking files: %s", list(df_dict.keys()))
    valid_files = {}
    invalid_files = {}

    for file, filedata in df_dict.items():
        ref_columns = _ref_columns_for(file)
        if ref_columns is None:
            logger.warning("Unrecognised file type, skipping: %s", file)
            invalid_files[file] = {"filename_validity": "Unrecognised file type"}
            continue

        date_match = re.search(r"(\d{8})", file)
        if not date_match:
            invalid_files[file] = {"filename_validity": "Could not extract date from filename"}
            continue

        # --- apply date and Valuation Period corrections before validating ---
        file, filedata = apply_auto_corrections(file, filedata)
        filename_date_str = re.search(r"(\d{8})", file).group(1)

        # --- filename convention ---
        filename_validity = validate_filename_convention(file, lbu_list)

        # --- re-validate after auto-corrections ---
        date_validity = not date_check(filename_date_str)
        val_date_validity = validate_end_of_month_column(filedata, ["Valuation Period"])

        # --- column names ---
        column_name_validity = validate_column_names(filedata, ref_columns)

        # --- special characters in Fund Code ---
        key_validity = validate_special_characters(filedata, ref_columns=["Fund Code"])

        # --- float precision ---
        float_2dp_validity = validate_float_precision(
            filedata, 2,
            ref_columns=["AUM in Base Currency (month-end)", "Closing FUM", "Net Flows"],
        )
        float_4dp_validity = validate_float_precision(
            filedata, 4,
            ref_columns=["Annual Management Fee", "Management Fee (%)"],
        )
        float_6dp_validity = validate_float_precision(
            filedata, 6,
            ref_columns=["Monthly performance"],
        )

        # --- stale data check — fails the file if data is identical to prior month ---
        is_stale, stale_msg = check_stale_data(file, filedata, archive_path)
        if is_stale is True:
            stale_validity = stale_msg          # truthy non-True → treated as failure
            logger.warning("STALE DATA: %s — %s", file, stale_msg)
        else:
            stale_validity = True               # differs from prior month, or no prior file
            logger.info("Stale check: %s — %s", file, stale_msg)

        # --- AUM monthly variance check (>5% change per fund fails the file) ---
        aum_variance_validity = check_aum_variance(file, filedata, archive_path)
        if aum_variance_validity is not True:
            logger.warning("AUM VARIANCE: %s — %s", file, aum_variance_validity)

        # --- aggregate result ---
        checks = {
            "filename_validity": filename_validity,
            "date_validity": date_validity,
            "val_date_validity": val_date_validity,
            "column_name_validity": column_name_validity,
            "key_validity": key_validity,
            "float_2dp_validity": float_2dp_validity,
            "float_4dp_validity": float_4dp_validity,
            "float_6dp_validity": float_6dp_validity,
            "stale_validity": stale_validity,
            "aum_variance_validity": aum_variance_validity,
        }
        failures = {name: result for name, result in checks.items() if result is not True}

        if not failures:
            valid_files[file] = filedata
        else:
            logger.warning("File failed validation: %s — %s", file, list(failures.keys()))
            invalid_files[file] = failures

    return valid_files, invalid_files
