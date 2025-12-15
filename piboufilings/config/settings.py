"""
Configuration settings for the piboufilings package.

Defaults are intentionally user-writable and have no import-time side effects.
"""

import os
from pathlib import Path

# Base paths (user-overridable via env). Resolution happens at runtime in callers.
DEFAULT_BASE_DIR = Path(os.getenv("PIBOUFILINGS_BASE_DIR", Path.cwd()))
DATA_DIR = Path(os.getenv("PIBOUFILINGS_DATA_DIR", DEFAULT_BASE_DIR / "data_raw")).expanduser().resolve()
LOGS_DIR = Path(os.getenv("PIBOUFILINGS_LOG_DIR", DEFAULT_BASE_DIR / "logs")).expanduser().resolve()

# SEC API settings
SEC_MAX_REQ_PER_SEC = 10
SAFETY_FACTOR = 0.7
SAFE_REQ_PER_SEC = SEC_MAX_REQ_PER_SEC * SAFETY_FACTOR
REQUEST_DELAY = 1 / SAFE_REQ_PER_SEC

# HTTP settings (User-Agent is set at runtime with user-provided name/email)
DEFAULT_HEADERS = {
    "User-Agent": "piboufilings/0.4.0 (set-user-name; contact: set-email@example.com)"
}

# Retry settings
MAX_RETRIES = 5
BACKOFF_FACTOR = 1
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

# Logging settings (used for header schema only)
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
