import csv
import glob
import logging
import os
import re
import shutil

import pandas as pd

from .validators import currency_to_float  # noqa: F401 — available for callers

logger = logging.getLogger(__name__)


def read_csv_files(folder_path, column_types=None, converters=None):
    """
    Read all CSV files in folder_path.

    Returns (dataframes, failed_files) where dataframes is a dict keyed by filename.
    """
    csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
    logger.info("Reading CSV files from %s", folder_path)
    for f in csv_files:
        logger.info("  Found: %s", os.path.basename(f))

    dataframes = {}
    failed_files = []

    for file_path in csv_files:
        file_name = os.path.basename(file_path)
        try:
            with open(file_path, "r") as f:
                header = f.readline().strip().split(",")
            filtered_types = {
                col: dtype
                for col, dtype in (column_types or {}).items()
                if col in header
            }
            df = pd.read_csv(
                file_path,
                dtype=filtered_types,
                skip_blank_lines=True,
                converters=converters,
            )
            dataframes[file_name] = df
        except Exception as e:
            logger.error("Error reading %s: %s", file_name, e)
            failed_files.append(file_name)

    return dataframes, failed_files


def save_to_csv(filename, filedata, precision_map, folder_path):
    """Format numeric columns to the required decimal precision and write to folder_path."""
    os.makedirs(folder_path, exist_ok=True)
    output_path = os.path.join(folder_path, filename)

    df = filedata.copy()
    try:
        for col, dp in precision_map.items():
            if col in df.columns:
                df[col] = df[col].apply(lambda x: f"{x:.{dp}f}" if pd.notna(x) else "")
    except Exception as e:
        logger.error("While processing %s: %s", filename, e)

    df.to_csv(output_path, index=False, quoting=csv.QUOTE_ALL, quotechar='"')
    logger.info("Saved: %s", output_path)


def move_to_processed(filename, input_folder, processed_folder):
    """
    Move a successfully saved input file into processed_folder.

    If the exact filename is not found (e.g. the date was corrected during
    validation so the key in valid_files differs from the name on disk), a
    wildcard glob is tried with the 8-digit date replaced by '*'.  If exactly
    one match is found that file is moved; if there are multiple ambiguous
    matches a warning is logged and the file is left in place.
    """
    src = os.path.join(input_folder, filename)
    if not os.path.exists(src):
        # Fallback: replace the 8-digit date with a wildcard and search.
        pattern = os.path.join(input_folder, re.sub(r"\d{8}", "*", filename))
        matches = glob.glob(pattern)
        if len(matches) == 1:
            src = matches[0]
            original_name = os.path.basename(src)
            logger.info(
                "Date-corrected filename: moving original '%s' as '%s'",
                original_name,
                filename,
            )
        elif len(matches) > 1:
            logger.warning(
                "Could not move '%s' — multiple files match the date-wildcard "
                "pattern '%s': %s",
                filename,
                pattern,
                [os.path.basename(m) for m in matches],
            )
            return
        else:
            logger.warning(
                "Could not move '%s' — file not found in input folder.",
                filename,
            )
            return
    os.makedirs(processed_folder, exist_ok=True)
    dst = os.path.join(processed_folder, filename)
    shutil.move(src, dst)
    logger.info("Moved to processed: %s", filename)
