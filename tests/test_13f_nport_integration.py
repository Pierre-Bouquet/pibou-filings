"""Network integration tests that hit the live SEC endpoints for 13F and NPORT."""

import pytest

from piboufilings.core.downloader import SECDownloader
from piboufilings.parsers.form_13f_parser import Form13FParser
from piboufilings.parsers.form_nport_parser import FormNPORTParser


def _make_downloader(tmp_path):
    return SECDownloader(
        user_name="Test Runner",
        user_agent_email="test@example.com",
        package_version="0.3.0",
        log_dir=tmp_path / "logs",
        max_workers=1,
        data_dir=tmp_path / "data_raw" / "test_raw",
    )


@pytest.mark.integration
def test_13f_parser_with_real_filing(tmp_path):
    downloader = _make_downloader(tmp_path)
    index_df = downloader.get_sec_index_data(start_year=2024, end_year=2024)
    subset = index_df[index_df["Form Type"].str.contains("13F-HR", na=False)].head(1)
    assert not subset.empty

    cik = subset.iloc[0]["CIK"]
    downloaded = downloader.download_filings(
        cik=cik,
        form_type="13F-HR",
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

    parser = Form13FParser(output_dir=tmp_path / "parsed_13f")
    parsed = parser.parse_filing(content)

    assert not parsed["filing_info"].empty
    assert "IRS_NUMBER" in parsed["filing_info"].columns
    # Expect holdings to parse for typical 13F XML filings
    assert not parsed["holdings"].empty
    assert "NAME_OF_ISSUER" in parsed["holdings"].columns


@pytest.mark.integration
def test_nport_parser_with_real_filing(tmp_path):
    downloader = _make_downloader(tmp_path)
    index_df = downloader.get_sec_index_data(start_year=2024, end_year=2024)
    subset = index_df[index_df["Form Type"].str.contains("NPORT-P", na=False)].head(1)
    assert not subset.empty

    cik = subset.iloc[0]["CIK"]
    downloaded = downloader.download_filings(
        cik=cik,
        form_type="NPORT-P",
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

    parser = FormNPORTParser(output_dir=tmp_path / "parsed_nport")
    parsed = parser.parse_filing(content)

    # Filing info should exist even for exhibits; holdings may be empty for exhibit-only filings
    assert not parsed["filing_info"].empty
    assert "SEC_FILE_NUMBER" in parsed["filing_info"].columns
