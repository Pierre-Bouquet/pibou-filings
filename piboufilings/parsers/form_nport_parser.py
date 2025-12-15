"""
Enhanced NPORT filing parser - normalized structure matching database schema.
Separates filing/fund info from individual holdings to eliminate data duplication.
"""

import pandas as pd
import re
from typing import Optional, Dict, Any, List
from pathlib import Path
from lxml import etree


class FormNPORTParser:
    """Enhanced NPORT parser with normalized structure matching database schema."""
    
    def __init__(self, output_dir: str = "./parsed_nport"):
        """Initialize parser with output directory."""
        self.output_dir = Path(output_dir)
    
    def parse_filing(self, content: str) -> Dict[str, pd.DataFrame]:
        """
        Parse a complete NPORT filing.
        
        Args:
            content: Raw filing content as string
        
        Returns:
            Dict containing 'filing_info' and 'holdings' DataFrames
        """
        result = {
            'filing_info': self._parse_filing_info(content),
            'holdings': pd.DataFrame()  # Default empty
        }
        
        # Determine if this is an exhibit filing (NPORT-EX) - skip these
        form_type = self._get_form_type(content)
        
        if 'EX' in form_type.upper():
            return result
        
        # Check PUBLIC DOCUMENT COUNT - only process holdings if count is 2
        doc_count = self._get_document_count(content)
        
        if doc_count >=1:
            # Handle regular NPORT filings with holdings - XML data
            xml_data = self._extract_xml_data(content)
            if xml_data:
                sec_file_number = None
                accession_number = None
                if not result['filing_info'].empty and 'SEC_FILE_NUMBER' in result['filing_info'].columns:
                    sec_file_number_val = result['filing_info']['SEC_FILE_NUMBER'].iloc[0]
                    if pd.notna(sec_file_number_val):
                        sec_file_number = str(sec_file_number_val)
                if not result['filing_info'].empty and 'ACCESSION_NUMBER' in result['filing_info'].columns:
                    accession_number_val = result['filing_info']['ACCESSION_NUMBER'].iloc[0]
                    if pd.notna(accession_number_val):
                        accession_number = str(accession_number_val)

                result['holdings'] = self._parse_holdings_from_xml(
                    xml_data,
                    result['filing_info'],
                    sec_file_number,
                    accession_number
                )
        
        return result
    
    def save_parsed_data(self, parsed_data: Dict[str, pd.DataFrame]):
        """Save parsed data to CSV files with proper CSV handling - matching 13F structure."""
        for data_type, df_original in parsed_data.items():
            
            if df_original.empty:
                continue

            df_to_save = df_original.copy()

            if data_type == "holdings":
                if not df_to_save.empty:
                    

                    expected_columns = [
                        'ACCESSION_NUMBER', 'CIK', 'PERIOD_OF_REPORT', 'FILED_DATE', 'SEC_FILE_NUMBER',
                        'SECURITY_NAME', 'TITLE', 'CUSIP', 'LEI',
                        'BALANCE', 'UNITS', 'CURRENCY', 'VALUE_USD', 
                        'PCT_VALUE', 'PAYOFF_PROFILE', 'ASSET_CATEGORY', 'ISSUER_CATEGORY', 
                        'COUNTRY', 'IS_RESTRICTED', 'FAIR_VALUE_LEVEL', 'IS_CASH_COLLATERAL', 
                        'IS_NON_CASH_COLLATERAL', 'IS_LOAN_BY_FUND', 'MATURITY_DATE', 
                        'COUPON_KIND', 'ANNUAL_RATE', 'IS_DEFAULT', 'NUM_PAYMENTS_ARREARS', 
                        'DERIVATIVE_CAT', 'COUNTERPARTY_NAME',
                        'ABS_CAT', 'ABS_SUB_CAT', 'CREATED_AT', 'UPDATED_AT'
                    ]                    
                                  
                    # Ensure all expected columns exist with proper defaults
                    for col in expected_columns:
                        if col not in df_to_save.columns:
                            df_to_save[col] = pd.NA
                    
                    # Reorder columns to match schema
                    df_to_save = df_to_save.reindex(columns=expected_columns)
                    
                    # Clean text fields to prevent CSV parsing issues
                    text_columns = df_to_save.select_dtypes(include=['object']).columns
                    for col in text_columns:
                        if col in df_to_save.columns:
                            df_to_save[col] = df_to_save[col].astype(str).str.replace(r'[\r\n\t]', ' ', regex=True)
                            df_to_save[col] = df_to_save[col].str.replace(r'"', '""', regex=True)
                    
                    filepath = self.output_dir / "nport_holdings.csv"
                    
                    self._dedupe_append(
                        filepath=filepath,
                        df=df_to_save,
                        key_cols=["ACCESSION_NUMBER", "SEC_FILE_NUMBER", "SECURITY_NAME", "TITLE", "BALANCE", "VALUE_USD"]
                    )
            
            elif data_type == "filing_info":
                if not df_to_save.empty:
                    

                    expected_columns = [
                        'ACCESSION_NUMBER', 'CIK', 'PERIOD_OF_REPORT', 'FILED_DATE', 'COMPANY_NAME', 'IRS_NUMBER',
                        'SEC_FILE_NUMBER', 'FILM_NUMBER', 'ACCEPTANCE_DATETIME', 'PUBLIC_DOCUMENT_COUNT',
                        'STATE_INC', 'FISCAL_YEAR_END', 'BUSINESS_STREET_1', 
                        'BUSINESS_STREET_2', 'BUSINESS_CITY', 'BUSINESS_STATE', 'BUSINESS_ZIP', 
                        'BUSINESS_PHONE', 'MAIL_STREET_1', 'MAIL_STREET_2', 'MAIL_CITY', 
                        'MAIL_STATE', 'MAIL_ZIP', 'FORMER_COMPANY_NAMES', 'REPORT_DATE', 
                        'FUND_REG_NAME', 'FUND_FILE_NUMBER', 'FUND_LEI', 'SERIES_NAME', 'SERIES_LEI',
                        'REPORT_PERIOD_END', 'REPORT_PERIOD_DATE', 'IS_FINAL_FILING',
                        'FUND_TOTAL_ASSETS', 'FUND_TOTAL_LIABS', 'FUND_NET_ASSETS',
                        'ASSETS_ATTR_MISC_SEC', 'ASSETS_INVESTED', 'AMT_PAY_ONE_YR_BANKS_BORR', 
                        'AMT_PAY_ONE_YR_CTRLD_COMP', 'AMT_PAY_ONE_YR_OTH_AFFIL', 'AMT_PAY_ONE_YR_OTHER',
                        'AMT_PAY_AFT_ONE_YR_BANKS_BORR', 'AMT_PAY_AFT_ONE_YR_CTRLD_COMP',
                        'AMT_PAY_AFT_ONE_YR_OTH_AFFIL', 'AMT_PAY_AFT_ONE_YR_OTHER',
                        'DELAY_DELIVERY', 'STANDBY_COMMIT', 'LIQUID_PREF', 'CASH_NOT_RPTD_IN_COR_D',
                        'IS_NON_CASH_COLLATERAL', 'MONTH_1_RETURN', 'MONTH_2_RETURN', 'MONTH_3_RETURN',
                        'MONTH_1_NET_REALIZED_GAIN', 'MONTH_2_NET_REALIZED_GAIN', 'MONTH_3_NET_REALIZED_GAIN',
                        'MONTH_1_NET_UNREALIZED_APPR', 'MONTH_2_NET_UNREALIZED_APPR', 'MONTH_3_NET_UNREALIZED_APPR',
                        'MONTH_1_REDEMPTION', 'MONTH_2_REDEMPTION', 'MONTH_3_REDEMPTION',
                        'MONTH_1_REINVESTMENT', 'MONTH_2_REINVESTMENT', 'MONTH_3_REINVESTMENT',
                        'MONTH_1_SALES', 'MONTH_2_SALES', 'MONTH_3_SALES',
                        'CREATED_AT', 'UPDATED_AT'
                    ]
                    
                    # Ensure all expected columns exist
                    for col in expected_columns:
                        if col not in df_to_save.columns:
                            df_to_save[col] = pd.NA
                        
                    # Reorder columns to match schema
                    df_to_save = df_to_save.reindex(columns=expected_columns)
                    
                    # Clean text fields
                    text_columns = df_to_save.select_dtypes(include=['object']).columns
                    for col in text_columns:
                        if col in df_to_save.columns:
                            df_to_save[col] = df_to_save[col].astype(str).str.replace(r'[\r\n\t]', ' ', regex=True)
                            df_to_save[col] = df_to_save[col].str.replace(r'"', '""', regex=True)
                    
                    filepath = self.output_dir / "nport_filing_info.csv"
                    
                    self._dedupe_append(
                        filepath=filepath,
                        df=df_to_save,
                        key_cols=["ACCESSION_NUMBER"] if "ACCESSION_NUMBER" in df_to_save.columns else ["CIK", "PERIOD_OF_REPORT", "SEC_FILE_NUMBER"]
                    )

    def _parse_filing_info(self, content: str) -> pd.DataFrame:
        """Extract comprehensive filing, company, fund, and performance information."""
        # Core filing and company patterns
        patterns = {
            # Core filing identification
            "ACCESSION_NUMBER": (r"ACCESSION NUMBER:\s+([\d\-]+)", pd.NA),
            "CIK": (r"CENTRAL INDEX KEY:\s+(\d+)", pd.NA),
            "FORM_TYPE": (r"CONFORMED SUBMISSION TYPE:\s+([\w\-]+)", pd.NA),
            "PERIOD_OF_REPORT": (r"CONFORMED PERIOD OF REPORT:\s+(\d+)", pd.NA),
            "FILED_DATE": (r"FILED AS OF DATE:\s+(\d+)", pd.NA),
            "SEC_FILE_NUMBER": (r"SEC FILE NUMBER:\s+([\d\-]+)", pd.NA),
            "FILM_NUMBER": (r"FILM NUMBER:\s+(\d+)", pd.NA),
            "ACCEPTANCE_DATETIME": (r"ACCEPTANCE-DATETIME>\s*(\d+)", pd.NA),
            "PUBLIC_DOCUMENT_COUNT": (r"PUBLIC DOCUMENT COUNT:\s+(\d+)", pd.NA),
            
            # Company information
            "COMPANY_NAME": (r"COMPANY CONFORMED NAME:\s*([^\r\n]+)", pd.NA),
            "IRS_NUMBER": (r"(?:IRS NUMBER|EIN):\s*([\d-]+)", pd.NA),
            "STATE_INC": (r"STATE OF INCORPORATION:\s*([A-Z]{2})", pd.NA),
            "FISCAL_YEAR_END": (r"FISCAL YEAR END:\s*(\d{4})", pd.NA),
            
            # Business Address
            "BUSINESS_STREET_1": (r"BUSINESS ADDRESS:.*?STREET 1:\s*([^\r\n]+)", pd.NA),
            "BUSINESS_STREET_2": (r"BUSINESS ADDRESS:.*?STREET 2:\s*([^\r\n]+)", pd.NA),
            "BUSINESS_CITY": (r"BUSINESS ADDRESS:.*?CITY:\s*([A-Za-z\s]+)", pd.NA),
            "BUSINESS_STATE": (r"BUSINESS ADDRESS:.*?STATE:\s*([A-Z]{2})", pd.NA),
            "BUSINESS_ZIP": (r"BUSINESS ADDRESS:.*?ZIP:\s*(\d{5})", pd.NA),
            "BUSINESS_PHONE": (r"BUSINESS PHONE:\s*([\d\-\(\)\s]+)", pd.NA),
            
            # Mail Address
            "MAIL_STREET_1": (r"MAIL ADDRESS:.*?STREET 1:\s*([^\r\n]+)", pd.NA),
            "MAIL_STREET_2": (r"MAIL ADDRESS:.*?STREET 2:\s*([^\r\n]+)", pd.NA),
            "MAIL_CITY": (r"MAIL ADDRESS:.*?CITY:\s*([A-Za-z\s]+)", pd.NA),
            "MAIL_STATE": (r"MAIL ADDRESS:.*?STATE:\s*([A-Z]{2})", pd.NA),
            "MAIL_ZIP": (r"MAIL ADDRESS:.*?ZIP:\s*(\d{5})", pd.NA)
        }
        
        # Extract basic info using regex patterns
        info = {}
        for field, (pattern, default) in patterns.items():
            try:
                match = re.search(pattern, content, re.DOTALL)
                info[field] = match.group(1).strip() if match else default
            except (AttributeError, IndexError):
                info[field] = default
        
        # Handle Former Company Names
        try:
            former_companies = []
            former_matches = re.findall(
                r"FORMER COMPANY:\s+FORMER CONFORMED NAME:\s+([^\r\n]+)\s+DATE OF NAME CHANGE:\s+(\d+)",
                content
            )
            for name, date in former_matches:
                former_companies.append(f"{name.strip()}({date})")
            info["FORMER_COMPANY_NAMES"] = "; ".join(former_companies) if former_companies else pd.NA
        except Exception:
            info["FORMER_COMPANY_NAMES"] = pd.NA

        # Extract fund and performance data from XML if available
        xml_data = self._extract_xml_data(content)
        if xml_data:
            fund_and_performance_info = self._extract_fund_and_performance_info(xml_data)
            info.update(fund_and_performance_info)

        try:
            # Define complete column order matching database schema
            desired_columns = [
                # Core filing info
                "ACCESSION_NUMBER", "CIK", "FORM_TYPE", "PERIOD_OF_REPORT", "FILED_DATE",
                "SEC_FILE_NUMBER", "FILM_NUMBER", "ACCEPTANCE_DATETIME", "PUBLIC_DOCUMENT_COUNT",
                
                # Company info
                "COMPANY_NAME", "IRS_NUMBER", "STATE_INC", "FISCAL_YEAR_END", 
                "BUSINESS_STREET_1", "BUSINESS_STREET_2", "BUSINESS_CITY", "BUSINESS_STATE", 
                "BUSINESS_ZIP", "BUSINESS_PHONE", "MAIL_STREET_1", "MAIL_STREET_2", 
                "MAIL_CITY", "MAIL_STATE", "MAIL_ZIP", "FORMER_COMPANY_NAMES",
                
                # Fund registration info
                "REPORT_DATE", "FUND_REG_NAME", "FUND_FILE_NUMBER", "FUND_LEI", "SERIES_NAME", "SERIES_LEI",
                
                # Financial metrics
                "FUND_TOTAL_ASSETS", "FUND_TOTAL_LIABS", "FUND_NET_ASSETS",
                "ASSETS_ATTR_MISC_SEC", "ASSETS_INVESTED",
                
                # Payable amounts (within one year)
                "AMT_PAY_ONE_YR_BANKS_BORR", "AMT_PAY_ONE_YR_CTRLD_COMP",
                "AMT_PAY_ONE_YR_OTH_AFFIL", "AMT_PAY_ONE_YR_OTHER",
                
                # Payable amounts (after one year)
                "AMT_PAY_AFT_ONE_YR_BANKS_BORR", "AMT_PAY_AFT_ONE_YR_CTRLD_COMP",
                "AMT_PAY_AFT_ONE_YR_OTH_AFFIL", "AMT_PAY_AFT_ONE_YR_OTHER",
                
                # Other financial metrics
                "DELAY_DELIVERY", "STANDBY_COMMIT", "LIQUID_PREF", "CASH_NOT_RPTD_IN_COR_D",
                "IS_NON_CASH_COLLATERAL",
                
                # Monthly returns
                "MONTH_1_RETURN", "MONTH_2_RETURN", "MONTH_3_RETURN",
                
                # Monthly gains
                "MONTH_1_NET_REALIZED_GAIN", "MONTH_2_NET_REALIZED_GAIN", "MONTH_3_NET_REALIZED_GAIN",
                "MONTH_1_NET_UNREALIZED_APPR", "MONTH_2_NET_UNREALIZED_APPR", "MONTH_3_NET_UNREALIZED_APPR",
                
                # Monthly flows
                "MONTH_1_REDEMPTION", "MONTH_2_REDEMPTION", "MONTH_3_REDEMPTION",
                "MONTH_1_REINVESTMENT", "MONTH_2_REINVESTMENT", "MONTH_3_REINVESTMENT",
                "MONTH_1_SALES", "MONTH_2_SALES", "MONTH_3_SALES",
                
                # Timestamps
                "CREATED_AT", "UPDATED_AT"
            ]
            
            # Add timestamp fields
            info["CREATED_AT"] = pd.Timestamp.now()
            info["UPDATED_AT"] = pd.Timestamp.now()
            
            # Create DataFrame
            filing_info_df = pd.DataFrame([info])
            filing_info_df = filing_info_df.reindex(columns=desired_columns)
            
            # Data type conversions
            self._convert_filing_info_data_types(filing_info_df)
            
            return filing_info_df
            
        except Exception as e:
            # Return empty DataFrame with proper columns
            empty_df = pd.DataFrame(columns=desired_columns)
            return empty_df

    def _extract_fund_and_performance_info(self, xml_data: str) -> dict:
        """Extract fund-level and performance data from XML."""
        fund_info = {}
        
        try:
            root = etree.fromstring(xml_data.encode('utf-8'))
            
            namespaces = {
                'nport': 'http://www.sec.gov/edgar/nport',
                'com': 'http://www.sec.gov/edgar/common',
                'ncom': 'http://www.sec.gov/edgar/nportcommon'
            }
            
            # General registration information
            gen_info = root.find('.//nport:genInfo', namespaces)
            if gen_info is not None:
                fund_info['FUND_REG_NAME'] = self._get_xml_text(gen_info, 'nport:regName', namespaces)
                fund_info['FUND_FILE_NUMBER'] = self._get_xml_text(gen_info, 'nport:regFileNumber', namespaces)
                fund_info['FUND_LEI'] = self._get_xml_text(gen_info, 'nport:regLei', namespaces)
                fund_info['SERIES_NAME'] = self._get_xml_text(gen_info, 'nport:seriesName', namespaces)
                fund_info['SERIES_LEI'] = self._get_xml_text(gen_info, 'nport:seriesLei', namespaces)
                fund_info['REPORT_PERIOD_END'] = self._get_xml_text(gen_info, 'nport:repPdEnd', namespaces)
                fund_info['REPORT_PERIOD_DATE'] = self._get_xml_text(gen_info, 'nport:repPdDate', namespaces)
                fund_info['IS_FINAL_FILING'] = self._get_xml_text(gen_info, 'nport:isFinalFiling', namespaces)
                fund_info['REPORT_DATE'] = fund_info['REPORT_PERIOD_END']  # Use for consistency
            
            # Fund financial information
            fund_info_elem = root.find('.//nport:fundInfo', namespaces)
            if fund_info_elem is not None:
                # Core financial metrics
                fund_info['FUND_TOTAL_ASSETS'] = self._get_xml_text(fund_info_elem, 'nport:totAssets', namespaces)
                fund_info['FUND_TOTAL_LIABS'] = self._get_xml_text(fund_info_elem, 'nport:totLiabs', namespaces)
                fund_info['FUND_NET_ASSETS'] = self._get_xml_text(fund_info_elem, 'nport:netAssets', namespaces)
                fund_info['ASSETS_ATTR_MISC_SEC'] = self._get_xml_text(fund_info_elem, 'nport:assetsAttrMiscSec', namespaces)
                fund_info['ASSETS_INVESTED'] = self._get_xml_text(fund_info_elem, 'nport:assetsInvested', namespaces)
                
                # Payable amounts - within one year
                fund_info['AMT_PAY_ONE_YR_BANKS_BORR'] = self._get_xml_text(fund_info_elem, 'nport:amtPayOneYrBanksBorr', namespaces)
                fund_info['AMT_PAY_ONE_YR_CTRLD_COMP'] = self._get_xml_text(fund_info_elem, 'nport:amtPayOneYrCtrldComp', namespaces)
                fund_info['AMT_PAY_ONE_YR_OTH_AFFIL'] = self._get_xml_text(fund_info_elem, 'nport:amtPayOneYrOthAffil', namespaces)
                fund_info['AMT_PAY_ONE_YR_OTHER'] = self._get_xml_text(fund_info_elem, 'nport:amtPayOneYrOther', namespaces)
                
                # Payable amounts - after one year
                fund_info['AMT_PAY_AFT_ONE_YR_BANKS_BORR'] = self._get_xml_text(fund_info_elem, 'nport:amtPayAftOneYrBanksBorr', namespaces)
                fund_info['AMT_PAY_AFT_ONE_YR_CTRLD_COMP'] = self._get_xml_text(fund_info_elem, 'nport:amtPayAftOneYrCtrldComp', namespaces)
                fund_info['AMT_PAY_AFT_ONE_YR_OTH_AFFIL'] = self._get_xml_text(fund_info_elem, 'nport:amtPayAftOneYrOthAffil', namespaces)
                fund_info['AMT_PAY_AFT_ONE_YR_OTHER'] = self._get_xml_text(fund_info_elem, 'nport:amtPayAftOneYrOther', namespaces)
                
                # Other financial metrics
                fund_info['DELAY_DELIVERY'] = self._get_xml_text(fund_info_elem, 'nport:delayDeliv', namespaces)
                fund_info['STANDBY_COMMIT'] = self._get_xml_text(fund_info_elem, 'nport:standByCommit', namespaces)
                fund_info['LIQUID_PREF'] = self._get_xml_text(fund_info_elem, 'nport:liquidPref', namespaces)
                fund_info['CASH_NOT_RPTD_IN_COR_D'] = self._get_xml_text(fund_info_elem, 'nport:cshNotRptdInCorD', namespaces)
                fund_info['IS_NON_CASH_COLLATERAL'] = self._get_xml_text(fund_info_elem, 'nport:isNonCashCollateral', namespaces)
                
                # Performance information
                return_info = fund_info_elem.find('.//nport:returnInfo', namespaces)
                if return_info is not None:
                    # Monthly returns
                    monthly_return = return_info.find('.//nport:monthlyTotReturn', namespaces)
                    if monthly_return is not None:
                        fund_info['MONTH_1_RETURN'] = monthly_return.get('rtn1')
                        fund_info['MONTH_2_RETURN'] = monthly_return.get('rtn2')
                        fund_info['MONTH_3_RETURN'] = monthly_return.get('rtn3')
                    
                    # Monthly performance breakdown
                    for i in range(1, 4):
                        oth_mon = return_info.find(f'.//nport:othMon{i}', namespaces)
                        if oth_mon is not None:
                            fund_info[f'MONTH_{i}_NET_REALIZED_GAIN'] = oth_mon.get('netRealizedGain')
                            fund_info[f'MONTH_{i}_NET_UNREALIZED_APPR'] = oth_mon.get('netUnrealizedAppr')
                
                # Monthly flow information
                for i in range(1, 4):
                    mon_flow = fund_info_elem.find(f'.//nport:mon{i}Flow', namespaces)
                    if mon_flow is not None:
                        fund_info[f'MONTH_{i}_REDEMPTION'] = mon_flow.get('redemption')
                        fund_info[f'MONTH_{i}_REINVESTMENT'] = mon_flow.get('reinvestment')
                        fund_info[f'MONTH_{i}_SALES'] = mon_flow.get('sales')
                        
        except Exception as e:
            print(f"Warning: Error extracting fund/performance info: {e}")
        
        return fund_info

    def _parse_holdings_from_xml(
        self,
        xml_data: str,
        filing_info_df: pd.DataFrame,
        sec_file_number: Optional[str],
        accession_number: Optional[str]
    ) -> pd.DataFrame:
        """Parse individual security holdings (security-specific data only)."""
        try:
            root = etree.fromstring(xml_data.encode('utf-8'))
            
            namespaces = {
                'nport': 'http://www.sec.gov/edgar/nport',
                'com': 'http://www.sec.gov/edgar/common',
                'ncom': 'http://www.sec.gov/edgar/nportcommon'
            }
            
            holdings = []
            # Retrieve FILED_DATE and use REPORT_DATE as PERIOD_OF_REPORT for holdings
            filed_date_val = filing_info_df['FILED_DATE'].iloc[0] if not filing_info_df.empty and 'FILED_DATE' in filing_info_df.columns else None
            period_of_report_val = filing_info_df['REPORT_DATE'].iloc[0] if not filing_info_df.empty and 'REPORT_DATE' in filing_info_df.columns else None
            cik_val = filing_info_df['CIK'].iloc[0] if not filing_info_df.empty and 'CIK' in filing_info_df.columns else None
            
            # Parse each investment/security - ONLY security-specific data
            for inv in root.findall('.//nport:invstOrSec', namespaces):
                holding = {
                    # Link to filing info - matching exact schema
                    'HOLDING_ID': None,  # Will be auto-generated in database
                    'ACCESSION_NUMBER': accession_number,
                    'CIK': cik_val,
                    'PERIOD_OF_REPORT': period_of_report_val, # Changed from REPORT_DATE
                    'FILED_DATE': filed_date_val, # Added
                    'SEC_FILE_NUMBER': sec_file_number,
                    
                    # Core security information
                    'SECURITY_NAME': self._get_xml_text(inv, 'nport:name', namespaces),
                    'TITLE': self._get_xml_text(inv, 'nport:title', namespaces),
                    'CUSIP': self._get_xml_text(inv, 'nport:cusip', namespaces),
                    'LEI': self._get_xml_text(inv, 'nport:lei', namespaces),
                    'BALANCE': self._get_xml_text(inv, 'nport:balance', namespaces),
                    'UNITS': self._get_xml_text(inv, 'nport:units', namespaces),
                    'CURRENCY': self._get_xml_text(inv, 'nport:curCd', namespaces),
                    'VALUE_USD': self._get_xml_text(inv, 'nport:valUSD', namespaces),
                    'PCT_VALUE': self._get_xml_text(inv, 'nport:pctVal', namespaces),
                    
                    # Classification
                    'PAYOFF_PROFILE': self._get_xml_text(inv, 'nport:payoffProfile', namespaces),
                    'ASSET_CATEGORY': self._get_xml_text(inv, 'nport:assetCat', namespaces),
                    'ISSUER_CATEGORY': self._get_xml_text(inv, 'nport:issuerCat', namespaces),
                    'COUNTRY': self._get_xml_text(inv, 'nport:invCountry', namespaces),
                    'IS_RESTRICTED': self._get_xml_text(inv, 'nport:isRestrictedSec', namespaces),
                    'FAIR_VALUE_LEVEL': self._get_xml_text(inv, 'nport:fairValLevel', namespaces),
                    
                    # Security lending - initialize with defaults
                    'IS_CASH_COLLATERAL': None,
                    'IS_NON_CASH_COLLATERAL': None,
                    'IS_LOAN_BY_FUND': None,
                    
                    # Debt security - initialize with defaults
                    'MATURITY_DATE': None,
                    'COUPON_KIND': None,
                    'ANNUAL_RATE': None,
                    'IS_DEFAULT': None,
                    'NUM_PAYMENTS_ARREARS': None,
                    
                    # Derivative - initialize with defaults
                    'DERIVATIVE_CAT': None,
                    'COUNTERPARTY_NAME': None,
                    
                    # Asset-backed securities - initialize with defaults
                    'ABS_CAT': None,
                    'ABS_SUB_CAT': None,
                    
                    # Timestamps
                    'CREATED_AT': pd.Timestamp.now(),
                    'UPDATED_AT': pd.Timestamp.now()
                }
                
                # Security lending information
                sec_lending = inv.find('nport:securityLending', namespaces)
                if sec_lending is not None:
                    holding['IS_CASH_COLLATERAL'] = self._get_xml_text(sec_lending, 'nport:isCashCollateral', namespaces)
                    holding['IS_NON_CASH_COLLATERAL'] = self._get_xml_text(sec_lending, 'nport:isNonCashCollateral', namespaces)
                    holding['IS_LOAN_BY_FUND'] = self._get_xml_text(sec_lending, 'nport:isLoanByFund', namespaces)
                
                # Debt security information
                debt_sec = inv.find('nport:debtSec', namespaces)
                if debt_sec is not None:
                    holding['MATURITY_DATE'] = debt_sec.get('maturityDt')
                    holding['COUPON_KIND'] = debt_sec.get('couponKind')
                    holding['ANNUAL_RATE'] = debt_sec.get('annualizedRt')
                    holding['IS_DEFAULT'] = debt_sec.get('isDefault')
                    holding['NUM_PAYMENTS_ARREARS'] = debt_sec.get('numPaymentsInArrears')
                
                # Derivative information
                derivative_info = inv.find('nport:derivativeInfo', namespaces)
                if derivative_info is not None:
                    holding['DERIVATIVE_CAT'] = self._get_xml_text(derivative_info, 'nport:derivCat', namespaces)
                    holding['COUNTERPARTY_NAME'] = self._get_xml_text(derivative_info, 'nport:counterpartyName', namespaces)
                
                # Asset-backed securities
                abs_info = inv.find('nport:assetBackedSec', namespaces)
                if abs_info is not None:
                    holding['ABS_CAT'] = self._get_xml_text(abs_info, 'nport:absCat', namespaces)
                    holding['ABS_SUB_CAT'] = self._get_xml_text(abs_info, 'nport:absSubCat', namespaces)
                
                # Extract CUSIP and ISIN with conditional logic
                # holding['OTHER_ID'] = None # Removed OTHER_ID initialization

                # Try to get CUSIP first if not already populated (it should be by the direct parse above)
                if holding['CUSIP'] is None:
                    cusip_elem = inv.find('.//nport:cusip', namespaces)
                    if cusip_elem is not None and cusip_elem.text:
                        holding['CUSIP'] = cusip_elem.text.strip()
                
                # Fallback: Try to find 'idenOther' if 'cusip' is not found or is empty
                if not holding['CUSIP']:
                    other_id_elem = inv.find('.//nport:idenOther', namespaces)
                    if other_id_elem is not None:
                        # Check if this otherId is a CUSIP (though ideally it was caught by direct nport:cusip)
                        id_type = other_id_elem.get('type')
                        if id_type and 'CUSIP' in id_type.upper():
                            holding['CUSIP'] = other_id_elem.get('value')
                        # else: # Removed assignment to holding['OTHER_ID']
                        #      holding['OTHER_ID'] = other_id_elem.get('value')
                else:
                    # If CUSIP was found directly, no action needed for OTHER_ID
                    pass

                # Fallback for general LEI if not directly parsed and not found as CUSIP in idenOther
                if not holding['LEI']:
                    other_id_elem_for_lei = inv.find('.//nport:idenOther', namespaces) # Re-find or use existing if safe
                    if other_id_elem_for_lei is not None:
                        id_type = other_id_elem_for_lei.get('type')
                        if id_type and 'LEI' in id_type.upper():
                            holding['LEI'] = other_id_elem_for_lei.get('value')
                        # If LEI was found in idenOther, no need to clear OTHER_ID as it's removed

                # Additional handling for investment categories
                inv_data = self._get_xml_text(inv, 'nport:invCategory', namespaces)
                holding['INVESTMENT_CATEGORY'] = inv_data if inv_data else "N/A"
                
                holdings.append(holding)
            
            # Fallback parsing without namespaces if no holdings found
            if not holdings:
                for inv in root.findall('.//invstOrSec'):
                    holding = {
                        'HOLDING_ID': None,
                        'ACCESSION_NUMBER': accession_number,
                        'CIK': cik_val,
                        'PERIOD_OF_REPORT': period_of_report_val,
                        'FILED_DATE': filed_date_val,
                        'SEC_FILE_NUMBER': sec_file_number,
                        'SECURITY_NAME': self._get_xml_text_simple(inv, 'name'),
                        'TITLE': None,
                        'CUSIP': self._get_xml_text_simple(inv, 'cusip'),
                        'LEI': self._get_xml_text_simple(inv, 'lei'), # Added general LEI for holding
                        # 'OTHER_ID': None, # Removed OTHER_ID
                        'BALANCE': self._get_xml_text_simple(inv, 'balance'),
                        'UNITS': None,
                        'CURRENCY': None,
                        'VALUE_USD': self._get_xml_text_simple(inv, 'valUSD'),
                        'PCT_VALUE': None,
                        'PAYOFF_PROFILE': None,
                        'ASSET_CATEGORY': self._get_xml_text_simple(inv, 'assetCat'),
                        'ISSUER_CATEGORY': None,
                        'COUNTRY': None,
                        'IS_RESTRICTED': None,
                        'FAIR_VALUE_LEVEL': None,
                        'IS_CASH_COLLATERAL': None,
                        'IS_NON_CASH_COLLATERAL': None,
                        'IS_LOAN_BY_FUND': None,
                        'MATURITY_DATE': None,
                        'COUPON_KIND': None,
                        'ANNUAL_RATE': None,
                        'IS_DEFAULT': None,
                        'NUM_PAYMENTS_ARREARS': None,
                        'DERIVATIVE_CAT': None,
                        'COUNTERPARTY_NAME': None,
                        'ABS_CAT': None,
                        'ABS_SUB_CAT': None,
                        'CREATED_AT': pd.Timestamp.now(),
                        'UPDATED_AT': pd.Timestamp.now()
                    }
                    holdings.append(holding)
            
            if not holdings:
                return pd.DataFrame()
            
            df = pd.DataFrame(holdings)
            
            # Data type conversions
            self._convert_holdings_data_types(df)
            
            return df
            
        except Exception as e:
            return pd.DataFrame()

    def _convert_filing_info_data_types(self, df: pd.DataFrame):
        """Convert data types for filing info DataFrame."""
        # Date columns
        date_columns = ['PERIOD_OF_REPORT', 'FILED_DATE', 'REPORT_PERIOD_END', 'REPORT_PERIOD_DATE']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], format='%Y%m%d', errors='coerce')
        
        # Datetime columns
        if 'ACCEPTANCE_DATETIME' in df.columns:
            df['ACCEPTANCE_DATETIME'] = pd.to_datetime(
                df['ACCEPTANCE_DATETIME'], format='%Y%m%d%H%M%S', errors='coerce')
        
        # Numeric columns
        numeric_cols = [
            'CIK', 'FILM_NUMBER', 'FISCAL_YEAR_END', 'PUBLIC_DOCUMENT_COUNT',
            'FUND_TOTAL_ASSETS', 'FUND_TOTAL_LIABS', 'FUND_NET_ASSETS',
            'ASSETS_ATTR_MISC_SEC', 'ASSETS_INVESTED', 'DELAY_DELIVERY', 
            'STANDBY_COMMIT', 'LIQUID_PREF', 'CASH_NOT_RPTD_IN_COR_D'
        ] + [f'MONTH_{i}_NET_REALIZED_GAIN' for i in range(1, 4)] + \
          [f'MONTH_{i}_NET_UNREALIZED_APPR' for i in range(1, 4)] + \
          [f'MONTH_{i}_RETURN' for i in range(1, 4)] + \
          [f'MONTH_{i}_REDEMPTION' for i in range(1, 4)] + \
          [f'MONTH_{i}_REINVESTMENT' for i in range(1, 4)] + \
          [f'MONTH_{i}_SALES' for i in range(1, 4)]
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Boolean columns
        boolean_cols = ['IS_FINAL_FILING', 'IS_NON_CASH_COLLATERAL']
        for col in boolean_cols:
            if col in df.columns:
                df[col] = df[col].map({
                    'Y': True, 'N': False, 'true': True, 'false': False,
                    'YES': True, 'NO': False, '1': True, '0': False
                })

    def _convert_holdings_data_types(self, df: pd.DataFrame):
        """Convert holdings data types for consistency."""
        if df.empty:
            return

        numeric_cols = [
            'BALANCE', 'VALUE_USD', 'PCT_VALUE', 'ANNUAL_RATE', 'NUM_PAYMENTS_ARREARS'
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Convert date columns to datetime, handling potential errors by setting to NaT
        date_cols = ['PERIOD_OF_REPORT', 'FILED_DATE', 'MATURITY_DATE'] # Added PERIOD_OF_REPORT, FILED_DATE, removed REPORT_DATE
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        # Convert specific columns to string to ensure consistency
        text_columns = df.select_dtypes(include=['object']).columns
        for col in text_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(r'[\r\n\t]', ' ', regex=True)
                df[col] = df[col].str.replace(r'"', '""', regex=True)

        # Boolean columns
        boolean_cols = [
            'IS_RESTRICTED', 'IS_CASH_COLLATERAL', 'IS_NON_CASH_COLLATERAL', 
            'IS_LOAN_BY_FUND', 'IS_DEFAULT'
        ]
        for col in boolean_cols:
            if col in df.columns:
                df[col] = df[col].map({
                    'Y': True, 'N': False, 'true': True, 'false': False,
                    'YES': True, 'NO': False, '1': True, '0': False
                })

    def _dedupe_append(self, filepath: Path, df: pd.DataFrame, key_cols: List[str]) -> None:
        """Write data to CSV with deduplication and CUSIP preference."""
        filepath.parent.mkdir(parents=True, exist_ok=True)

        columns = list(df.columns)
        records: Dict[Any, Dict[str, Any]] = {}

        def norm_key(row_dict: Dict[str, Any]) -> Any:
            return tuple(None if pd.isna(row_dict.get(k, pd.NA)) else row_dict.get(k, pd.NA) for k in key_cols)

        def prefer(new: Dict[str, Any], current: Dict[str, Any]) -> bool:
            cur_cusip = current.get("CUSIP", pd.NA)
            new_cusip = new.get("CUSIP", pd.NA)
            return (pd.isna(cur_cusip) or cur_cusip in ("", None)) and (not pd.isna(new_cusip) and new_cusip not in ("", None))

        def add_row(row_dict: Dict[str, Any]) -> None:
            key = norm_key(row_dict)
            existing = records.get(key)
            if existing is None or prefer(row_dict, existing):
                records[key] = row_dict

        if filepath.exists():
            for chunk in pd.read_csv(filepath, chunksize=50000):
                for _, row in chunk.iterrows():
                    add_row(row.to_dict())

        for _, row in df.iterrows():
            add_row(row.to_dict())

        if not records:
            return

        pd.DataFrame(records.values()).reindex(columns=columns).to_csv(filepath, index=False)

    def _get_form_type(self, content: str) -> str:
        """Extract form type from content."""
        match = re.search(r"CONFORMED SUBMISSION TYPE:\s+([\w\-]+)", content)
        return match.group(1) if match else ""
    
    def _get_document_count(self, content: str) -> int:
        """Extract public document count from content."""
        match = re.search(r"PUBLIC DOCUMENT COUNT:\s+(\d+)", content)
        return int(match.group(1)) if match else 0
    
    def _extract_xml_data(self, content: str) -> Optional[str]:
        """Extract XML data from NPORT filing."""
        try:
            # Method 1: Find XML blocks between <XML> tags
            xml_blocks = re.findall(r'<XML>(.*?)</XML>', content, re.DOTALL)
            
            if xml_blocks:
                # Usually the largest XML block contains the holdings data
                xml_content = max(xml_blocks, key=len)
                # Clean XML - remove XML declarations
                xml_content = re.sub(r'<\?xml[^>]+\?>', '', xml_content).strip()
                return xml_content if xml_content else None
            
            # Method 2: Look for nport-specific XML structures
            nport_match = re.search(
                r'<edgarSubmission[^>]*>.*?</edgarSubmission>', 
                content, 
                re.DOTALL | re.IGNORECASE
            )
            if nport_match:
                return nport_match.group(0)
            
            return None
            
        except Exception:
            return None
    
    def _get_xml_text(self, element, path: str, namespaces: dict) -> Optional[str]:
        """Safely extract text from XML element with namespace support."""
        try:
            found = element.find(path, namespaces)
            if found is not None and found.text:
                return found.text.strip()
            return None
        except Exception:
            return None
    
    def _get_xml_text_simple(self, element, path: str) -> Optional[str]:
        """Safely extract text from XML element without namespace."""
        try:
            found = element.find(path)
            return found.text.strip() if found is not None and found.text else None
        except Exception:
            return None

    def get_cik_from_content(self, content: str) -> Optional[str]:
        """Extract CIK from filing content."""
        try:
            match = re.search(r"CENTRAL INDEX KEY:\s+(\d+)", content)
            return match.group(1) if match else None
        except Exception:
            return None


# Usage example
def process_nport_filing(file_path: str, parser: FormNPORTParser):
    """Process a single NPORT filing file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Parse the filing
        parsed_data = parser.parse_filing(content)
        
        # Save the parsed data
        # CIK and Accession Number are no longer extracted or used by the parser's save method.
        parser.save_parsed_data(parsed_data)
            
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")


# Batch processing example
def process_nport_directory(directory_path: str, output_dir: str = "./parsed_nport"):
    """Process all NPORT files in a directory."""
    parser = FormNPORTParser(output_dir)
    directory = Path(directory_path)
    
    nport_files = list(directory.glob("*.txt")) + list(directory.glob("*.sgml"))
    
    for file_path in nport_files:
        print(f"Processing: {file_path.name}")
        process_nport_filing(str(file_path), parser)
    
