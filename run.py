"""
CSV Validator — entry point.

Usage:
    python run.py                                    # normal scheduled run
    python run.py --override FILE1.csv FILE2.csv     # skip all checks for named files

Scheduling on Windows Task Scheduler:
    Program:  python
    Arguments: "D:\\Claude Code\\csv_validator\\run.py"
    Start in: D:\\Claude Code\\csv_validator

Or use run.bat which sets the working directory automatically.
"""

import argparse
import logging
import os
import sys
from datetime import datetime


def _setup_logging(log_dir):
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"csv_validator_{datetime.now():%Y%m%d_%H%M%S}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_file


# Ensure the script's own directory is on the path so sibling modules resolve.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import config
except ImportError:
    sys.exit(
        "ERROR: config.py not found.\n"
        "Copy config.example.py to config.py and fill in your actual paths."
    )

from csv_validator.checker import file_check
from csv_validator.io_utils import read_csv_files, save_to_csv


def _parse_args():
    parser = argparse.ArgumentParser(description="CSV Validator")
    parser.add_argument(
        "--override",
        nargs="+",
        metavar="FILENAME",
        default=[],
        help=(
            "One or more filenames to save directly, skipping all validation checks. "
            "Use for files confirmed as correct that would otherwise fail. "
            "Example: --override FILE1.csv FILE2.csv"
        ),
    )
    return parser.parse_args()


def _build_expected_dtypes():
    all_cols = list(set(config.FUM_COLS + config.PERF_COLS + config.PEER_COLS))
    return {col: "float" if col in config.ALL_FLOAT_COLS else "str" for col in all_cols}


def main():
    args = _parse_args()
    override_files = set(args.override)

    log_file = _setup_logging(config.LOG_DIR)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("CSV Validator starting")
    logger.info("Log file  : %s", log_file)
    logger.info("Input     : %s", config.INPUT_PATH)
    logger.info("Output    : %s", config.OUTPUT_PATH)
    logger.info("Archive   : %s", config.ARCHIVE_PATH)
    if override_files:
        logger.info("Overrides : %s", sorted(override_files))
    logger.info("=" * 60)

    expected_dtypes = _build_expected_dtypes()

    # 1. Read all files
    files, read_failures = read_csv_files(config.INPUT_PATH, column_types=expected_dtypes)
    if read_failures:
        logger.warning("Could not read: %s", read_failures)

    # 2. Split into normal validation path and override path
    normal_files   = {f: df for f, df in files.items() if f not in override_files}
    override_dict  = {f: df for f, df in files.items() if f in override_files}

    unknown_overrides = override_files - set(files)
    if unknown_overrides:
        logger.warning("Override file(s) not found in input folder: %s", unknown_overrides)

    # 3. Validate normal files
    valid_files, invalid_files = file_check(
        normal_files, lbu_list=config.LBU_LIST, archive_path=config.ARCHIVE_PATH
    )

    # 4. Save valid files
    for filename, filedata in valid_files.items():
        save_to_csv(filename, filedata, config.PRECISION_MAP, config.OUTPUT_PATH)

    # 5. Save override files (formatting applied, all checks skipped)
    for filename, filedata in override_dict.items():
        logger.warning("OVERRIDE: saving %s without validation", filename)
        save_to_csv(filename, filedata, config.PRECISION_MAP, config.OUTPUT_PATH)

    # 6. Summary
    logger.info("=" * 60)
    logger.info(
        "Done — valid: %d, invalid: %d, overridden: %d, read failures: %d",
        len(valid_files), len(invalid_files), len(override_dict), len(read_failures),
    )
    if invalid_files:
        logger.warning("Files with validation issues:")
        for fname, issues in invalid_files.items():
            logger.warning("  %s: %s", fname, issues)
    if read_failures:
        logger.warning("Files that could not be read: %s", read_failures)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
