# config.example.py — committed to git as a template.
#
# To use:
#   1. Copy this file to config.py
#   2. Fill in your actual paths
#   3. config.py is listed in .gitignore and will NOT be committed.

# Folder that contains the monthly CSV files to validate.
INPUT_PATH = r"C:\path\to\your\input\folder"

# Folder where formatted/validated CSVs are written (can be a UNC network path).
OUTPUT_PATH = r"\\server\share\path\to\output\folder"

# Root folder containing prior month files used for stale and AUM variance checks.
# Files must be organised in year subfolders, e.g.:
#   C:\path\to\archive\2025\FUND_monthly_perf_MGR_20251231.csv
#   C:\path\to\archive\2026\FUND_monthly_perf_MGR_20260131.csv
ARCHIVE_PATH = r"C:\path\to\your\archive\folder"

# Folder where successfully processed input files are moved after saving.
# Files that fail validation remain in INPUT_PATH, making rejections immediately visible.
# Created automatically if it does not exist.
PROCESSED_PATH = r"C:\path\to\your\processed\folder"

# Directory where log files will be written (created automatically if absent).
LOG_DIR = r"C:\path\to\your\log\folder"

# LBU identifiers that are accepted in filenames.
# Replace with your actual LBU codes.
LBU_LIST = ["LBU1", "LBU2", "LBU3"]

# ---------------------------------------------------------------------------
# Column schemas — one list per file type.
# Copy the exact header names from your CSV templates.
# ---------------------------------------------------------------------------

FUM_COLS = []   # Column names expected in FUM flows files

PERF_COLS = []  # Column names expected in monthly performance files

PEER_COLS = []  # Column names expected in peer ranking files

# Columns that must be read as float dtype (subset of the above).
ALL_FLOAT_COLS = []

# Decimal places to apply when writing each numeric column: {"Column Name": places}
PRECISION_MAP = {}
