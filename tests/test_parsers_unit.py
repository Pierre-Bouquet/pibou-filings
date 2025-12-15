"""Offline unit coverage for parsers, downloader path handling, and validation utilities."""

import importlib
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from piboufilings import get_parser_for_form_type_internal
from piboufilings.core.downloader import SECDownloader
from piboufilings.parsers.form_13f_parser import Form13FParser
from piboufilings.parsers.form_nport_parser import FormNPORTParser
from piboufilings.parsers.form_sec16_parser import FormSection16Parser
from piboufilings.parsers.parser_utils import validate_filing_content
from piboufilings.config import settings


def _sample_13f_content() -> str:
    holdings_xml = """
    <XML>
    <?xml version="1.0" encoding="UTF-8"?>
    <informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
      <infoTable>
        <nameOfIssuer>ACME CORP</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>000000000</cusip>
        <value>100</value>
        <shrsOrPrnAmt>
          <sshPrnamt>10</sshPrnamt>
          <sshPrnamtType>SH</sshPrnamtType>
        </shrsOrPrnAmt>
        <investmentDiscretion>Sole</investmentDiscretion>
        <votingAuthority>
          <Sole>10</Sole>
          <Shared>0</Shared>
          <None>0</None>
        </votingAuthority>
      </infoTable>
    </informationTable>
    </XML>
    """
    # First XML block is intentionally different so the parser picks the second one
    xml_header = "<XML><placeholder>header</placeholder></XML>"
    return textwrap.dedent(
        f"""
        SEC-HEADER
        ACCESSION NUMBER: 0000000000-00-000000
        CONFORMED SUBMISSION TYPE: 13F-HR
        CENTRAL INDEX KEY: 0001234567
        IRS NUMBER: 12-3456789
        CONFORMED PERIOD OF REPORT: 20231231
        FILED AS OF DATE: 20240131
        form13FFileNumber>028-12345</form13FFileNumber>
        tableEntryTotal>1</tableEntryTotal>
        tableValueTotal>100</tableValueTotal>
        List of Other Included Managers:
        1. 028-99999 Sample Manager
        <PAGE>
        {xml_header}
        {holdings_xml}
        """
    ).strip()


def _sample_nport_content(form_type: str = "NPORT-P") -> str:
    xml_block = """
    <XML>
    <edgarSubmission xmlns:nport="http://www.sec.gov/edgar/nport"
                     xmlns:ncom="http://www.sec.gov/edgar/nportcommon"
                     xmlns:com="http://www.sec.gov/edgar/common">
      <nport:genInfo>
        <nport:regName>Sample Fund</nport:regName>
        <nport:regFileNumber>811-00001</nport:regFileNumber>
        <nport:regLei>LEI123</nport:regLei>
        <nport:seriesName>Sample Series</nport:seriesName>
        <nport:seriesLei>SLEI123</nport:seriesLei>
        <nport:repPdEnd>2024-03-31</nport:repPdEnd>
        <nport:repPdDate>2024-03-31</nport:repPdDate>
        <nport:isFinalFiling>Y</nport:isFinalFiling>
      </nport:genInfo>
      <nport:fundInfo>
        <nport:totAssets>1000</nport:totAssets>
        <nport:totLiabs>100</nport:totLiabs>
        <nport:netAssets>900</nport:netAssets>
        <nport:assetsInvested>800</nport:assetsInvested>
        <nport:delayDeliv>0</nport:delayDeliv>
      </nport:fundInfo>
      <nport:invstOrSec>
        <nport:name>Sample Bond</nport:name>
        <nport:title>Bond</nport:title>
        <nport:cusip>111111111</nport:cusip>
        <nport:lei>LEI-HOLDING</nport:lei>
        <nport:balance>5</nport:balance>
        <nport:units>SH</nport:units>
        <nport:curCd>USD</nport:curCd>
        <nport:valUSD>1000</nport:valUSD>
        <nport:pctVal>0.5</nport:pctVal>
        <nport:payoffProfile>Plain</nport:payoffProfile>
        <nport:assetCat>Debt</nport:assetCat>
        <nport:issuerCat>Foreign</nport:issuerCat>
        <nport:invCountry>US</nport:invCountry>
        <nport:isRestrictedSec>N</nport:isRestrictedSec>
        <nport:fairValLevel>1</nport:fairValLevel>
        <nport:securityLending>
          <nport:isCashCollateral>Y</nport:isCashCollateral>
        </nport:securityLending>
        <nport:invCategory>Debt</nport:invCategory>
      </nport:invstOrSec>
    </edgarSubmission>
    </XML>
    """
    return textwrap.dedent(
        f"""
        SEC-HEADER
        ACCESSION NUMBER: 0001605941-24-000001
        CONFORMED SUBMISSION TYPE: {form_type}
        CENTRAL INDEX KEY: 0001605941
        CONFORMED PERIOD OF REPORT: 20240331
        SEC FILE NUMBER: 811-00001
        FILED AS OF DATE: 20240415
        PUBLIC DOCUMENT COUNT: 2
        {xml_block}
        """
    ).strip()


def _sample_section16_content() -> str:
    xml_body = """
    <ownershipDocument>
      <schemaVersion>5.0</schemaVersion>
      <documentType>4</documentType>
      <periodOfReport>2024-01-01</periodOfReport>
      <issuer>
        <issuerCik>0000001111</issuerCik>
        <issuerName>Issuer Inc</issuerName>
        <issuerTradingSymbol>ISSR</issuerTradingSymbol>
      </issuer>
      <reportingOwner>
        <reportingOwnerId>
          <rptOwnerCik>0000002222</rptOwnerCik>
          <rptOwnerName>Owner Person</rptOwnerName>
        </reportingOwnerId>
        <reportingOwnerAddress>
          <rptOwnerStreet1>1 Main St</rptOwnerStreet1>
          <rptOwnerCity>City</rptOwnerCity>
          <rptOwnerState>CA</rptOwnerState>
          <rptOwnerZipCode>94000</rptOwnerZipCode>
        </reportingOwnerAddress>
        <reportingOwnerRelationship>
          <isDirector>1</isDirector>
          <isOfficer>0</isOfficer>
          <officerTitle>CEO</officerTitle>
          <isTenPercentOwner>1</isTenPercentOwner>
          <isOther>0</isOther>
        </reportingOwnerRelationship>
      </reportingOwner>
      <nonDerivativeTable>
        <nonDerivativeTransaction footnoteId="F1">
          <securityTitle><value>Common Stock</value></securityTitle>
          <transactionCoding>
            <transactionFormType>4</transactionFormType>
            <transactionCode>P</transactionCode>
            <equitySwapInvolved>0</equitySwapInvolved>
          </transactionCoding>
          <transactionDate><value>2024-01-01</value></transactionDate>
          <transactionAmounts>
            <transactionShares><value>10</value></transactionShares>
            <transactionPricePerShare><value>5.5</value></transactionPricePerShare>
          </transactionAmounts>
          <postTransactionAmounts>
            <sharesOwnedFollowingTransaction><value>20</value></sharesOwnedFollowingTransaction>
          </postTransactionAmounts>
          <ownershipNature>
            <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
            <natureOfOwnership><value>Direct</value></natureOfOwnership>
          </ownershipNature>
        </nonDerivativeTransaction>
      </nonDerivativeTable>
      <footnotes>
        <footnote id="F1">Test note</footnote>
      </footnotes>
    </ownershipDocument>
    """
    return textwrap.dedent(
        f"""
        SEC-HEADER
        ACCESSION NUMBER: 0000000000-00-000000
        FILED AS OF DATE: 20240102
        {xml_body}
        """
    ).strip()


def test_13f_parser_parses_holdings_and_other_sections(tmp_path):
    parser = Form13FParser(output_dir=tmp_path)
    content = _sample_13f_content()

    parsed = parser.parse_filing(content)

    assert not parsed["filing_info"].empty
    filing_row = parsed["filing_info"].iloc[0]
    assert filing_row["IRS_NUMBER"] == "12-3456789"
    assert filing_row["FORM_13F_FILE_NUMBER"] == "028-12345"
    assert not parsed["holdings"].empty
    assert parsed["holdings"].iloc[0]["NAME_OF_ISSUER"] == "ACME CORP"
    # Other included managers should be captured from the text section
    included = parsed["other_included_managers"]
    assert len(included) == 1
    assert included.iloc[0]["RELATED_MANAGER_NAME"] == "Sample Manager"


def test_13f_save_parsed_data_deduplicates_and_renames(tmp_path):
    parser = Form13FParser(output_dir=tmp_path)
    parsed_data = {
        "filing_info": pd.DataFrame(
            [{"FORM_13F_FILE_NUMBER": "028-12345", "IRS_NUMBER": "12-3456789"}]
        ),
        "holdings": pd.DataFrame(
            [
                {
                    "FORM_13F_FILE_NUMBER": "028-12345",
                    "NAME_OF_ISSUER": "ACME",
                    "CUSIP": 0,
                    "SHARE_VALUE": 100,
                }
            ]
        ),
        "other_managers_reporting": pd.DataFrame(),
        "other_included_managers": pd.DataFrame(),
    }

    parser.save_parsed_data(parsed_data, "028-12345", "0001234567")
    parser.save_parsed_data(parsed_data, "028-12345", "0001234567")  # second call should dedupe

    info_path = tmp_path / "13f_info.csv"
    holdings_path = tmp_path / "13f_holdings.csv"
    assert info_path.exists()
    assert holdings_path.exists()

    info_df = pd.read_csv(info_path)
    holdings_df = pd.read_csv(holdings_path)
    # FORM_13F_FILE_NUMBER should be renamed when persisted
    assert "SEC_FILE_NUMBER" in info_df.columns
    assert "FORM_13F_FILE_NUMBER" not in info_df.columns
    assert len(info_df) == 1
    # Holdings should dedupe and keep SEC_FILE_NUMBER
    assert "SEC_FILE_NUMBER" in holdings_df.columns
    assert len(holdings_df) == 1


def test_nport_parser_skips_exhibits():
    parser = FormNPORTParser(output_dir="unused")
    content = _sample_nport_content(form_type="NPORT-EX")

    parsed = parser.parse_filing(content)

    assert not parsed["filing_info"].empty
    assert parsed["holdings"].empty  # exhibit filings should not parse holdings


def test_nport_parser_extracts_holdings_and_filing_info(tmp_path):
    parser = FormNPORTParser(output_dir=tmp_path)
    content = _sample_nport_content()

    parsed = parser.parse_filing(content)

    assert not parsed["filing_info"].empty
    info_row = parsed["filing_info"].iloc[0]
    assert info_row["SEC_FILE_NUMBER"] == "811-00001"
    assert info_row["CIK"] == 1605941
    assert info_row["FUND_LEI"] == "LEI123"

    assert not parsed["holdings"].empty
    holding_row = parsed["holdings"].iloc[0]
    assert holding_row["SECURITY_NAME"] == "Sample Bond"
    assert holding_row["SEC_FILE_NUMBER"] == "811-00001"
    assert holding_row["CUSIP"] == "111111111"
    # PCT_VALUE is numeric and should be coerced
    assert float(holding_row["PCT_VALUE"]) == 0.5
    assert holding_row["LEI"] == "LEI-HOLDING"
    assert holding_row["CIK"] == 1605941


def test_nport_save_parsed_data_drops_sensitive_columns(tmp_path):
    parser = FormNPORTParser(output_dir=tmp_path)
    parsed_data = {
        "filing_info": pd.DataFrame(
            [
                {
                    "ACCESSION_NUMBER": "0001605941-24-000001",
                    "CIK": "0001605941",
                    "PERIOD_OF_REPORT": "2024-03-31",
                    "FILED_DATE": "2024-04-15",
                    "COMPANY_NAME": "Sample Fund",
                    "IRS_NUMBER": "12-3456789",
                    "SEC_FILE_NUMBER": "811-00001",
                    "FUND_LEI": "LEI123",
                    "SERIES_LEI": "SLEI123",
                }
            ]
        ),
        "holdings": pd.DataFrame(
            [
                {
                    "ACCESSION_NUMBER": "0001605941-24-000001",
                    "PERIOD_OF_REPORT": "2024-03-31",
                    "FILED_DATE": "2024-04-15",
                    "CIK": "0001605941",
                    "SEC_FILE_NUMBER": "811-00001",
                    "SECURITY_NAME": "Sample Bond",
                    "CUSIP": "111111111",
                    "LEI": "LEI-HOLDING",
                    "PCT_VALUE": 0.5,
                }
            ]
        ),
    }

    parser.save_parsed_data(parsed_data)

    holdings_path = tmp_path / "nport_holdings.csv"
    assert holdings_path.exists()
    df = pd.read_csv(holdings_path)
    assert "CUSIP" in df.columns
    assert "LEI" in df.columns
    assert "CIK" in df.columns
    assert "ACCESSION_NUMBER" in df.columns
    # Expected columns should include SEC_FILE_NUMBER and PCT_VALUE data
    assert "SEC_FILE_NUMBER" in df.columns
    assert df["PCT_VALUE"].iloc[0] == 0.5
    # Dedup should keep single row across repeated saves
    parser.save_parsed_data(parsed_data)
    df_after = pd.read_csv(holdings_path)
    assert len(df_after) == 1


def test_nport_dedup_on_filing_info(tmp_path):
    parser = FormNPORTParser(output_dir=tmp_path)
    parsed_data = {
        "filing_info": pd.DataFrame(
            [
                {
                    "ACCESSION_NUMBER": "0001605941-24-000001",
                    "CIK": "0001605941",
                    "PERIOD_OF_REPORT": "2024-03-31",
                    "FILED_DATE": "2024-04-15",
                    "COMPANY_NAME": "Sample Fund",
                    "IRS_NUMBER": "12-3456789",
                    "SEC_FILE_NUMBER": "811-00001",
                    "FUND_LEI": "LEI123",
                }
            ]
        ),
        "holdings": pd.DataFrame(),
    }
    parser.save_parsed_data(parsed_data)
    parser.save_parsed_data(parsed_data)
    info_path = tmp_path / "nport_filing_info.csv"
    df = pd.read_csv(info_path)
    assert len(df) == 1
    assert "ACCESSION_NUMBER" in df.columns


def test_nport_dedup_prefers_row_with_cusip(tmp_path):
    parser = FormNPORTParser(output_dir=tmp_path)
    base_row_missing_cusip = {
        "ACCESSION_NUMBER": "0001605941-24-000001",
        "PERIOD_OF_REPORT": "2024-03-31",
        "FILED_DATE": "2024-04-15",
        "CIK": "0001605941",
        "SEC_FILE_NUMBER": "811-00001",
        "SECURITY_NAME": "Sample Bond",
        "CUSIP": pd.NA,
        "LEI": "LEI-HOLDING",
        "PCT_VALUE": 0.5,
    }
    better_row_with_cusip = {**base_row_missing_cusip, "CUSIP": "111111111"}
    parser.save_parsed_data(
        {
            "filing_info": pd.DataFrame(),
            "holdings": pd.DataFrame([base_row_missing_cusip]),
        }
    )
    parser.save_parsed_data(
        {
            "filing_info": pd.DataFrame(),
            "holdings": pd.DataFrame([better_row_with_cusip]),
        }
    )
    holdings_path = tmp_path / "nport_holdings.csv"
    df = pd.read_csv(holdings_path)
    assert len(df) == 1
    assert df.iloc[0]["CUSIP"] == "111111111"


def test_section16_parser_merges_footnotes_and_flags(tmp_path):
    parser = FormSection16Parser(output_dir=tmp_path)
    content = _sample_section16_content()

    parsed = parser.parse_filing(content)

    assert not parsed["filing_info"].empty
    info = parsed["filing_info"].iloc[0]
    assert info["ISSUER_CIK"] == "0000001111"
    assert info["RPT_OWNER_CIK"] == "0000002222"
    assert bool(info["IS_DIRECTOR"]) is True
    assert bool(info["IS_TEN_PCT_OWNER"]) is True

    transactions = parsed["transactions"]
    assert not transactions.empty
    assert transactions.iloc[0]["FOOTNOTE_IDS"] == "F1"


def test_downloader_save_raw_filing_builds_expected_paths(tmp_path):
    downloader = SECDownloader(
        user_name="Test",
        user_agent_email="test@example.com",
        data_dir=tmp_path / "data" / "raw_test",
    )
    output_path = downloader._save_raw_filing(
        cik="0001234567",
        form_type="13F-HR",
        accession_number="0001234567-89-000001",
        content="sample content",
        form_13f_file_number_for_path="028-12345",
    )

    assert Path(output_path).exists()
    assert Path(output_path).read_text() == "sample content"
    # Path should include the sanitized form 13F file number and accession folder
    assert "028_12345" in output_path
    assert "0001234567-89-000001" in output_path


def test_downloader_save_raw_filing_skips_exhibits(tmp_path):
    downloader = SECDownloader(
        user_name="Test",
        user_agent_email="test@example.com",
        data_dir=tmp_path / "data" / "raw_test",
    )
    result = downloader._save_raw_filing(
        cik="0001234567",
        form_type="13F-HR/EX",
        accession_number="0001234567-89-000001",
        content="exhibit content",
        form_13f_file_number_for_path=None,
    )
    assert np.isnan(result)
    # No raw files should be written for exhibits
    assert not any((tmp_path / "data").rglob("*.txt"))


def test_validate_filing_content_flags_supported_form():
    content = """
    SEC-HEADER
    ACCESSION NUMBER: 0000000000-00-000000
    CENTRAL INDEX KEY: 0001111111
    COMPANY CONFORMED NAME: Demo Corp
    FILED AS OF DATE: 20240101
    CONFORMED SUBMISSION TYPE: 13F-HR
    <XML><data>placeholder</data></XML>
    """
    result = validate_filing_content(textwrap.dedent(content))
    assert result["is_valid_sec_filing"] is True
    assert result["form_type"] == "13F-HR"
    assert result["supported"] is True
    assert result["accession_number"] == "0000000000-00-000000"
    assert result["cik"] == "0001111111"


def test_parser_selector_matches_new_parsers(tmp_path):
    assert isinstance(get_parser_for_form_type_internal("13F-HR", tmp_path), Form13FParser)
    assert isinstance(get_parser_for_form_type_internal("NPORT-P", tmp_path), FormNPORTParser)
    assert isinstance(get_parser_for_form_type_internal("SECTION-6", tmp_path), FormSection16Parser)
    # Backward compatibility
    assert isinstance(get_parser_for_form_type_internal("4", tmp_path), FormSection16Parser)
    assert get_parser_for_form_type_internal("UNKNOWN", tmp_path) is None


def test_import_has_no_side_effects(monkeypatch, tmp_path):
    custom_base = tmp_path / "side_effect_base"
    custom_data = custom_base / "data_raw"
    custom_logs = custom_base / "logs"
    monkeypatch.setenv("PIBOUFILINGS_BASE_DIR", str(custom_base))
    monkeypatch.setenv("PIBOUFILINGS_DATA_DIR", str(custom_data))
    monkeypatch.setenv("PIBOUFILINGS_LOG_DIR", str(custom_logs))
    if custom_data.exists():
        for p in custom_data.rglob("*"):
            p.unlink()
    if custom_logs.exists():
        for p in custom_logs.rglob("*"):
            p.unlink()
    importlib.reload(settings)
    assert not custom_data.exists()
    assert not custom_logs.exists()
    # Restore defaults for downstream tests
    monkeypatch.delenv("PIBOUFILINGS_BASE_DIR", raising=False)
    monkeypatch.delenv("PIBOUFILINGS_DATA_DIR", raising=False)
    monkeypatch.delenv("PIBOUFILINGS_LOG_DIR", raising=False)
    importlib.reload(settings)


def test_manifest_excludes_local_datasets():
    manifest = Path("MANIFEST.in").read_text()
    assert "my_sec_data" in manifest
    assert "my_sec_raw_data" in manifest
