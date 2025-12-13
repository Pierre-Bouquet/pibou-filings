# PibouFilings

A Python library to download, parse, and analyze SEC EDGAR filings—especially 13F and N-PORT filings—at scale.

[![PyPI version](https://badge.fury.io/py/piboufilings.svg)](https://badge.fury.io/py/piboufilings)
[![License: Non-Commercial](https://img.shields.io/badge/License-Non_Commercial-blue.svg)](LICENSE)


## Installation

```bash
pip install piboufilings
```

## Quick Start

The primary way to use `piboufilings` is with the `get_filings()` function:

```python
from piboufilings import get_filings

# Remember to replace with your actual email for the User-Agent
USER_AGENT_EMAIL = "yourname@example.com"
USER_NAME = "Your Name or Company"  # Add your name or company

get_filings(
    user_name=USER_NAME,
    user_agent_email=USER_AGENT_EMAIL,
    cik="0001067983",               # Berkshire Hathaway CIK
    form_type=["13F-HR", "NPORT-P"],# String or list of strings
    start_year=2020,
    end_year=2025,
    base_dir="./my_sec_data",       # Optional: Custom directory for parsed CSVs
    log_dir="./my_sec_logs",        # Optional: Custom directory for logs
    keep_raw_files=True,            # Set to False to delete raw .txt files after parsing
    max_workers=5                   # Parallel workers for downloads/parsing
)
```

After running, parsed data will be written to `./my_sec_data` (or `./data_parsed` by default) and logs to `./my_sec_logs` (or `./logs`). Raw filings are always staged under `data_raw/raw/<identifier>/<form>/<accession>/` so you can re-parse or audit any download at a later date.

CIK number can be obtained from [SEC EDGAR Search Filings](https://www.sec.gov/search-filings).

---

## Filing Structure & Identifiers
PibouFilings organizes EDGAR data around two key public identifiers:

*   **IRS_NUMBER:** The Employer Identification Number (EIN) issued by the U.S. Internal Revenue Service. It uniquely identifies the legal entity submitting the filing.
*   **SEC_FILE_NUMBER:** The registration number assigned by the SEC. It distinguishes different types of filers and registrations (e.g., 028-xxxxx for 13F filers, 811-xxxxx for investment companies).

These two identifiers are public information, managed by U.S. federal agencies (IRS and SEC respectively), and act as the primary keys for organizing and indexing filings within PibouFilings.

### Filing Index
All parsed filings are first grouped by `IRS_NUMBER` and `SEC_FILE_NUMBER` into a structured index of registrants.

This allows you to track a fund or manager across multiple filings and time periods with full auditability.

### Holdings Reports
Each individual security holding (from 13F or N-PORT forms) is reported with a corresponding `SEC_FILE_NUMBER`.

This structure lets you link back any security-level data to the registered filing entity while keeping sensitive personal identifiers (e.g., signatory names) optional or excluded. When a filing discloses a CUSIP or similar identifier, it is preserved in the resulting CSVs so you can reconcile holdings downstream (see the legal notice below for usage requirements).

## Key Features

-   **Automated Downloads:** Fetch 13F and N-PORT filings by CIK, date range, or retrieve all available.
-   **Smart Parsing:**
    -   `Form13FParser`: Extracts detailed holdings and cover page data (including `IRS_NUMBER` and `SEC_FILE_NUMBER`) from 13F-HR filings.
    -   `FormNPORTParser`: Parses comprehensive fund/filer information (including `IRS_NUMBER` and `SEC_FILE_NUMBER`) and security holdings from N-PORT-P filings.
-   **Structured CSV Output:**
    -   `13f_info.csv`: Filer information, summary fields, and a `SEC_FILING_URL` back to the original document.
    -   `13f_holdings.csv`: Aggregated holdings data from all processed 13F forms (including the reported CUSIP where available).
    -   `13f_other_managers_reporting.csv`: List of “other managers reporting for this manager” taken from each 13F cover page.
    -   `13f_other_included_managers.csv`: Detailed mapping of numbered “other included managers” so holdings can be joined back to the entities referenced in the table footers.
    -   `nport_filing_info.csv`: Fund/filer information and summaries for N-PORT forms.
    -   `nport_holdings.csv`: Aggregated holdings data from all processed N-PORT forms.
-   **Robust EDGAR Interaction:**
    -   Adheres to SEC rate limits (10 req/sec) via a configurable global token bucket rate limiter.
    -   Comprehensive retry mechanism for network requests (handles connection errors, read errors, and specific HTTP status codes like 429, 5xx).
-   **Efficient & Configurable:**
    -   Parallelized downloads using `ThreadPoolExecutor` for faster processing of CIKs with multiple filings.
    -   Option to `keep_raw_files` (default True) or delete them after processing.
    -   Customizable directories for data and logs.
-   **Detailed Logging:**
    -   Records operations to a daily CSV log file (e.g., `logs/filing_operations_YYYYMMDD.csv`).
    -   Logs include timestamps, descriptive `operation_type` (e.g., `DOWNLOAD_SINGLE_FILING_SUCCESS`), CIK, accession number, success/failure status, error messages, and specific `error_code` (like HTTP status codes) where applicable.
-   **Data Analytics Ready:** Pandas DataFrames are used internally and for the final CSV outputs.
-   **Handles Amendments:** Automatically processes and correctly identifies amended filings (e.g., `13F-HR/A`, `NPORT-P/A`).


## Supported Form Types

| Category       | Supported Forms                               | Notes                                                                 |
|----------------|-----------------------------------------------|-----------------------------------------------------------------------|
| 13F Filings    | `13F-HR`, `13F-HR/A`                          | Institutional Investment Manager holdings reports.                    |
| N-PORT Filings | `NPORT-P`, `NPORT-P/A`                        | Monthly portfolio holdings for registered investment companies (funds). |
| Ignored        | `NPORT-EX`, `NPORT-EX/A`, `NT NPORT-P`, `NT NPORT-EX` | Exhibit-only or notice filings, typically not parsed for holdings.    |

## Field Reference

### `13f_info.csv`
| Column | Description |
| --- | --- |
| `CIK` | Central Index Key for the registrant (10-digit, zero padded). |
| `REPORT_TYPE` | Verbatim `reportType` value (e.g., “13F COMBINATION REPORT”). |
| `IRS_NUMBER` | Employer Identification Number (EIN) extracted from the header. |
| `SEC_FILE_NUMBER` | The filer’s Form 13F file number (028-xxxxx). |
| `DOC_TYPE` | Conformed submission type (e.g., `13F-HR`, `13F-HR/A`). |
| `CONFORMED_DATE` | Period of report in `YYYY-MM-DD`. |
| `FILED_DATE` | Filing date in `YYYY-MM-DD`. |
| `ACCEPTANCE_DATETIME` | EDGAR acceptance timestamp (`YYYY-MM-DD HH:MM:SS`). |
| `PUBLIC_DOCUMENT_COUNT` | Number of public documents attached to the submission. |
| `SEC_ACT` | Applicable Securities Act reference (e.g., `1934 Act`). |
| `FILM_NUMBER` | SEC film number assigned to the filing. |
| `NUMBER_TRADES` | `tableEntryTotal` (count of holdings rows). |
| `TOTAL_VALUE` | `tableValueTotal` (total holdings value reported, thousands USD). |
| `OTHER_INCLUDED_MANAGERS_COUNT` | `otherIncludedManagersCount` element value. |
| `IS_CONFIDENTIAL_OMITTED` | `true/false` flag from `isConfidentialOmitted`. |
| `SIGNATURE_NAME`/`TITLE`/`CITY`/`STATE` | Signatory block metadata. |
| `AMENDMENT_FLAG` | `Y` or `N` depending on whether the filing is an amendment. |
| `MAIL_*`, `BUSINESS_*` fields | Mailing and business address lines captured from the header. |
| `COMPANY_NAME` | “COMPANY CONFORMED NAME” value. |
| `BUSINESS_PHONE` | Phone number provided in the header. |
| `STATE_INC` | State of incorporation. |
| `FORMER_COMPANY_NAME` | Most recent former name, if supplied. |
| `FISCAL_YEAR_END` | Fiscal year end in `MMDD`. |
| `STANDARD_INDUSTRIAL_CLASSIFICATION` | SIC description reported by the filer. |
| `SEC_FILING_URL` | Direct HTTPS link to the raw EDGAR text file that was parsed. |
| `CREATED_AT` / `UPDATED_AT` | Timestamps for when the row was generated by PibouFilings. |

### `13f_holdings.csv`
| Column | Description |
| --- | --- |
| `SEC_FILE_NUMBER` | File number of the reporting manager for the holding. |
| `CONFORMED_DATE` | Reporting period (`YYYY-MM-DD`). |
| `NAME_OF_ISSUER` | `nameOfIssuer` element from the XML table. |
| `TITLE_OF_CLASS` | Security class (`titleOfClass`). |
| `CUSIP` | Reported CUSIP identifier (exactly as filed). |
| `SHARE_VALUE` | Market value reported (`value`, in thousands USD). |
| `SHARE_AMOUNT` | Number of shares or principal amount (`sshPrnamt`). |
| `SH_PRN` | Share/Principal type (`sshPrnamtType`, e.g., `SH`, `PRN`). |
| `PUT_CALL` | `putCall` tag for option positions (often blank). |
| `DISCRETION` | `investmentDiscretion` field (`SOLE`, `SHARED`, `DEFINED`). |
| `SOLE_VOTING_AUTHORITY` | Shares with sole voting authority. |
| `SHARED_VOTING_AUTHORITY` | Shares with shared voting authority. |
| `NONE_VOTING_AUTHORITY` | Shares with no voting authority. |
| `CREATED_AT` / `UPDATED_AT` | Generation timestamps for each holding row. |

The helper CSVs `13f_other_managers_reporting.csv` and `13f_other_included_managers.csv` mirror the tables from each cover page and contain the SEC file numbers and names necessary to interpret the numbered manager references that appear in the holdings.

---

## Disclaimer


### Identifier & Data Usage Notice

PibouFilings emits the identifiers that appear in the original documents (e.g., CUSIP, CINS, ISIN, LEI). Those identifiers remain the property of their respective issuers (for example, CUSIP Global Services and the American Bankers Association for CUSIPs). By using this software you agree to:

1. Use such identifiers only in accordance with the licensing terms imposed by their owners.
2. Obtain any required licenses for commercial redistribution or downstream products that include those identifiers.
3. Remove or redact identifiers if your use case is not covered by those licenses.

The project itself does not grant any rights to proprietary identifier datasets.

### General Disclaimer

PibouFilings is an independent, open-source research tool and is not affiliated with, endorsed by, or in any way connected to the U.S. Securities and Exchange Commission (SEC), the EDGAR system, or any proprietary data providers.

All data processed by this library is sourced exclusively from publicly accessible EDGAR filings. While certain filings may contain proprietary identifiers (such as CUSIP, ISIN, CINS, and similar licensed codes), these fields are preserved verbatim in the outputs so you can reconcile the records; compliance with any licensing restrictions remains your responsibility (see the notice above).

This project is governed by a Non-Commercial License and is intended solely for educational and research purposes. Any commercial redistribution or use of the software or its outputs without prior express written permission from the author is strictly prohibited.

Users are required to comply with [SEC Fair Access guidelines](https://www.sec.gov/edgar/sec-api-documentation), including but not limited to the use of a valid User-Agent and adherence to their request rate limits. By using PibouFilings, you acknowledge and agree to adhere to these terms. 

The author makes no representations or warranties regarding the accuracy, completeness, or usefulness of the information provided through this tool, and shall not be liable for any losses or damages arising out of the use of or reliance upon such information. Users assume all responsibility for their use of the software and the data generated therein.

For any questions about the use of this software or its compliance frameworks, please contact the author directly.
