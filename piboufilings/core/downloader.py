"""
Core functionality for downloading SEC filings.
"""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm
import re
import time
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config.settings import (
    SEC_MAX_REQ_PER_SEC,
    SAFETY_FACTOR,
    SAFE_REQ_PER_SEC,
    REQUEST_DELAY,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    BACKOFF_FACTOR,
    RETRY_STATUS_CODES,
    DATA_DIR
)

from .logger import FilingLogger
from .rate_limiter import GlobalRateLimiter

class SECDownloader:
    """A class to handle downloading SEC EDGAR filings."""
    
    def __init__(self, user_name: str, user_agent_email: str, package_version: str = "0.3.0", log_dir: str = "./logs", max_workers: int = 5):
        """
        Initialize the SEC downloader.
        
        Args:
            user_name: Name of the user or organization
            user_agent_email: Contact email address for SEC's fair access rules (required)
            package_version: Version of the piboufilings package
            log_dir: Directory to store log files (defaults to './logs')
            max_workers: Maximum number of parallel download workers (defaults to 5)
        """
        self.session = self._setup_session()
        
        # Create headers with the provided user_agent
        self.headers = DEFAULT_HEADERS.copy()
        self.headers["User-Agent"] = f"piboufilings/{package_version} ({user_name}; contact: {user_agent_email})"
            
        self.logger = FilingLogger(log_dir=log_dir)
        self.last_request_time = time.time() - REQUEST_DELAY  # Initialize to allow immediate first request
        self.max_workers = max_workers
        
        # Initialize the global rate limiter
        self.rate_limiter = GlobalRateLimiter(
            rate=SEC_MAX_REQ_PER_SEC,
            safety_factor=SAFETY_FACTOR
        )
            
    def download_filings(
        self,
        cik: str,
        form_type: str,
        start_year: int,
        end_year: Optional[int] = None,
        save_raw: bool = True,
        show_progress: bool = True,
        index_data_subset: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Download all filings of a specific type for a company within a date range.
        
        Args:
            cik: Company CIK number (will be zero-padded to 10 digits)
            form_type: Type of form to download (e.g., '13F-HR')
            start_year: Starting year for the search
            end_year: Ending year (defaults to current year)
            save_raw: Whether to save raw filing data (defaults to True)
            show_progress: Whether to show progress bars (defaults to True)
            index_data_subset: Optional pre-filtered DataFrame of index entries for this specific CIK and form type.
                               If provided, skips fetching and filtering the main index.
            
        Returns:
            pd.DataFrame: DataFrame containing information about downloaded filings
        """
        try:
            # Normalize CIK
            cik = str(cik).zfill(10)
            
            company_filings: pd.DataFrame
            
            if index_data_subset is not None and not index_data_subset.empty:
                # Use the provided subset directly
                company_filings = index_data_subset
                # Ensure the subset is indeed for the given CIK and form_type as a safeguard, though
                # the caller should ideally ensure this.
                # This filtering on the subset is a light check.
                company_filings = company_filings[
                    (company_filings["CIK"] == cik) &
                    (company_filings["Form Type"].str.contains(form_type, na=False))
                ]
                if company_filings.empty:
                    self.logger.log_operation(
                        cik=cik,
                        operation_type="SUBSET_VALIDATION_ERROR",
                        download_success=False,
                        download_error_message=f"Provided index_data_subset for {form_type} and {cik} resulted in no filings after re-check."
                    )
                    return pd.DataFrame()

            else:
                # Fetch index data if subset is not provided or is empty
                index_data = self.get_sec_index_data(start_year, end_year)
                
                if index_data.empty:
                    self.logger.log_operation(
                        cik=cik,
                        operation_type="INDEX_FETCH_NO_RESULTS_FOR_DOWNLOAD",
                        download_success=False,
                        download_error_message=f"Failed to get index data for years {start_year}-{end_year} (when attempting to download for CIK {cik}, form {form_type})"
                    )
                    return pd.DataFrame()

                # Filter for the specific company and form type
                company_filings = index_data[
                    (index_data["CIK"] == cik) & 
                    (index_data["Form Type"].str.contains(form_type, na=False))
                ]
            
            if company_filings.empty:
                self.logger.log_operation(
                    cik=cik,
                    operation_type="NO_FILINGS_FOUND_FOR_CIK_FORM_IN_INDEX",
                    download_success=False,
                    download_error_message=f"No {form_type} filings found for {cik} (date range {start_year}-{end_year or 'current year'})"
                )
                return pd.DataFrame()
            
            # Download filings in parallel
            downloaded_filings_info = [] # Renamed to avoid conflict
            
            # Create a progress bar for the user
            pbar = None
            if show_progress:
                pbar = tqdm(
                    total=len(company_filings),
                    desc=f"Downloading filings for CIK {cik}"
                )
            
            # Define function to download a single filing
            def download_single_filing_wrapper(filing):
                try:
                    # Extract accession number from Filename
                    accession_match = re.search(r'edgar/data/\d+/([0-9\-]+)\.txt', filing["Filename"])
                    if not accession_match:
                        self.logger.log_operation(
                            cik=cik,
                            operation_type="FILENAME_PARSE_ERROR_IN_WRAPPER",
                            download_success=False,
                            download_error_message=f"Invalid filename format: {filing['Filename']}"
                        )
                        return None
                            
                    accession_number = accession_match.group(1)

                    detected_form_type = form_type
                    if "Form Type" in filing and pd.notna(filing["Form Type"]):
                        detected_form_type = str(filing["Form Type"]).strip() or form_type
                    
                    # Download the filing
                    filing_info = self._download_single_filing(
                        cik=cik,
                        accession_number=accession_number,
                        form_type=detected_form_type,
                        save_raw=save_raw
                    )
                    
                    # Update progress bar
                    if pbar:
                        pbar.update(1)
                        
                    return filing_info
                except Exception as e:
                    # Log the error but don't propagate it to allow other downloads to continue
                    self.logger.log_operation(
                        cik=cik,
                        operation_type="DOWNLOAD_FILING_WRAPPER_GENERAL_ERROR",
                        download_success=False,
                        download_error_message=f"Error downloading filing: {str(e)}"
                    )
                    if pbar:
                        pbar.update(1)
                    return None
            
            # Use ThreadPoolExecutor to download filings in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all download tasks
                future_to_filing = {
                    executor.submit(download_single_filing_wrapper, filing_row): filing_row # Pass the row (Series)
                    for _, filing_row in company_filings.iterrows() # Iterate over rows
                }
                
                # Process completed downloads
                for future in as_completed(future_to_filing):
                    filing_info_result = future.result() # Renamed
                    if filing_info_result:
                        downloaded_filings_info.append(filing_info_result)
            
            # Close progress bar
            if pbar:
                pbar.close()
            
            self.logger.log_operation(
                cik=cik,
                operation_type="DOWNLOAD_FILINGS_BATCH_PROCESSED",
                download_success=True,
                download_error_message=f"Successfully processed {len(downloaded_filings_info)} filings for download",
                error_code=200
            )
            return pd.DataFrame(downloaded_filings_info) # Use the collected list

        except Exception as e:
            self.logger.log_operation(
                cik=cik,
                operation_type="DOWNLOAD_FILINGS_UNHANDLED_EXCEPTION",
                download_success=False,
                download_error_message=f"Error downloading filings: {str(e)}"
            )
            return pd.DataFrame()
    
    def _respect_rate_limit(self):
        """Ensure requests comply with SEC rate limits using the global rate limiter."""
        # Use the global rate limiter to control request rate
        self.rate_limiter.acquire(block=True)
    
    def _download_single_filing(
        self,
        cik: str,
        accession_number: str,
        form_type: str,
        save_raw: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Download a single filing and save it if requested.
        
        Args:
            cik: Company CIK number
            accession_number: Filing accession number
            form_type: Type of form
            save_raw: Whether to save the raw filing
            
        Returns:
            Optional[Dict[str, Any]]: Information about the downloaded filing
        """
        try:
            # Construct the URL
            # The accession number might contain hyphens, which need to be removed for the URL
            clean_accession = accession_number.replace('-', '')
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{clean_accession}/{accession_number}.txt"
            
            # Apply rate limiting before making the request
            self._respect_rate_limit()
            
            # Download the filing
            response = self.session.get(url, headers=self.headers)
            # Log the request details regardless of success/failure
            # self.logger.log_operation( ... ) # Consider adding a generic request log here if needed
            
            if response.status_code != 200:
                self.logger.log_operation(
                    cik=cik,
                    accession_number=accession_number,
                    operation_type="DOWNLOAD_SINGLE_FILING_HTTP_ERROR",
                    download_success=False,
                    download_error_message=f"HTTP error {response.status_code} for {url}",
                    error_code=response.status_code
                )
                return None
            
            # Save raw filing if requested
            raw_path = None
            if save_raw:
                try:
                    form_13f_file_number_for_save = None
                    if "13F" in form_type: # Check if it's a 13F type filing
                        match = re.search(r"form13FFileNumber>([^<]+)</", response.text)
                        if match:
                            form_13f_file_number_for_save = match.group(1).strip()
                        else:
                            form_13f_file_number_for_save = "unknown_13F_file_number" # Placeholder

                    raw_path = self._save_raw_filing(
                        cik=cik,
                        form_type=form_type,
                        accession_number=accession_number,
                        content=response.text,
                        form_13f_file_number_for_path=form_13f_file_number_for_save
                    )
                except IOError as e:
                    self.logger.log_operation(
                        cik=cik,
                        accession_number=accession_number,
                        operation_type="SAVE_RAW_FILING_IO_ERROR",
                        download_success=True,
                        parse_success=False,
                        download_error_message=f"Failed to save raw filing: {str(e)}"
                    )
            
            self.logger.log_operation(
                cik=cik,
                accession_number=accession_number,
                operation_type="DOWNLOAD_SINGLE_FILING_SUCCESS",
                download_success=True
            )
            
            return {
                "cik": cik,
                "accession_number": accession_number,
                "form_type": form_type,
                "download_date": datetime.now().strftime("%Y-%m-%d"),
                "raw_path": raw_path,
                "url": url
            }
        except requests.RequestException as e:
            status_code = None
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
            self.logger.log_operation(
                cik=cik,
                accession_number=accession_number,
                operation_type="DOWNLOAD_SINGLE_FILING_REQUEST_EXCEPTION",
                download_success=False,
                download_error_message=f"Request error: {str(e)}",
                error_code=status_code # Log status_code if available from exception
            )
            return None
        except Exception as e:
            self.logger.log_operation(
                cik=cik,
                accession_number=accession_number,
                operation_type="DOWNLOAD_SINGLE_FILING_UNEXPECTED_ERROR",
                download_success=False,
                download_error_message=f"Unexpected error: {str(e)}"
            )
            return None
    
    def _save_raw_filing(
        self,
        cik: str,
        form_type: str,
        accession_number: str,
        content: str,
        form_13f_file_number_for_path: Optional[str] = None
    ) -> str:
        """
        Save a raw filing to disk.
        
        Args:
            cik: Company CIK number
            form_type: Type of form
            accession_number: Filing accession number
            content: Raw filing content
            form_13f_file_number_for_path: Optional form 13F file number for directory and filename
            
        Returns:
            str: Path to the saved file
            
        Raises:
            IOError: If there is an error creating directories or writing the file
        """
        # Ensure DATA_DIR exists
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(os.path.join(DATA_DIR, "raw"), exist_ok=True)
        
        # Determine primary directory based on form type
        primary_identifier_dir: str
        if "13F" in form_type and form_13f_file_number_for_path and form_13f_file_number_for_path != "unknown_13F_file_number":
            # Sanitize form_13f_file_number_for_path for use as a directory name
            sane_form_13f_fn = form_13f_file_number_for_path.replace('-', '_').replace('/', '_')
            primary_identifier_dir = os.path.join(DATA_DIR, "raw", sane_form_13f_fn)
        else:
            primary_identifier_dir = os.path.join(DATA_DIR, "raw", cik)
        
        #Check if this is an exhibit filing
        is_exhibit = "EX" in form_type
        if is_exhibit:
            return np.nan # Using np.nan to signify not saved, consistent with potential existing logic
        # Check if this is an amendment filing
        is_amendment = form_type.endswith("/A") or "/A" in form_type
        
        # Handle the form type path correctly
        base_form_type = form_type.split("/A")[0] if is_amendment else form_type
        # The form_dir is now relative to the primary_identifier_dir
        form_dir = os.path.join(primary_identifier_dir, base_form_type)
        os.makedirs(form_dir, exist_ok=True)
        
        # If it's an amendment, create an A subfolder
        if is_amendment:
            a_dir = os.path.join(form_dir, "A")
            os.makedirs(a_dir, exist_ok=True)
            output_dir = a_dir
        else:
            output_dir = form_dir
        
        # Create an accession-specific directory for SEC file number storage to avoid overwrites
        accession_specific_dir = output_dir
        if "13F" in form_type and form_13f_file_number_for_path and form_13f_file_number_for_path != "unknown_13F_file_number":
            safe_accession_dir = accession_number.replace('/', '_')
            accession_specific_dir = os.path.join(output_dir, safe_accession_dir)
            os.makedirs(accession_specific_dir, exist_ok=True)
        
        # Determine filename based on form type
        filename: str
        if "13F" in form_type and form_13f_file_number_for_path and form_13f_file_number_for_path != "unknown_13F_file_number":
            # Sanitize form_13f_file_number_for_path for use as a filename
            sane_form_13f_fn_for_file = form_13f_file_number_for_path.replace('/', '_')
            filename = f"{sane_form_13f_fn_for_file}_{accession_number}.txt"
        else:
            # Sanitize form_type for filename
            sane_form_type = form_type.replace('/', '_')
            filename = f"{cik}_{sane_form_type}_{accession_number}.txt"
            
        output_path = os.path.join(accession_specific_dir, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return output_path
    
    def get_sec_index_data(
        self,
        start_year: int = 1999,
        end_year: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Get SEC EDGAR index data for the specified year range.
        
        Args:
            start_year: Starting year for the index data
            end_year: Ending year for the index data (defaults to current year)
            
        Returns:
            pd.DataFrame: DataFrame containing the index data
        """
        try:
            if end_year is None:
                end_year = datetime.today().year
                
            all_reports = []
            for year in range(start_year, end_year + 1):
                for quarter in range(1, 5):
                    # Skip future quarters
                    current_year = datetime.today().year
                    current_quarter = (datetime.today().month - 1) // 3 + 1
                    if year > current_year or (year == current_year and quarter > current_quarter):
                        continue
                        
                    # Apply rate limiting before making the request
                    self._respect_rate_limit()
                    
                    df = self._parse_form_idx(year, quarter)
                    if not df.empty:
                        all_reports.append(df)
                        
            if not all_reports:
                self.logger.log_operation(
                    operation_type="INDEX_FETCH_NO_REPORTS_FOUND",
                    download_success=False,
                    download_error_message=f"No index data found for years {start_year}-{end_year}"
                )
                return pd.DataFrame(columns=[
                    "CIK", "Name", "Date Filed", "Form Type",
                    "accession_number", "Filename"
                ])
                
            df_all = pd.concat(all_reports).reset_index(drop=True)
            
            # Extract CIK and accession number from Filename
            df_all[['CIK_extracted', 'accession_number']] = df_all['Filename'].str.extract(
                r'edgar/data/(\d+)/([0-9\-]+)\.txt'
            )
            
            # Clean up accession number (remove .txt if present)
            df_all['accession_number'] = df_all['accession_number'].str.replace('.txt', '')
            
            # Zero-pad CIK to 10 digits
            df_all['CIK'] = df_all['CIK_extracted'].str.zfill(10)
            
            self.logger.log_operation(
                operation_type="INDEX_FETCH_SUCCESS",
                download_success=True,
                download_error_message=f"Retrieved index data with {len(df_all)} entries"
            )
            
            return df_all[['CIK', 'Name', 'Date Filed', 'Form Type', 'accession_number', 'Filename']]
        except Exception as e:
            self.logger.log_operation(
                operation_type="INDEX_FETCH_UNHANDLED_EXCEPTION",
                download_success=False,
                download_error_message=f"Error retrieving index data: {str(e)}"
            )
            return pd.DataFrame(columns=[
                "CIK", "Name", "Date Filed", "Form Type",
                "accession_number", "Filename"
            ])
    
    def _parse_form_idx(self, year: int, quarter: int) -> pd.DataFrame:
        """
        Parse a specific quarter's form index file.
        
        Args:
            year: Year to retrieve index for
            quarter: Quarter (1-4) to retrieve index for
            
        Returns:
            pd.DataFrame: DataFrame containing the parsed index data
        """
        try:
            url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/form.idx"
            
            # Apply rate limiting before making the request
            self._respect_rate_limit()
            
            response = self.session.get(url, headers=self.headers)
            
            if response.status_code != 200:
                self.logger.log_operation(
                    operation_type="INDEX_FETCH_PARTIAL_HTTP_ERROR",
                    download_success=False,
                    download_error_message=f"Failed to retrieve index for {year} Q{quarter}: HTTP {response.status_code}",
                    error_code=response.status_code
                )
                return pd.DataFrame()
                
            lines = response.text.splitlines()
            try:
                start_idx = next(i for i, line in enumerate(lines) if set(line.strip()) == {'-'})
            except StopIteration:
                self.logger.log_operation(
                    operation_type="INDEX_PARSE_UNEXPECTED_FORMAT_ERROR",
                    download_success=False,
                    download_error_message=f"Unexpected format in index file for {year} Q{quarter}"
                )
                return pd.DataFrame()
                
            entries = []
            for line in lines[start_idx + 1:]:
                try:
                    if len(line) < 98:  # Ensure minimum line length
                        continue
                        
                    entry = {
                        "Form Type": line[0:12].strip(),
                        "Name": line[12:74].strip(),
                        "CIK": line[74:86].strip(),
                        "Date Filed": line[86:98].strip(),
                        "Filename": line[98:].strip()
                    }
                    entries.append(entry)
                except Exception as e:
                    # Skip individual entries that can't be parsed
                    continue
                    
            if not entries:
                self.logger.log_operation(
                    operation_type="INDEX_PARSE_NO_VALID_ENTRIES_FOUND",
                    download_success=False,
                    download_error_message=f"No valid entries found in index for {year} Q{quarter}"
                )
                return pd.DataFrame()
                
            self.logger.log_operation(
                operation_type="INDEX_PARSE_SUCCESS",
                download_success=True,
                download_error_message=f"Successfully parsed {len(entries)} entries from {year} Q{quarter}"
            )
            return pd.DataFrame(entries)
        except Exception as e:
            self.logger.log_operation(
                operation_type="INDEX_PARSE_UNHANDLED_EXCEPTION",
                download_success=False,
                download_error_message=f"Error parsing index for {year} Q{quarter}: {str(e)}"
            )
            return pd.DataFrame()
    
    def _setup_session(self) -> requests.Session:
        """Set up a requests session with retry logic."""
        session = requests.Session()
        retry_strategy = Retry(
            total=MAX_RETRIES,
            connect=MAX_RETRIES,  # Retry on connection errors
            read=MAX_RETRIES,     # Retry on read errors (like IncompleteRead)
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=RETRY_STATUS_CODES,
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session 
