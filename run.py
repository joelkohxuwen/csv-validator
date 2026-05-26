"""
CSV Validator — entry point.

Usage:
    python run.py

Scheduling on Windows Task Scheduler:
    Program:  python
    Arguments: "D:\\Claude Code\\csv_validator\\run.py"
    Start in: D:\\Claude Code\\csv_validator

Or use run.bat which sets the working directory automatically.
"""

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


def _build_expected_dtypes():
    all_cols = list(set(config.FUM_COLS + config.PERF_COLS + config.PEER_COLS))
    return {col: "float" if col in config.ALL_FLOAT_COLS else "str" for col in all_cols}


def main():
    log_file = _setup_logging(config.LOG_DIR)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("CSV Validator starting")
    logger.info("Log file  : %s", log_file)
    logger.info("Input     : %s", config.INPUT_PATH)
    logger.info("Output    : %s", config.OUTPUT_PATH)
    logger.info("=" * 60)

    expected_dtypes = _build_expected_dtypes()

    # 1. Read
    files, read_failures = read_csv_files(config.INPUT_PATH, column_types=expected_dtypes)
    if read_failures:
        logger.warning("Could not read: %s", read_failures)

    # 2. Validate
    valid_files, invalid_files, stale_warnings = file_check(
        files, lbu_list=config.LBU_LIST, input_folder=config.INPUT_PATH
    )

    # 3. Save valid files
    for filename, filedata in valid_files.items():
        save_to_csv(filename, filedata, config.PRECISION_MAP, config.OUTPUT_PATH)

    # 4. Summary
    logger.info("=" * 60)
    logger.info(
        "Done — valid: %d, invalid: %d, read failures: %d, stale warnings: %d",
        len(valid_files), len(invalid_files), len(read_failures), len(stale_warnings),
    )
    if invalid_files:
        logger.warning("Files with validation issues:")
        for fname, issues in invalid_files.items():
            logger.warning("  %s: %s", fname, issues)
    if stale_warnings:
        logger.warning("Stale data warnings:")
        for fname, msg in stale_warnings.items():
            logger.warning("  %s: %s", fname, msg)
    if read_failures:
        logger.warning("Files that could not be read: %s", read_failures)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
