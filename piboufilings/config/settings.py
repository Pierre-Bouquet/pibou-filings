"""
Configuration settings for the piboufilings package.
"""

import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data_raw"
LOGS_DIR = BASE_DIR / "logs"

# SEC API settings
SEC_MAX_REQ_PER_SEC = 10
SAFETY_FACTOR = 0.7
SAFE_REQ_PER_SEC = SEC_MAX_REQ_PER_SEC * SAFETY_FACTOR
REQUEST_DELAY = 1 / SAFE_REQ_PER_SEC

# HTTP settings
DEFAULT_HEADERS = {
    "User-Agent": "piboufilings/0.1.0 (thisisgeorgeemail@gmail.com)"
}

# Retry settings
MAX_RETRIES = 5
BACKOFF_FACTOR = 1
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

# Logging settings
LOG_FILE_PATH = LOGS_DIR / "download_log.csv"
LOG_HEADERS = [
    "timestamp",
    "cik",
    "accession_number",
    "period",
    "form_type",
    "status",
    "error_code",
    "error_msg"
]

# Create necessary directories
DATA_DIR.mkdir(exist_ok=True)
