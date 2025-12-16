# PibouFilings

<h3 style="text-align: center;">A Python library to download, parse, and analyze SEC EDGAR filings at scale. </h3>

[![PyPI](https://img.shields.io/pypi/v/piboufilings?color=blue)](https://pypi.org/project/piboufilings/)
[![License](https://img.shields.io/badge/License-Non_Commercial-blue)](./LICENCE)
[![Downloads](https://img.shields.io/pepy/dt/piboufilings?color=blue)](https://pepy.tech/projects/piboufilings)
[![Open In Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/14CGkio1NVXI6pkuPliAmdBL4sT8u6H-t#scrollTo=wk3GmLlhbidZ)

---


## Filing Contents at a Glance

Unlock structured, analysis-ready data from the SEC’s filings:

- **Filer Metadata:** Clean, machine-ready identifiers and attributes for every SEC registrant.
- **13F Holdings:** Quarter-by-quarter institutional portfolios — securities, CUSIPs, share counts, values, voting authority, and manager relationships.
- **N-PORT Fund Disclosures:** Monthly holdings for mutual funds and ETFs, enriched with fund/series metadata, balance-sheet items, and returns.
- **Section 16 (Forms 3/4/5):** Fully normalized insider trading data — filing metadata, issuer/owner links, transaction tables (non-derivative & derivative), prices, share amounts, and end-of-period holdings.


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
    cik="0001067983",               # Berkshire Hathaway CIK; None: download all available data
    form_type=["13F-HR", "NPORT-P", "SECTION-6"],# String or list of strings
    start_year=2020,
    end_year=2025,
    base_dir="./my_sec_data",       # Optional: Custom directory for parsed CSVs
    log_dir="./my_sec_logs",        # Optional: Custom directory for logs
    raw_data_dir="./my_sec_raw_data",# Optional: Custom directory for raw filings
    keep_raw_files=True,            # Set to False to delete raw .txt files after parsing
    max_workers=5                   # Parallel workers for downloads/parsing
)
```

After running, parsed data will be written to `./my_sec_data` (or `./data_parsed` by default) and logs to `./my_sec_logs` (or `./logs`). Raw filings default to `./data_raw/<identifier>/<form>/<accession>/`; set `raw_data_dir` to place them elsewhere (e.g., `./my_sec_raw_data/<identifier>/<form>/<accession>/`).

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

-   **Automated Downloads:** Fetch 13F, N-PORT, and Section 16 filings (via alias `SECTION-6`) by CIK, date range, or retrieve all available.
-   **Smart Parsing:**
    -   `Form13FParser`: Extracts detailed holdings and cover page data (including `IRS_NUMBER` and `SEC_FILE_NUMBER`) from 13F-HR filings.
    -   `FormNPORTParser`: Parses comprehensive fund/filer information (including `IRS_NUMBER` and `SEC_FILE_NUMBER`) and security holdings from N-PORT-P filings.
    -   `FormSection16Parser`: Normalizes Section 16 ownership XML (Forms 3/4/5) into filing-, transaction-, and holdings-level DataFrames (backed by the `sec16_*.csv` outputs).
-   **Structured CSV Output:**
    -   `13f_info.csv`: Filer information, summary fields, and a `SEC_FILING_URL` back to the original document.
    -   `13f_holdings.csv`: Aggregated holdings data from all processed 13F forms (including the reported CUSIP where available).
    -   `13f_other_managers_reporting.csv`: List of “other managers reporting for this manager” taken from each 13F cover page.
    -   `13f_other_included_managers.csv`: Detailed mapping of numbered “other included managers” so holdings can be joined back to the entities referenced in the table footers.
    -   `nport_filing_info.csv`: Fund/filer information and summaries for N-PORT forms.
    -   `nport_holdings.csv`: Aggregated holdings data from all processed N-PORT forms (includes CUSIP where provided).
    -   `sec16_info.csv`: Filing-level metadata plus issuer/reporting-owner identifiers and role flags for Forms 3/4/5 (alias `SECTION-6`).
    -   `sec16_transactions.csv`: Line-item insider transactions (non-derivative and derivative tables), including codes, dates, share amounts, prices, and post-transaction balances.
    -   `sec16_holdings.csv`: End-of-period holdings snapshots from the Section 16 tables, aligned with issuer and owner identifiers.
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
| Section 16     | `3`, `3/A`, `4`, `4/A`, `5`, `5/A` (or alias `SECTION-6`) | Insider ownership and trade reports filed by officers/directors/10% holders. |
| Ignored        | `NPORT-EX`, `NPORT-EX/A`, `NT NPORT-P`, `NT NPORT-EX` | Exhibit-only or notice filings, typically not parsed for holdings.    |

## Field Reference

<details>
<summary> 13f_info.csv </summary>

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
</details>

<details>
<summary> 13f_holdings.csv </summary>

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

</details>

<details>
<summary> nport_filing_info.csv </summary>

### `nport_filing_info.csv`
| Column | Description |
| --- | --- |
| `ACCESSION_NUMBER` | EDGAR accession number for the N-PORT filing. |
| `CIK` | Central Index Key of the registrant (fund complex). |
| `FORM_TYPE` | Conformed submission type from the header (e.g., `NPORT-P`, `NPORT-P/A`). |
| `PERIOD_OF_REPORT` | Header `CONFORMED PERIOD OF REPORT` date for the filing. |
| `FILED_DATE` | Header `FILED AS OF DATE`; official filing date. |
| `SEC_FILE_NUMBER` | Header `SEC FILE NUMBER`; registrant’s file number (e.g., `811-xxxxx`). |
| `FILM_NUMBER` | SEC film number assigned to the submission. |
| `ACCEPTANCE_DATETIME` | Header `ACCEPTANCE-DATETIME`; EDGAR acceptance timestamp. |
| `PUBLIC_DOCUMENT_COUNT` | Header `PUBLIC DOCUMENT COUNT`; number of public documents attached. |
| `COMPANY_NAME` | Header `COMPANY CONFORMED NAME`; registrant name. |
| `IRS_NUMBER` | EIN/IRS number of the registrant. |
| `STATE_INC` | State of incorporation from the header. |
| `FISCAL_YEAR_END` | Fiscal year end from the header (`MMDD`). |
| `BUSINESS_STREET_1` | Business address street line 1 from the header. |
| `BUSINESS_STREET_2` | Business address street line 2 from the header. |
| `BUSINESS_CITY` | Business address city. |
| `BUSINESS_STATE` | Business address state. |
| `BUSINESS_ZIP` | Business address ZIP code. |
| `BUSINESS_PHONE` | Business phone number from the header. |
| `MAIL_STREET_1` | Mailing address street line 1. |
| `MAIL_STREET_2` | Mailing address street line 2. |
| `MAIL_CITY` | Mailing address city. |
| `MAIL_STATE` | Mailing address state. |
| `MAIL_ZIP` | Mailing address ZIP code. |
| `FORMER_COMPANY_NAMES` | Semicolon-separated former names with change dates, as reported in the header. |
| `REPORT_DATE` | Reporting period end date from N-PORT XML (`genInfo/repPdEnd`). |
| `FUND_REG_NAME` | Fund registrant name from N-PORT XML (`regName`). |
| `FUND_FILE_NUMBER` | Fund file number from N-PORT XML (`regFileNumber`). |
| `FUND_LEI` | Fund registrant LEI from N-PORT XML (`regLei`). |
| `SERIES_NAME` | Series name reported in N-PORT (`seriesName`). |
| `SERIES_LEI` | Series LEI (`seriesLei`). |
| `FUND_TOTAL_ASSETS` | Total assets from `fundInfo/totAssets`. |
| `FUND_TOTAL_LIABS` | Total liabilities from `fundInfo/totLiabs`. |
| `FUND_NET_ASSETS` | Net assets from `fundInfo/netAssets`. |
| `ASSETS_ATTR_MISC_SEC` | Assets attributable to miscellaneous securities (`assetsAttrMiscSec`). |
| `ASSETS_INVESTED` | Net assets invested in securities (`assetsInvested`). |
| `AMT_PAY_ONE_YR_BANKS_BORR` | Amount payable within one year to banks for borrowings. |
| `AMT_PAY_ONE_YR_CTRLD_COMP` | Amount payable within one year to controlled companies. |
| `AMT_PAY_ONE_YR_OTH_AFFIL` | Amount payable within one year to other affiliates. |
| `AMT_PAY_ONE_YR_OTHER` | Amount payable within one year to non-affiliates/other parties. |
| `AMT_PAY_AFT_ONE_YR_BANKS_BORR` | Amount payable after one year to banks for borrowings. |
| `AMT_PAY_AFT_ONE_YR_CTRLD_COMP` | Amount payable after one year to controlled companies. |
| `AMT_PAY_AFT_ONE_YR_OTH_AFFIL` | Amount payable after one year to other affiliates. |
| `AMT_PAY_AFT_ONE_YR_OTHER` | Amount payable after one year to non-affiliates/other parties. |
| `DELAY_DELIVERY` | Delayed delivery and when-issued commitments (`delayDeliv`). |
| `STANDBY_COMMIT` | Standby commitment agreements (`standByCommit`). |
| `LIQUID_PREF` | Amount of liquid preferred stock and similar instruments (`liquidPref`). |
| `CASH_NOT_RPTD_IN_COR_D` | Cash not reported in the core data section (`cshNotRptdInCorD`). |
| `IS_NON_CASH_COLLATERAL` | Flag indicating presence of non-cash collateral at the fund level. |
| `MONTH_1_RETURN` | Total return for the most recent month (`monthlyTotReturn@rtn1`). |
| `MONTH_2_RETURN` | Total return for the second month preceding the report date (`rtn2`). |
| `MONTH_3_RETURN` | Total return for the third month preceding the report date (`rtn3`). |
| `MONTH_1_NET_REALIZED_GAIN` | Net realized gain/loss for the most recent month. |
| `MONTH_2_NET_REALIZED_GAIN` | Net realized gain/loss for the second month preceding the report date. |
| `MONTH_3_NET_REALIZED_GAIN` | Net realized gain/loss for the third month preceding the report date. |
| `MONTH_1_NET_UNREALIZED_APPR` | Net unrealized appreciation/depreciation for the most recent month. |
| `MONTH_2_NET_UNREALIZED_APPR` | Net unrealized appreciation/depreciation for the second month. |
| `MONTH_3_NET_UNREALIZED_APPR` | Net unrealized appreciation/depreciation for the third month. |
| `MONTH_1_REDEMPTION` | Redemptions during the most recent month (`mon1Flow@redemption`). |
| `MONTH_2_REDEMPTION` | Redemptions during the second month. |
| `MONTH_3_REDEMPTION` | Redemptions during the third month. |
| `MONTH_1_REINVESTMENT` | Reinvestments during the most recent month (`mon1Flow@reinvestment`). |
| `MONTH_2_REINVESTMENT` | Reinvestments during the second month. |
| `MONTH_3_REINVESTMENT` | Reinvestments during the third month. |
| `MONTH_1_SALES` | Sales during the most recent month (`mon1Flow@sales`). |
| `MONTH_2_SALES` | Sales during the second month. |
| `MONTH_3_SALES` | Sales during the third month. |
| `CREATED_AT` / `UPDATED_AT` | Timestamps for when the row was generated/updated by PibouFilings. |

</details>

<details>
<summary> nport_holdings.csv </summary>

### `nport_holdings.csv`
| Column | Description |
| --- | --- |
| `ACCESSION_NUMBER` | Accession number of the N-PORT filing this holding comes from. |
| `CIK` | Registrant CIK (fund complex) copied from filing info. |
| `PERIOD_OF_REPORT` | Reporting period end date used for the holding (from `REPORT_DATE`). |
| `FILED_DATE` | Filing date (`FILED AS OF DATE`). |
| `SEC_FILE_NUMBER` | Registrant’s SEC file number associated with the holding. |
| `SECURITY_NAME` | `invstOrSec/name`; name of the security or issuer. |
| `TITLE` | `invstOrSec/title`; security title or description. |
| `CUSIP` | Security CUSIP from `cusip` (or `idenOther` when typed as CUSIP). |
| `LEI` | Security LEI from `lei` (or `idenOther` when typed as LEI). |
| `BALANCE` | `invstOrSec/balance`; quantity or notional amount of the position. |
| `UNITS` | `invstOrSec/units`; unit type or share class for the balance. |
| `CURRENCY` | `invstOrSec/curCd`; currency code of the holding. |
| `VALUE_USD` | `invstOrSec/valUSD`; fair value of the position in U.S. dollars. |
| `PCT_VALUE` | `invstOrSec/pctVal`; position’s percentage of fund net assets. |
| `PAYOFF_PROFILE` | `invstOrSec/payoffProfile`; payoff profile classification (e.g., debt, equity, derivative). |
| `ASSET_CATEGORY` | `invstOrSec/assetCat`; asset category for the holding. |
| `ISSUER_CATEGORY` | `invstOrSec/issuerCat`; issuer category classification. |
| `COUNTRY` | `invstOrSec/invCountry`; country of investment or issuer. |
| `IS_RESTRICTED` | `invstOrSec/isRestrictedSec`; flag if the security is restricted. |
| `FAIR_VALUE_LEVEL` | `invstOrSec/fairValLevel`; fair value hierarchy level (e.g., 1, 2, 3). |
| `IS_CASH_COLLATERAL` | `securityLending/isCashCollateral`; flag if position is posted as cash collateral. |
| `IS_NON_CASH_COLLATERAL` | `securityLending/isNonCashCollateral`; flag if position is posted as non-cash collateral. |
| `IS_LOAN_BY_FUND` | `securityLending/isLoanByFund`; flag if this is a security loaned by the fund. |
| `MATURITY_DATE` | `debtSec@maturityDt`; maturity date for debt securities. |
| `COUPON_KIND` | `debtSec@couponKind`; coupon type (e.g., fixed, floating). |
| `ANNUAL_RATE` | `debtSec@annualizedRt`; annualized interest rate for debt securities. |
| `IS_DEFAULT` | `debtSec@isDefault`; flag if the issuer is in default. |
| `NUM_PAYMENTS_ARREARS` | `debtSec@numPaymentsInArrears`; number of payments in arrears. |
| `DERIVATIVE_CAT` | `derivativeInfo/derivCat`; derivative category for the position. |
| `COUNTERPARTY_NAME` | `derivativeInfo/counterpartyName`; name of the derivative counterparty. |
| `ABS_CAT` | `assetBackedSec/absCat`; asset-backed security category. |
| `ABS_SUB_CAT` | `assetBackedSec/absSubCat`; asset-backed security subcategory. |
| `CREATED_AT` / `UPDATED_AT` | Timestamps for when the row was generated/updated by PibouFilings. |

</details>

<details>
<summary> sec16_info.csv </summary>

### `sec16_info.csv`
| Column | Description |
| --- | --- |
| `ACCESSION_NUMBER` | EDGAR accession number for the Section 16 filing. |
| `DOCUMENT_TYPE` | XML `documentType` (e.g., `3`, `4`, `5`, `3/A`, `4/A`, `5/A`). |
| `PERIOD_OF_REPORT` | XML `periodOfReport`; the reporting period date for the form. |
| `DATE_FILED` | Header `FILED AS OF DATE`; official filing date. |
| `ACCEPTANCE_DATETIME` | Header `ACCEPTANCE-DATETIME`; EDGAR acceptance timestamp. |
| `SCHEMA_VERSION` | Section 16 XML `schemaVersion` used by the filing. |
| `ISSUER_CIK` | XML `issuerCik`; CIK of the issuer whose securities are reported. |
| `ISSUER_NAME` | XML `issuerName`; legal name of the issuer. |
| `ISSUER_TRADING_SYMBOL` | XML `issuerTradingSymbol`; issuer’s ticker symbol. |
| `RPT_OWNER_CIK` | XML `rptOwnerCik`; CIK of the reporting owner (insider). |
| `RPT_OWNER_NAME` | XML `rptOwnerName`; name of the reporting owner. |
| `RPT_OWNER_STREET1` | XML `rptOwnerStreet1`; first address line for the reporting owner. |
| `RPT_OWNER_STREET2` | XML `rptOwnerStreet2`; second address line, if present. |
| `RPT_OWNER_CITY` | XML `rptOwnerCity`; city of the reporting owner. |
| `RPT_OWNER_STATE` | XML `rptOwnerState`; state or province of the reporting owner. |
| `RPT_OWNER_ZIP` | XML `rptOwnerZipCode`; postal/ZIP code of the reporting owner. |
| `IS_DIRECTOR` | XML `isDirector`; boolean flag if the owner is a director of the issuer. |
| `IS_OFFICER` | XML `isOfficer`; boolean flag if the owner is an officer of the issuer. |
| `OFFICER_TITLE` | XML `officerTitle`; officer role/title (e.g., “Chief Executive Officer”). |
| `IS_TEN_PCT_OWNER` | XML `isTenPercentOwner`; boolean flag for ≥10% beneficial ownership. |
| `IS_OTHER` | XML `isOther`; boolean flag indicating any “other” relationship to the issuer. |
| `OTHER_TEXT` | XML `otherText`; description of the “other” relationship when `IS_OTHER` is true. |
| `REMARKS` | XML `remarks`; free-form remarks section from the filing. |
| `SEC_FILING_URL` | Direct HTTPS link to the raw EDGAR text file that was parsed. |
| `CREATED_AT` / `UPDATED_AT` | Timestamps for when the row was generated/updated by PibouFilings. |

</details>

<details>
<summary> sec16_transactions.csv </summary>

### `sec16_transactions.csv`
| Column | Description |
| --- | --- |
| `ACCESSION_NUMBER` | Accession number of the filing this transaction comes from. |
| `DOCUMENT_TYPE` | Filing-level `documentType` (e.g., `3`, `4`, `5`). |
| `PERIOD_OF_REPORT` | Filing-level `periodOfReport`; reporting period of the form. |
| `ISSUER_CIK` | Issuer CIK from `issuerCik`. |
| `ISSUER_NAME` | Issuer name from `issuerName`. |
| `ISSUER_TRADING_SYMBOL` | Issuer ticker symbol from `issuerTradingSymbol`. |
| `RPT_OWNER_CIK` | Reporting owner CIK from `rptOwnerCik`. |
| `RPT_OWNER_NAME` | Reporting owner name from `rptOwnerName`. |
| `TABLE_TYPE` | Source table: `NON_DERIVATIVE` or `DERIVATIVE`. |
| `SECURITY_TITLE` | XML `securityTitle/value`; title of the security transacted. |
| `TRANSACTION_FORM_TYPE` | XML `transactionCoding/transactionFormType`; form subtype for the line. |
| `TRANSACTION_CODE` | XML `transactionCoding/transactionCode`; Form 4 transaction code (e.g., `P`, `S`, `M`). |
| `EQUITY_SWAP_INVOLVED` | XML `transactionCoding/equitySwapInvolved`; flag if an equity swap is involved. |
| `TRANSACTION_DATE` | XML `transactionDate/value`; date on which the transaction occurred. |
| `DEEMED_EXECUTION_DATE` | XML `deemedExecutionDate/value`; deemed execution date, if reported. |
| `TRANSACTION_SHARES` | XML `transactionAmounts/transactionShares/value`; number of shares/units transacted. |
| `TRANSACTION_PRICE_PER_SHARE` | XML `transactionAmounts/transactionPricePerShare/value`; price per share or unit. |
| `SHARES_OWNED_FOLLOWING_TRANSACTION` | XML `postTransactionAmounts/sharesOwnedFollowingTransaction/value`; shares beneficially owned after the transaction. |
| `DIRECT_OR_INDIRECT_OWNERSHIP` | XML `ownershipNature/directOrIndirectOwnership/value`; typically `D` (direct) or `I` (indirect). |
| `NATURE_OF_OWNERSHIP` | XML `ownershipNature/natureOfOwnership/value`; text describing the nature of ownership. |
| `CONVERSION_OR_EXERCISE_PRICE` | For derivative transactions: XML `conversionOrExercisePrice/value`; exercise/conversion price. |
| `EXERCISE_DATE` | XML `exerciseDate/value`; date when the derivative becomes exercisable. |
| `EXPIRATION_DATE` | XML `expirationDate/value`; expiration date of the derivative instrument. |
| `UNDERLYING_SECURITY_TITLE` | XML `underlyingSecurity/underlyingSecurityTitle/value`; title of the underlying security. |
| `UNDERLYING_SECURITY_SHARES` | XML `underlyingSecurity/underlyingSecurityShares/value`; number of underlying shares represented. |
| `FOOTNOTE_IDS` | Comma-separated list of `footnoteId` values referenced by this transaction row. |
| `CREATED_AT` / `UPDATED_AT` | Timestamps for when the row was generated/updated by PibouFilings. |

</details>

<details>
<summary> sec16_holdings.csv </summary>

### `sec16_holdings.csv`
| Column | Description |
| --- | --- |
| `ACCESSION_NUMBER` | Accession number of the filing this holding comes from. |
| `DOCUMENT_TYPE` | Filing-level `documentType` (e.g., `3`, `4`, `5`). |
| `PERIOD_OF_REPORT` | Filing-level `periodOfReport`; date of the ownership snapshot. |
| `ISSUER_CIK` | Issuer CIK from `issuerCik`. |
| `ISSUER_NAME` | Issuer name from `issuerName`. |
| `ISSUER_TRADING_SYMBOL` | Issuer ticker symbol from `issuerTradingSymbol`. |
| `RPT_OWNER_CIK` | Reporting owner CIK from `rptOwnerCik`. |
| `RPT_OWNER_NAME` | Reporting owner name from `rptOwnerName`. |
| `TABLE_TYPE` | Source table: `NON_DERIVATIVE_HOLDING` or `DERIVATIVE_HOLDING`. |
| `SECURITY_TITLE` | XML `securityTitle/value`; title of the held security or derivative. |
| `SHARES_OWNED` | XML `postTransactionAmounts/sharesOwnedFollowingTransaction/value`; shares/units beneficially owned. |
| `DIRECT_OR_INDIRECT_OWNERSHIP` | XML `ownershipNature/directOrIndirectOwnership/value`; `D` (direct) or `I` (indirect). |
| `NATURE_OF_OWNERSHIP` | XML `ownershipNature/natureOfOwnership/value`; text describing the nature of ownership. |
| `CONVERSION_OR_EXERCISE_PRICE` | For derivative holdings: XML `conversionOrExercisePrice/value`; exercise/conversion price. |
| `EXERCISE_DATE` | XML `exerciseDate/value`; date when the derivative becomes exercisable. |
| `EXPIRATION_DATE` | XML `expirationDate/value`; expiration date of the derivative holding. |
| `UNDERLYING_SECURITY_TITLE` | XML `underlyingSecurity/underlyingSecurityTitle/value`; title of the underlying security. |
| `UNDERLYING_SECURITY_SHARES` | XML `underlyingSecurity/underlyingSecurityShares/value`; number of underlying shares represented. |
| `FOOTNOTE_IDS` | Comma-separated `footnoteId` values referenced by this holding row. |
| `CREATED_AT` / `UPDATED_AT` | Timestamps for when the row was generated/updated by PibouFilings. |

</details>
<br>
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

PibouFilings is an independent, open-source research tool and is not affiliated with, endorsed by, or in any way connected to the U.S. Securities and Exchange Commission (SEC), the EDGAR system, CUSIP Global Services, or any other proprietary data provider.

PibouFilings processes only publicly accessible EDGAR filings and does not incorporate external or third-party datasets. All information is extracted directly from the original SEC submissions. Some filings may contain licensed proprietary identifiers (including, but not limited to, CUSIP, ISIN, and CINS codes). These identifiers are retained solely as they appear in the source filings to support accurate record reconciliation. PibouFilings does not grant, sublicense, or convey any rights to such identifiers. Users are solely responsible for securing any necessary licenses and ensuring compliance with all applicable intellectual property or data-usage restrictions.

This project is distributed under a Non-Commercial License and is intended solely for research and educational purposes. This license governs the PibouFilings source code and the processed formats generated by the library; it does not supersede or modify any third-party rights associated with identifiers contained in the filings. Any commercial use or redistribution of the software or its outputs requires prior written permission from the author.

Users must comply with the SEC’s [Fair Access guidelines](https://www.sec.gov/edgar/sec-api-documentation), including the use of a valid User-Agent and adherence to rate-limit requirements. By using PibouFilings, you acknowledge these obligations.

The author makes no warranty regarding the accuracy, completeness, or suitability of any information produced by this tool and disclaims all liability for any losses or damages arising from its use. Users assume full responsibility for how they apply the software and for any data generated through it.

For questions about usage or compliance, please contact the author directly.
