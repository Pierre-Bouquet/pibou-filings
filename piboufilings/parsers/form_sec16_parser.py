"""
Parser for Section 16 insider filings (Forms 3, 4, and 5).
Extracts filing-level metadata, transactions, and holdings from ownershipDocument XML.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

import pandas as pd


class FormSection16Parser:
    """Parse Section 16 Forms 3/4/5 filings into normalized CSV-friendly DataFrames."""

    def __init__(self, output_dir: str = "./parsed_sec16"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def parse_filing(self, content: str) -> Dict[str, pd.DataFrame]:
        """Parse a single Section 16 filing."""
        root = self._get_xml_root(content)
        footnotes = self._parse_footnotes(root) if root is not None else {}
        filing_info = self._parse_filing_info(content, root)
        issuer_info = self._get_issuer(root)
        owner_info = self._get_primary_reporting_owner(root)

        transactions = self._parse_transactions(root, filing_info, issuer_info, owner_info, footnotes)
        holdings = self._parse_holdings(root, filing_info, issuer_info, owner_info, footnotes)
        return {
            "filing_info": filing_info,
            "transactions": transactions,
            "holdings": holdings
        }

    def save_parsed_data(self, parsed_data: Dict[str, pd.DataFrame]):
        """Persist parsed DataFrames to CSV with deduplication."""
        output_map = {
            "filing_info": ("sec16_info.csv", self._expected_info_columns()),
            "transactions": ("sec16_transactions.csv", self._expected_transaction_columns()),
            "holdings": ("sec16_holdings.csv", self._expected_holdings_columns())
        }

        for data_type, df in parsed_data.items():
            if df is None or df.empty:
                continue

            if data_type not in output_map:
                continue

            filename, expected_cols = output_map[data_type]
            df_to_save = df.copy()

            for col in expected_cols:
                if col not in df_to_save.columns:
                    df_to_save[col] = pd.NA

            df_to_save = df_to_save.reindex(columns=expected_cols)
            self._write_dataframe(self.output_dir / filename, df_to_save)

    def _expected_info_columns(self) -> List[str]:
        return [
            "ACCESSION_NUMBER",
            "DOCUMENT_TYPE",
            "PERIOD_OF_REPORT",
            "DATE_FILED",
            "ACCEPTANCE_DATETIME",
            "SCHEMA_VERSION",
            "ISSUER_CIK",
            "ISSUER_NAME",
            "ISSUER_TRADING_SYMBOL",
            "RPT_OWNER_CIK",
            "RPT_OWNER_NAME",
            "RPT_OWNER_STREET1",
            "RPT_OWNER_STREET2",
            "RPT_OWNER_CITY",
            "RPT_OWNER_STATE",
            "RPT_OWNER_ZIP",
            "IS_DIRECTOR",
            "IS_OFFICER",
            "OFFICER_TITLE",
            "IS_TEN_PCT_OWNER",
            "IS_OTHER",
            "OTHER_TEXT",
            "REMARKS",
            "SEC_FILING_URL",
            "CREATED_AT",
            "UPDATED_AT"
        ]

    def _expected_transaction_columns(self) -> List[str]:
        return [
            "ACCESSION_NUMBER",
            "DOCUMENT_TYPE",
            "PERIOD_OF_REPORT",
            "ISSUER_CIK",
            "ISSUER_NAME",
            "ISSUER_TRADING_SYMBOL",
            "RPT_OWNER_CIK",
            "RPT_OWNER_NAME",
            "TABLE_TYPE",
            "SECURITY_TITLE",
            "TRANSACTION_FORM_TYPE",
            "TRANSACTION_CODE",
            "EQUITY_SWAP_INVOLVED",
            "TRANSACTION_DATE",
            "DEEMED_EXECUTION_DATE",
            "TRANSACTION_SHARES",
            "TRANSACTION_PRICE_PER_SHARE",
            "SHARES_OWNED_FOLLOWING_TRANSACTION",
            "DIRECT_OR_INDIRECT_OWNERSHIP",
            "NATURE_OF_OWNERSHIP",
            "CONVERSION_OR_EXERCISE_PRICE",
            "EXERCISE_DATE",
            "EXPIRATION_DATE",
            "UNDERLYING_SECURITY_TITLE",
            "UNDERLYING_SECURITY_SHARES",
            "FOOTNOTE_IDS",
            "CREATED_AT",
            "UPDATED_AT"
        ]

    def _expected_holdings_columns(self) -> List[str]:
        return [
            "ACCESSION_NUMBER",
            "DOCUMENT_TYPE",
            "PERIOD_OF_REPORT",
            "ISSUER_CIK",
            "ISSUER_NAME",
            "ISSUER_TRADING_SYMBOL",
            "RPT_OWNER_CIK",
            "RPT_OWNER_NAME",
            "TABLE_TYPE",
            "SECURITY_TITLE",
            "SHARES_OWNED",
            "DIRECT_OR_INDIRECT_OWNERSHIP",
            "NATURE_OF_OWNERSHIP",
            "CONVERSION_OR_EXERCISE_PRICE",
            "EXERCISE_DATE",
            "EXPIRATION_DATE",
            "UNDERLYING_SECURITY_TITLE",
            "UNDERLYING_SECURITY_SHARES",
            "FOOTNOTE_IDS",
            "CREATED_AT",
            "UPDATED_AT"
        ]

    def _write_dataframe(self, file_path: Path, df_to_save: pd.DataFrame) -> None:
        """Append rows to CSV with deduplication (no concat FutureWarning)."""
        if df_to_save is None:
            return

        expected_cols = list(df_to_save.columns)

        def _nonempty(df: pd.DataFrame) -> pd.DataFrame:
            df = df.dropna(how="all")
            return df if not df.empty else pd.DataFrame(columns=expected_cols)

        def _drop_all_na_cols(df: pd.DataFrame) -> pd.DataFrame:
            # Avoid pandas FutureWarning: concat with all-NA columns
            all_na_cols = [c for c in df.columns if df[c].isna().all()]
            return df.drop(columns=all_na_cols) if all_na_cols else df

        frames: list[pd.DataFrame] = []

        if file_path.exists():
            existing = pd.read_csv(file_path)
            existing = existing.reindex(columns=expected_cols)
            existing = _nonempty(existing)
            if not existing.empty:
                frames.append(_drop_all_na_cols(existing))

        incoming = df_to_save.reindex(columns=expected_cols)
        incoming = _nonempty(incoming)
        if not incoming.empty:
            frames.append(_drop_all_na_cols(incoming))

        if not frames:
            return

        combined_df = pd.concat(frames, ignore_index=True)
        combined_df = combined_df.reindex(columns=expected_cols)  # restore full schema
        combined_df = combined_df.drop_duplicates()
        combined_df.to_csv(file_path, index=False)


    def _get_xml_root(self, content: str) -> Optional[ET.Element]:
        """Extract and parse the ownershipDocument XML section."""
        try:
            match = re.search(
                r"<ownershipDocument[^>]*>.*?</ownershipDocument>",
                content,
                re.DOTALL | re.IGNORECASE
            )
            if not match:
                return None
            return ET.fromstring(match.group(0))
        except ET.ParseError:
            return None

    def _parse_footnotes(self, root: Optional[ET.Element]) -> Dict[str, str]:
        if root is None:
            return {}
        notes = {}
        for fn in root.findall(".//footnote"):
            fn_id = fn.attrib.get("id")
            text = fn.text.strip() if fn.text else ""
            if fn_id:
                notes[fn_id] = text
        return notes

    def _parse_filing_info(self, content: str, root: Optional[ET.Element]) -> pd.DataFrame:
        """Build filing-level and reporting-owner-level metadata."""
        timestamp = pd.Timestamp.now()
        info: Dict[str, Any] = {
            "ACCESSION_NUMBER": self._extract_regex(content, r"ACCESSION NUMBER:\s*([\d\-]+)"),
            "DOCUMENT_TYPE": self._find_text(root, ".//documentType"),
            "PERIOD_OF_REPORT": self._find_text(root, ".//periodOfReport"),
            "DATE_FILED": self._extract_regex(content, r"FILED AS OF DATE:\s*(\d+)"),
            "ACCEPTANCE_DATETIME": self._extract_regex(content, r"ACCEPTANCE-DATETIME>\s*(\d+)"),
            "SCHEMA_VERSION": self._find_text(root, ".//schemaVersion"),
            "ISSUER_CIK": None,
            "ISSUER_NAME": None,
            "ISSUER_TRADING_SYMBOL": None,
            "RPT_OWNER_CIK": None,
            "RPT_OWNER_NAME": None,
            "RPT_OWNER_STREET1": None,
            "RPT_OWNER_STREET2": None,
            "RPT_OWNER_CITY": None,
            "RPT_OWNER_STATE": None,
            "RPT_OWNER_ZIP": None,
            "IS_DIRECTOR": None,
            "IS_OFFICER": None,
            "OFFICER_TITLE": None,
            "IS_TEN_PCT_OWNER": None,
            "IS_OTHER": None,
            "OTHER_TEXT": None,
            "REMARKS": self._find_text(root, ".//remarks"),
            "SEC_FILING_URL": pd.NA,
            "CREATED_AT": timestamp,
            "UPDATED_AT": timestamp
        }

        issuer = self._get_issuer(root)
        owner = self._get_primary_reporting_owner(root)

        if issuer:
            info.update({
                "ISSUER_CIK": issuer.get("cik"),
                "ISSUER_NAME": issuer.get("name"),
                "ISSUER_TRADING_SYMBOL": issuer.get("trading_symbol")
            })

        if owner:
            info.update({
                "RPT_OWNER_CIK": owner.get("cik"),
                "RPT_OWNER_NAME": owner.get("name"),
                "RPT_OWNER_STREET1": owner.get("street1"),
                "RPT_OWNER_STREET2": owner.get("street2"),
                "RPT_OWNER_CITY": owner.get("city"),
                "RPT_OWNER_STATE": owner.get("state"),
                "RPT_OWNER_ZIP": owner.get("zip"),
                "IS_DIRECTOR": owner.get("is_director"),
                "IS_OFFICER": owner.get("is_officer"),
                "OFFICER_TITLE": owner.get("officer_title"),
                "IS_TEN_PCT_OWNER": owner.get("is_ten_pct"),
                "IS_OTHER": owner.get("is_other"),
                "OTHER_TEXT": owner.get("other_text")
            })

        df = pd.DataFrame([info])
        df["DATE_FILED"] = pd.to_datetime(df["DATE_FILED"], format="%Y%m%d", errors="coerce")
        df["PERIOD_OF_REPORT"] = pd.to_datetime(df["PERIOD_OF_REPORT"], errors="coerce")
        if "ACCEPTANCE_DATETIME" in df.columns:
            df["ACCEPTANCE_DATETIME"] = pd.to_datetime(
                df["ACCEPTANCE_DATETIME"], format="%Y%m%d%H%M%S", errors="coerce"
            )
        bool_map = {"1": True, "0": False, "true": True, "false": False, True: True, False: False}
        for flag in ["IS_DIRECTOR", "IS_OFFICER", "IS_TEN_PCT_OWNER", "IS_OTHER"]:
            df[flag] = df[flag].map(bool_map).astype("boolean")
        return df

    def _parse_transactions(
        self,
        root: Optional[ET.Element],
        filing_info: pd.DataFrame,
        issuer: Dict[str, Any],
        owner: Dict[str, Any],
        footnotes: Dict[str, str]
    ) -> pd.DataFrame:
        if root is None:
            return pd.DataFrame(columns=self._expected_transaction_columns())

        base = self._transaction_base_row(filing_info, issuer, owner)
        timestamp = pd.Timestamp.now()
        rows: List[Dict[str, Any]] = []

        # Non-derivative transactions
        for node in root.findall(".//nonDerivativeTransaction"):
            row = base.copy()
            row["TABLE_TYPE"] = "NON_DERIVATIVE"
            row["SECURITY_TITLE"], f1 = self._text_with_fns(node, "securityTitle/value")
            row["TRANSACTION_FORM_TYPE"], f2 = self._text_with_fns(node, "transactionCoding/transactionFormType")
            row["TRANSACTION_CODE"], f3 = self._text_with_fns(node, "transactionCoding/transactionCode")
            row["EQUITY_SWAP_INVOLVED"], f4 = self._text_with_fns(node, "transactionCoding/equitySwapInvolved")
            row["TRANSACTION_DATE"], f5 = self._text_with_fns(node, "transactionDate/value")
            row["DEEMED_EXECUTION_DATE"], f6 = self._text_with_fns(node, "deemedExecutionDate/value")
            row["TRANSACTION_SHARES"], f7 = self._text_with_fns(node, "transactionAmounts/transactionShares/value")
            row["TRANSACTION_PRICE_PER_SHARE"], f8 = self._text_with_fns(node, "transactionAmounts/transactionPricePerShare/value")
            row["SHARES_OWNED_FOLLOWING_TRANSACTION"], f9 = self._text_with_fns(node, "postTransactionAmounts/sharesOwnedFollowingTransaction/value")
            row["DIRECT_OR_INDIRECT_OWNERSHIP"], f10 = self._text_with_fns(node, "ownershipNature/directOrIndirectOwnership/value")
            row["NATURE_OF_OWNERSHIP"], f11 = self._text_with_fns(node, "ownershipNature/natureOfOwnership/value")
            row["FOOTNOTE_IDS"] = self._combine_footnotes([f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11, self._footnotes_from_node(node)], footnotes)
            row["CREATED_AT"] = timestamp
            row["UPDATED_AT"] = timestamp
            rows.append(row)

        # Derivative transactions
        for node in root.findall(".//derivativeTransaction"):
            row = base.copy()
            row["TABLE_TYPE"] = "DERIVATIVE"
            row["SECURITY_TITLE"], f1 = self._text_with_fns(node, "securityTitle/value")
            row["TRANSACTION_FORM_TYPE"], f2 = self._text_with_fns(node, "transactionCoding/transactionFormType")
            row["TRANSACTION_CODE"], f3 = self._text_with_fns(node, "transactionCoding/transactionCode")
            row["EQUITY_SWAP_INVOLVED"], f4 = self._text_with_fns(node, "transactionCoding/equitySwapInvolved")
            row["TRANSACTION_DATE"], f5 = self._text_with_fns(node, "transactionDate/value")
            row["DEEMED_EXECUTION_DATE"], f6 = self._text_with_fns(node, "deemedExecutionDate/value")
            row["TRANSACTION_SHARES"], f7 = self._text_with_fns(node, "transactionAmounts/transactionShares/value")
            row["TRANSACTION_PRICE_PER_SHARE"], f8 = self._text_with_fns(node, "transactionAmounts/transactionPricePerShare/value")
            row["SHARES_OWNED_FOLLOWING_TRANSACTION"], f9 = self._text_with_fns(node, "postTransactionAmounts/sharesOwnedFollowingTransaction/value")
            row["DIRECT_OR_INDIRECT_OWNERSHIP"], f10 = self._text_with_fns(node, "ownershipNature/directOrIndirectOwnership/value")
            row["NATURE_OF_OWNERSHIP"], f11 = self._text_with_fns(node, "ownershipNature/natureOfOwnership/value")
            row["CONVERSION_OR_EXERCISE_PRICE"], f12 = self._text_with_fns(node, "conversionOrExercisePrice/value")
            row["EXERCISE_DATE"], f13 = self._text_with_fns(node, "exerciseDate/value")
            row["EXPIRATION_DATE"], f14 = self._text_with_fns(node, "expirationDate/value")
            row["UNDERLYING_SECURITY_TITLE"], f15 = self._text_with_fns(node, "underlyingSecurity/underlyingSecurityTitle/value")
            row["UNDERLYING_SECURITY_SHARES"], f16 = self._text_with_fns(node, "underlyingSecurity/underlyingSecurityShares/value")
            row["FOOTNOTE_IDS"] = self._combine_footnotes(
                [f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11, f12, f13, f14, f15, f16, self._footnotes_from_node(node)],
                footnotes
            )
            row["CREATED_AT"] = timestamp
            row["UPDATED_AT"] = timestamp
            rows.append(row)

        df = pd.DataFrame(rows, columns=self._expected_transaction_columns())
        if df.empty:
            return df

        for date_col in ["TRANSACTION_DATE", "DEEMED_EXECUTION_DATE", "PERIOD_OF_REPORT", "EXERCISE_DATE", "EXPIRATION_DATE"]:
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

        numeric_cols = ["TRANSACTION_SHARES", "TRANSACTION_PRICE_PER_SHARE", "SHARES_OWNED_FOLLOWING_TRANSACTION",
                        "CONVERSION_OR_EXERCISE_PRICE", "UNDERLYING_SECURITY_SHARES"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _parse_holdings(
        self,
        root: Optional[ET.Element],
        filing_info: pd.DataFrame,
        issuer: Dict[str, Any],
        owner: Dict[str, Any],
        footnotes: Dict[str, str]
    ) -> pd.DataFrame:
        if root is None:
            return pd.DataFrame(columns=self._expected_holdings_columns())

        base = self._holdings_base_row(filing_info, issuer, owner)
        timestamp = pd.Timestamp.now()
        rows: List[Dict[str, Any]] = []

        for node in root.findall(".//nonDerivativeHolding"):
            row = base.copy()
            row["TABLE_TYPE"] = "NON_DERIVATIVE_HOLDING"
            row["SECURITY_TITLE"], f1 = self._text_with_fns(node, "securityTitle/value")
            row["SHARES_OWNED"], f2 = self._text_with_fns(node, "postTransactionAmounts/sharesOwnedFollowingTransaction/value")
            row["DIRECT_OR_INDIRECT_OWNERSHIP"], f3 = self._text_with_fns(node, "ownershipNature/directOrIndirectOwnership/value")
            row["NATURE_OF_OWNERSHIP"], f4 = self._text_with_fns(node, "ownershipNature/natureOfOwnership/value")
            row["FOOTNOTE_IDS"] = self._combine_footnotes([f1, f2, f3, f4, self._footnotes_from_node(node)], footnotes)
            row["CREATED_AT"] = timestamp
            row["UPDATED_AT"] = timestamp
            rows.append(row)

        for node in root.findall(".//derivativeHolding"):
            row = base.copy()
            row["TABLE_TYPE"] = "DERIVATIVE_HOLDING"
            row["SECURITY_TITLE"], f1 = self._text_with_fns(node, "securityTitle/value")
            row["SHARES_OWNED"], f2 = self._text_with_fns(node, "postTransactionAmounts/sharesOwnedFollowingTransaction/value")
            row["DIRECT_OR_INDIRECT_OWNERSHIP"], f3 = self._text_with_fns(node, "ownershipNature/directOrIndirectOwnership/value")
            row["NATURE_OF_OWNERSHIP"], f4 = self._text_with_fns(node, "ownershipNature/natureOfOwnership/value")
            row["CONVERSION_OR_EXERCISE_PRICE"], f5 = self._text_with_fns(node, "conversionOrExercisePrice/value")
            row["EXERCISE_DATE"], f6 = self._text_with_fns(node, "exerciseDate/value")
            row["EXPIRATION_DATE"], f7 = self._text_with_fns(node, "expirationDate/value")
            row["UNDERLYING_SECURITY_TITLE"], f8 = self._text_with_fns(node, "underlyingSecurity/underlyingSecurityTitle/value")
            row["UNDERLYING_SECURITY_SHARES"], f9 = self._text_with_fns(node, "underlyingSecurity/underlyingSecurityShares/value")
            row["FOOTNOTE_IDS"] = self._combine_footnotes(
                [f1, f2, f3, f4, f5, f6, f7, f8, f9, self._footnotes_from_node(node)],
                footnotes
            )
            row["CREATED_AT"] = timestamp
            row["UPDATED_AT"] = timestamp
            rows.append(row)

        df = pd.DataFrame(rows, columns=self._expected_holdings_columns())
        if df.empty:
            return df

        for date_col in ["PERIOD_OF_REPORT", "EXERCISE_DATE", "EXPIRATION_DATE"]:
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        for col in ["SHARES_OWNED", "CONVERSION_OR_EXERCISE_PRICE", "UNDERLYING_SECURITY_SHARES"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _transaction_base_row(
        self,
        filing_info: pd.DataFrame,
        issuer: Dict[str, Any],
        owner: Dict[str, Any]
    ) -> Dict[str, Any]:
        accession = filing_info["ACCESSION_NUMBER"].iloc[0] if not filing_info.empty else pd.NA
        period = filing_info["PERIOD_OF_REPORT"].iloc[0] if not filing_info.empty else pd.NA
        doc_type = filing_info["DOCUMENT_TYPE"].iloc[0] if not filing_info.empty else pd.NA
        return {
            "ACCESSION_NUMBER": accession,
            "DOCUMENT_TYPE": doc_type,
            "PERIOD_OF_REPORT": period,
            "ISSUER_CIK": issuer.get("cik") if issuer else pd.NA,
            "ISSUER_NAME": issuer.get("name") if issuer else pd.NA,
            "ISSUER_TRADING_SYMBOL": issuer.get("trading_symbol") if issuer else pd.NA,
            "RPT_OWNER_CIK": owner.get("cik") if owner else pd.NA,
            "RPT_OWNER_NAME": owner.get("name") if owner else pd.NA
        }

    def _holdings_base_row(
        self,
        filing_info: pd.DataFrame,
        issuer: Dict[str, Any],
        owner: Dict[str, Any]
    ) -> Dict[str, Any]:
        accession = filing_info["ACCESSION_NUMBER"].iloc[0] if not filing_info.empty else pd.NA
        period = filing_info["PERIOD_OF_REPORT"].iloc[0] if not filing_info.empty else pd.NA
        doc_type = filing_info["DOCUMENT_TYPE"].iloc[0] if not filing_info.empty else pd.NA
        return {
            "ACCESSION_NUMBER": accession,
            "DOCUMENT_TYPE": doc_type,
            "PERIOD_OF_REPORT": period,
            "ISSUER_CIK": issuer.get("cik") if issuer else pd.NA,
            "ISSUER_NAME": issuer.get("name") if issuer else pd.NA,
            "ISSUER_TRADING_SYMBOL": issuer.get("trading_symbol") if issuer else pd.NA,
            "RPT_OWNER_CIK": owner.get("cik") if owner else pd.NA,
            "RPT_OWNER_NAME": owner.get("name") if owner else pd.NA
        }

    def _get_issuer(self, root: Optional[ET.Element]) -> Dict[str, Any]:
        if root is None:
            return {}
        issuer_node = root.find(".//issuer")
        if issuer_node is None:
            return {}
        return {
            "cik": self._find_text(issuer_node, ".//issuerCik"),
            "name": self._find_text(issuer_node, ".//issuerName"),
            "trading_symbol": self._find_text(issuer_node, ".//issuerTradingSymbol")
        }

    def _get_primary_reporting_owner(self, root: Optional[ET.Element]) -> Dict[str, Any]:
        if root is None:
            return {}
        owner_node = root.find(".//reportingOwner")
        if owner_node is None:
            return {}
        address_node = owner_node.find(".//reportingOwnerAddress")
        rel_node = owner_node.find(".//reportingOwnerRelationship")
        return {
            "cik": self._find_text(owner_node, ".//rptOwnerCik"),
            "name": self._find_text(owner_node, ".//rptOwnerName"),
            "street1": self._find_text(address_node, ".//rptOwnerStreet1") if address_node is not None else None,
            "street2": self._find_text(address_node, ".//rptOwnerStreet2") if address_node is not None else None,
            "city": self._find_text(address_node, ".//rptOwnerCity") if address_node is not None else None,
            "state": self._find_text(address_node, ".//rptOwnerState") if address_node is not None else None,
            "zip": self._find_text(address_node, ".//rptOwnerZipCode") if address_node is not None else None,
            "is_director": self._find_text(rel_node, ".//isDirector") if rel_node is not None else None,
            "is_officer": self._find_text(rel_node, ".//isOfficer") if rel_node is not None else None,
            "officer_title": self._find_text(rel_node, ".//officerTitle") if rel_node is not None else None,
            "is_ten_pct": self._find_text(rel_node, ".//isTenPercentOwner") if rel_node is not None else None,
            "is_other": self._find_text(rel_node, ".//isOther") if rel_node is not None else None,
            "other_text": self._find_text(rel_node, ".//otherText") if rel_node is not None else None
        }

    def _text_with_fns(self, element: ET.Element, path: str) -> Tuple[Optional[str], Set[str]]:
        """Return text and footnote ids for a nested path."""
        target = self._find_node(element, path)
        text = target.text.strip() if target is not None and target.text else None
        fns: Set[str] = set()
        if target is not None:
            fn_attr = target.attrib.get("footnoteId")
            if fn_attr:
                fns.add(fn_attr.strip())
        return text, fns

    def _find_node(self, element: ET.Element, path: str) -> Optional[ET.Element]:
        current = element
        for part in path.split("/"):
            if current is None:
                return None
            current = current.find(part)
        return current

    def _find_text(self, element: Optional[ET.Element], path: str) -> Optional[str]:
        if element is None:
            return None
        target = element.find(path)
        return target.text.strip() if target is not None and target.text else None

    def _extract_regex(self, content: str, pattern: str) -> Optional[str]:
        match = re.search(pattern, content)
        return match.group(1).strip() if match else None

    def _combine_footnotes(self, fn_sets: List[Set[str]], footnote_map: Dict[str, str]) -> Any:
        combined: Set[str] = set()
        for fn_set in fn_sets:
            combined.update(fn_set)
        combined = {fn for fn in combined if fn in footnote_map or fn}
        if not combined:
            return pd.NA
        return ",".join(sorted(combined))

    def _footnotes_from_node(self, node: ET.Element) -> Set[str]:
        fn_attr = node.attrib.get("footnoteId")
        return {fn_attr.strip()} if fn_attr else set()
