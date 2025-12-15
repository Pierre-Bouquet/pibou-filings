"""Integration and persistence tests for Section 16 parser behavior."""

import pandas as pd
import pytest

from piboufilings import get_parser_for_form_type_internal
from piboufilings.core.downloader import SECDownloader
from piboufilings.parsers.form_sec16_parser import FormSection16Parser


@pytest.mark.integration
def test_section16_parser_with_real_filing(tmp_path):
    downloader = SECDownloader(
        user_name="Test Runner",
        user_agent_email="test@example.com",
        package_version="0.3.0",
        log_dir=tmp_path / "logs",
        max_workers=1,
        data_dir=tmp_path / "data_raw" / "test_raw",
    )

    index_df = downloader.get_sec_index_data(start_year=2024, end_year=2024)
    subset = index_df[index_df["Form Type"].str.startswith("4", na=False)].head(1)
    assert not subset.empty

    cik = subset.iloc[0]["CIK"]
    downloaded = downloader.download_filings(
        cik=cik,
        form_type="SECTION-6",
        start_year=2024,
        end_year=2024,
        show_progress=False,
        index_data_subset=subset,
    )
    assert not downloaded.empty
    raw_path = downloaded.iloc[0]["raw_path"]
    assert raw_path and raw_path.strip()

    with open(raw_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    parser = FormSection16Parser(output_dir=tmp_path / "parsed")
    parsed = parser.parse_filing(content)

    assert not parsed["filing_info"].empty
    # Expect at least one transaction or holding
    assert not parsed["transactions"].empty or not parsed["holdings"].empty
    assert parsed["filing_info"].iloc[0]["ISSUER_CIK"] is not None
    assert parsed["filing_info"].iloc[0]["RPT_OWNER_CIK"] is not None


def test_section16_save_dedup(tmp_path):
    parser = FormSection16Parser(output_dir=tmp_path)
    sample_rows = pd.DataFrame(
        [
            {"ACCESSION_NUMBER": "acc", "DOCUMENT_TYPE": "4", "PERIOD_OF_REPORT": "2023-01-01"},
            {"ACCESSION_NUMBER": "acc", "DOCUMENT_TYPE": "4", "PERIOD_OF_REPORT": "2023-01-01"},
        ]
    )
    parsed_data = {
        "filing_info": sample_rows,
        "transactions": pd.DataFrame(),
        "holdings": pd.DataFrame()
    }
    parser.save_parsed_data(parsed_data)
    # Append again to exercise deduplication path
    parser.save_parsed_data(parsed_data)
    saved = pd.read_csv(tmp_path / "sec16_info.csv")
    assert len(saved) == 2
    parser.save_parsed_data(parsed_data)
    saved_after = pd.read_csv(tmp_path / "sec16_info.csv")
    assert len(saved_after) == 2
    assert "PERIOD_OF_REPORT" in saved_after.columns


def test_parser_selector_routes_sec16():
    assert get_parser_for_form_type_internal("SECTION-6", "./out").__class__.__name__ == "FormSection16Parser"
    # Backward compatibility: still route numeric forms
    assert get_parser_for_form_type_internal("4", "./out").__class__.__name__ == "FormSection16Parser"
    assert get_parser_for_form_type_internal("13F-HR", "./out").__class__.__name__ == "Form13FParser"
    assert get_parser_for_form_type_internal("NPORT-P", "./out").__class__.__name__ == "FormNPORTParser"
    assert get_parser_for_form_type_internal("UNKNOWN", "./out") is None
