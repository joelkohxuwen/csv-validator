# CSV Validator

A scheduled Python tool that validates and formats monthly CSV files before they are written to a target output folder. Checks performed include filename convention, date validity, column names, float precision, special characters, and stale data detection against the prior month's file.

---

## Project structure

```
csv_validator/
├── csv_validator/          # Python package
│   ├── __init__.py
│   ├── validators.py       # Individual validation functions
│   ├── io_utils.py         # CSV reading and writing
│   └── checker.py          # Orchestration — runs all checks on each file
├── tests/
│   └── __init__.py
├── config.example.py       # Configuration template — safe to commit
├── config.py               # Your local configuration — NOT committed (gitignored)
├── pyproject.toml
├── requirements.txt
├── run.py                  # Entry point
└── run.bat                 # Windows convenience wrapper for Task Scheduler
```

---

## Prerequisites

- Python 3.8 or later
- pip

---

## Setup

### 1. Clone or unzip

```
git clone https://github.com/<your-org>/csv-validator.git
cd csv-validator
```

Or simply unzip the archive and `cd` into the folder.

### 2. Install dependencies

```
pip install -r requirements.txt
```

If your environment already has pandas and numpy (e.g. Anaconda), you can skip this step.

### 3. Create your config file

Copy the template and fill in your values:

```
cp config.example.py config.py       # macOS / Linux
copy config.example.py config.py     # Windows
```

Then open `config.py` and edit each value. Example:

```python
# Folder containing the monthly CSV files to validate
INPUT_PATH = r"C:\Users\username\Documents\monthly_files"

# Folder where validated and formatted CSVs will be written
# Supports UNC network paths
OUTPUT_PATH = r"\\fileserver\shared\output\formatted"

# Directory for log files (created automatically if it does not exist)
LOG_DIR = r"C:\Users\username\csv_validator_logs"

# LBU codes accepted in filenames
LBU_LIST = ["CODE1", "CODE2", "CODE3"]

# Column names expected in each file type
# Copy the exact header row from your CSV templates
FUM_COLS = [
    "Entity Code", "Product Type", "Fund Code", "ISIN",
    "Fund Name", "Valuation Period", "Closing Value", "Net Flows",
]

PERF_COLS = [
    "Fund Code", "Fund Name", "ISIN", "Valuation Period",
    "AUM", "Monthly Return", "Base Currency",
]

PEER_COLS = [
    "Fund Code", "Fund Name", "Valuation Period",
    "Rank 1M", "Rank 3M", "Rank 1Y",
    "Total peers in group 1M", "Total peers in group 1Y",
]

# Subset of the above columns that should be read as float
ALL_FLOAT_COLS = ["Closing Value", "Net Flows", "AUM", "Monthly Return"]

# Number of decimal places to enforce when writing each numeric column
PRECISION_MAP = {
    "Closing Value": 2,
    "Net Flows": 2,
    "AUM": 2,
    "Monthly Return": 6,
}
```

> `config.py` is listed in `.gitignore` and will never be committed.

---

## Running manually

```
python run.py
```

A timestamped log file is written to `LOG_DIR` on every run. Console output mirrors the log.

---

## Scheduling on Windows Task Scheduler

1. Open **Task Scheduler → Create Basic Task**
2. Set your trigger (e.g. monthly, on a specific day)
3. Action → **Start a program**
   - **Program:** `C:\path\to\csv_validator\run.bat`
   - **Start in:** `C:\path\to\csv_validator`
4. Under **General → Security options**
   - Select **"Run whether user is logged on or not"**
   - Tick **"Run with highest privileges"**
   - Ensure the task runs under your **domain account** (required for network share access)

If `python` is not on the system PATH, edit `run.bat` to use the full Python path:

```bat
@echo off
cd /d "%~dp0"
C:\Users\username\AppData\Local\Programs\Python\Python311\python.exe run.py
```

---

## Checks performed

| Check | Description |
|---|---|
| Filename convention | Matches expected pattern; LBU code is in the accepted list |
| Date validity | Date in filename is the last day of the month |
| Valuation Period | Date column in the file matches the filename date; auto-corrected if not |
| Column names | All expected columns are present |
| Special characters | Key identifier columns contain only permitted characters |
| Float precision | Numeric columns do not exceed the configured decimal places |
| Stale data | Current file is compared against the previous month's equivalent file; a warning is logged if the data appears identical |

---

## Output

- **Valid files** are formatted and written to `OUTPUT_PATH`
- **Invalid files** are logged with a per-check breakdown of what failed
- **Stale warnings** are logged separately and do not block a file from being saved
