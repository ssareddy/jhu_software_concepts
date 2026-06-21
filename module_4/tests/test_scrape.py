"""
tests/test_scrape.py
---------------------
Coverage tests for the pure (non-Selenium) helper functions in scrape.py.

All Selenium-dependent code (_build_driver, _get_page_source, _safe_quit,
scrape_data, check_robots_txt) is marked ``# pragma: no cover`` in scrape.py
because it requires a live headless browser and network access — neither of
which is available in the test environment.

This file targets every *testable* function:
  - _build_search_url
  - _parse_entry
  - _parse_page
  - _get_resume_page
  - _write_resume_marker
  - _load_existing_records
  - _save_raw
"""
import json
import sys
import os

import pytest
from bs4 import BeautifulSoup
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# _build_search_url
# ---------------------------------------------------------------------------

@pytest.mark.analysis
def test_build_search_url_contains_page_param():
    """_build_search_url includes the correct page number in the query string."""
    from scrape import _build_search_url
    url = _build_search_url(page=3)
    assert "page=3" in url


@pytest.mark.analysis
def test_build_search_url_contains_per_page_param():
    """_build_search_url includes the per_page parameter."""
    from scrape import _build_search_url
    url = _build_search_url(page=1, per_page=20)
    assert "per_page=20" in url


@pytest.mark.analysis
def test_build_search_url_starts_with_base():
    """_build_search_url URL starts with the GradCafe base URL."""
    from scrape import _build_search_url, BASE_URL
    url = _build_search_url(page=1)
    assert url.startswith(BASE_URL)


@pytest.mark.analysis
def test_build_search_url_includes_survey_path():
    """_build_search_url URL includes the /survey/ path."""
    from scrape import _build_search_url
    url = _build_search_url(page=1)
    assert "/survey/" in url


@pytest.mark.analysis
def test_build_search_url_custom_per_page():
    """_build_search_url respects a custom per_page value."""
    from scrape import _build_search_url
    url = _build_search_url(page=5, per_page=50)
    assert "per_page=50" in url
    assert "page=5" in url


# ---------------------------------------------------------------------------
# _parse_entry — uses BeautifulSoup objects, no Selenium
# ---------------------------------------------------------------------------

def _make_rows(summary_html, tags_html=None, notes_html=None):
    """Helper: parse HTML strings into BeautifulSoup <tr> objects."""
    def _tr(html):
        if html is None:
            return None
        soup = BeautifulSoup(f"<table>{html}</table>", "html.parser")
        return soup.find("tr")
    return _tr(summary_html), _tr(tags_html), _tr(notes_html)


@pytest.mark.analysis
def test_parse_entry_extracts_institution():
    """_parse_entry pulls raw_institution_program from col 0."""
    from scrape import _parse_entry
    summary, tags, notes = _make_rows(
        '<tr>'
        '<td>MIT</td>'
        '<td>Computer Science · PhD</td>'
        '<td>Jun 06, 2026</td>'
        '<td><a href="/result/123">Accepted on Jun 02</a></td>'
        '</tr>',
        '<tr><td>Accepted on Jun 02   Fall 2026   American</td></tr>',
        '<tr><td>GPA: 3.9</td></tr>',
    )
    result = _parse_entry(summary, tags, notes)
    assert result["raw_institution_program"] == "MIT"


@pytest.mark.analysis
def test_parse_entry_extracts_url():
    """_parse_entry captures the /result/ href as the URL."""
    from scrape import _parse_entry
    summary, tags, notes = _make_rows(
        '<tr>'
        '<td>Stanford</td>'
        '<td>CS · Masters</td>'
        '<td>Mar 01, 2024</td>'
        '<td><a href="/result/456">Rejected on Feb 15</a></td>'
        '</tr>',
    )
    result = _parse_entry(summary, tags, notes)
    assert "/result/456" in result["url"]


@pytest.mark.analysis
def test_parse_entry_extracts_absolute_url():
    """_parse_entry keeps already-absolute URLs unchanged."""
    from scrape import _parse_entry
    summary, tags, notes = _make_rows(
        '<tr>'
        '<td>Yale</td>'
        '<td>Physics · PhD</td>'
        '<td>Apr 01, 2024</td>'
        '<td><a href="https://www.thegradcafe.com/result/789">Accepted</a></td>'
        '</tr>',
    )
    result = _parse_entry(summary, tags, notes)
    assert result["url"].startswith("https://")


@pytest.mark.analysis
def test_parse_entry_extracts_raw_notes():
    """_parse_entry captures the notes row text."""
    from scrape import _parse_entry
    summary, tags, notes = _make_rows(
        '<tr>'
        '<td>Harvard</td>'
        '<td>Biology · PhD</td>'
        '<td>Feb 20, 2024</td>'
        '<td><a href="/result/321">Accepted</a></td>'
        '</tr>',
        '<tr><td>Accepted   Fall 2026   International</td></tr>',
        '<tr><td>Strong research background in genomics.</td></tr>',
    )
    result = _parse_entry(summary, tags, notes)
    assert "genomics" in result["raw_notes"]


@pytest.mark.analysis
def test_parse_entry_no_url_returns_empty_string():
    """_parse_entry returns empty string for url when no /result/ link exists."""
    from scrape import _parse_entry
    summary, _, _ = _make_rows(
        '<tr><td>School</td><td>Program</td><td>Date</td><td>Status</td></tr>'
    )
    result = _parse_entry(summary, None, None)
    assert result.get("url", "") == ""


@pytest.mark.analysis
def test_parse_entry_too_few_cells_returns_empty_dict():
    """_parse_entry returns {} when the row has fewer than 3 cells."""
    from scrape import _parse_entry
    summary, _, _ = _make_rows('<tr><td>only one cell</td></tr>')
    result = _parse_entry(summary, None, None)
    assert result == {}


@pytest.mark.analysis
def test_parse_entry_no_tags_no_notes():
    """_parse_entry works when tags_row and notes_row are None."""
    from scrape import _parse_entry
    summary, _, _ = _make_rows(
        '<tr>'
        '<td>CMU</td>'
        '<td>ML · PhD</td>'
        '<td>Jan 15, 2024</td>'
        '<td><a href="/result/111">Waitlisted</a></td>'
        '</tr>',
    )
    result = _parse_entry(summary, None, None)
    assert result["raw_institution_program"] == "CMU"
    assert result["raw_notes"] == ""


@pytest.mark.analysis
def test_parse_entry_decision_extracted_from_decision_cell():
    """_parse_entry extracts decision keyword from the decision cell."""
    from scrape import _parse_entry
    summary, _, _ = _make_rows(
        '<tr>'
        '<td>Princeton</td>'
        '<td>Math · PhD</td>'
        '<td>Mar 10, 2024</td>'
        '<td><a href="/result/999">Rejected on Mar 05</a></td>'
        '</tr>',
    )
    result = _parse_entry(summary, None, None)
    assert "Rejected" in result["raw_degree_status"] or "rejected" in result["raw_degree_status"].lower()


# ---------------------------------------------------------------------------
# _parse_page — parses full HTML strings
# ---------------------------------------------------------------------------

def _make_page_html(rows_html: str) -> str:
    return f"""
    <html><body>
    <table>
      <tr><th>School</th><th>Program</th><th>Date</th><th>Decision</th></tr>
      {rows_html}
    </table>
    </body></html>
    """


@pytest.mark.analysis
def test_parse_page_returns_list():
    """_parse_page always returns a list."""
    from scrape import _parse_page
    result = _parse_page("<html><body></body></html>")
    assert isinstance(result, list)


@pytest.mark.analysis
def test_parse_page_empty_html_returns_empty():
    """_parse_page returns empty list when no table is present."""
    from scrape import _parse_page
    assert _parse_page("<html><body><p>no table</p></body></html>") == []


@pytest.mark.analysis
def test_parse_page_no_result_links_returns_empty():
    """_parse_page returns empty list when no /result/ links exist."""
    from scrape import _parse_page
    html = "<html><body><table><tr><td>A</td><td>B</td><td>C</td><td>D</td></tr></table></body></html>"
    assert _parse_page(html) == []


@pytest.mark.analysis
def test_parse_page_parses_one_record():
    """_parse_page extracts one record from a minimal valid page."""
    from scrape import _parse_page
    html = _make_page_html(
        '<tr>'
        '<td>MIT</td>'
        '<td>CS · PhD</td>'
        '<td>Jun 06, 2026</td>'
        '<td><a href="/result/1">Accepted on Jun 02</a></td>'
        '</tr>'
        '<tr><td>Accepted on Jun 02   Fall 2026   American</td></tr>'
        '<tr><td>Strong applicant.</td></tr>'
    )
    records = _parse_page(html)
    assert len(records) == 1
    assert records[0]["raw_institution_program"] == "MIT"


@pytest.mark.analysis
def test_parse_page_parses_multiple_records():
    """_parse_page extracts multiple records from a page with several entries."""
    from scrape import _parse_page
    entry = (
        '<tr>'
        '<td>{school}</td>'
        '<td>CS · PhD</td>'
        '<td>Jun 06, 2026</td>'
        '<td><a href="/result/{n}">Accepted</a></td>'
        '</tr>'
        '<tr><td>Accepted   Fall 2026   American</td></tr>'
    )
    html = _make_page_html(
        entry.format(school="MIT", n=1) +
        entry.format(school="Stanford", n=2) +
        entry.format(school="Harvard", n=3)
    )
    records = _parse_page(html)
    assert len(records) == 3


@pytest.mark.analysis
def test_parse_page_no_table_returns_empty():
    """_parse_page returns empty list when html has no <table>."""
    from scrape import _parse_page
    result = _parse_page("<html><body><div>no table here</div></body></html>")
    assert result == []


@pytest.mark.analysis
def test_parse_page_skips_header_rows():
    """_parse_page skips rows with <th> elements."""
    from scrape import _parse_page
    html = (
        "<html><body><table>"
        "<tr><th>School</th><th>Program</th><th>Date</th><th>Decision</th></tr>"
        '<tr><td>Yale</td><td>Physics · PhD</td><td>Mar 01, 2024</td>'
        '<td><a href="/result/10">Rejected</a></td></tr>'
        "<tr><td>Rejected   Fall 2026   International</td></tr>"
        "</table></body></html>"
    )
    records = _parse_page(html)
    assert len(records) == 1


# ---------------------------------------------------------------------------
# _get_resume_page
# ---------------------------------------------------------------------------

@pytest.mark.analysis
def test_get_resume_page_no_file_returns_1(tmp_path):
    """_get_resume_page returns 1 when no output file exists."""
    from scrape import _get_resume_page
    assert _get_resume_page(tmp_path / "nonexistent.json") == 1


@pytest.mark.analysis
def test_get_resume_page_reads_marker(tmp_path):
    """_get_resume_page reads the _resume_from_page marker."""
    from scrape import _get_resume_page
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"_resume_from_page": 42, "records": []}), encoding="utf-8")
    assert _get_resume_page(path) == 42


@pytest.mark.analysis
def test_get_resume_page_infers_from_records(tmp_path):
    """_get_resume_page infers next page from source_page in existing records."""
    from scrape import _get_resume_page
    records = [{"source_page": 5}, {"source_page": 7}]
    path = tmp_path / "raw.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    assert _get_resume_page(path) == 8  # max(5,7) + 1


@pytest.mark.analysis
def test_get_resume_page_empty_list_returns_1(tmp_path):
    """_get_resume_page returns 1 when file contains an empty list."""
    from scrape import _get_resume_page
    path = tmp_path / "raw.json"
    path.write_text(json.dumps([]), encoding="utf-8")
    assert _get_resume_page(path) == 1


@pytest.mark.analysis
def test_get_resume_page_corrupt_json_returns_1(tmp_path):
    """_get_resume_page returns 1 when the file contains invalid JSON."""
    from scrape import _get_resume_page
    path = tmp_path / "raw.json"
    path.write_text("not valid json {{{{", encoding="utf-8")
    assert _get_resume_page(path) == 1


# ---------------------------------------------------------------------------
# _write_resume_marker
# ---------------------------------------------------------------------------

@pytest.mark.analysis
def test_write_resume_marker_creates_file(tmp_path):
    """_write_resume_marker writes a JSON file with the marker."""
    from scrape import _write_resume_marker
    path = tmp_path / "raw.json"
    _write_resume_marker([{"url": "http://x.com/1"}], next_page=10, path=path)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["_resume_from_page"] == 10
    assert len(data["records"]) == 1


@pytest.mark.analysis
def test_write_resume_marker_overwrites_existing(tmp_path):
    """_write_resume_marker overwrites any existing file."""
    from scrape import _write_resume_marker
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"old": True}), encoding="utf-8")
    _write_resume_marker([], next_page=5, path=path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["_resume_from_page"] == 5


# ---------------------------------------------------------------------------
# _load_existing_records
# ---------------------------------------------------------------------------

@pytest.mark.analysis
def test_load_existing_records_no_file(tmp_path):
    """_load_existing_records returns [] when file does not exist."""
    from scrape import _load_existing_records
    assert _load_existing_records(tmp_path / "missing.json") == []


@pytest.mark.analysis
def test_load_existing_records_none_path():
    """_load_existing_records returns [] when path is None."""
    from scrape import _load_existing_records
    assert _load_existing_records(None) == []


@pytest.mark.analysis
def test_load_existing_records_plain_list(tmp_path):
    """_load_existing_records reads a plain JSON list."""
    from scrape import _load_existing_records
    records = [{"url": "http://x.com/1"}, {"url": "http://x.com/2"}]
    path = tmp_path / "raw.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    assert _load_existing_records(path) == records


@pytest.mark.analysis
def test_load_existing_records_resume_format(tmp_path):
    """_load_existing_records reads the 'records' key from resume-marker format."""
    from scrape import _load_existing_records
    records = [{"url": "http://x.com/3"}]
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"_resume_from_page": 5, "records": records}), encoding="utf-8")
    assert _load_existing_records(path) == records


@pytest.mark.analysis
def test_load_existing_records_corrupt_returns_empty(tmp_path):
    """_load_existing_records returns [] on invalid JSON."""
    from scrape import _load_existing_records
    path = tmp_path / "raw.json"
    path.write_text("{{not json}}", encoding="utf-8")
    assert _load_existing_records(path) == []


# ---------------------------------------------------------------------------
# _save_raw
# ---------------------------------------------------------------------------

@pytest.mark.analysis
def test_save_raw_writes_clean_list(tmp_path):
    """_save_raw writes a plain JSON list with no resume marker."""
    from scrape import _save_raw
    records = [{"url": "http://x.com/1", "raw_institution_program": "MIT"}]
    path = tmp_path / "output.json"
    _save_raw(records, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[0]["url"] == "http://x.com/1"
    assert "_resume_from_page" not in data


@pytest.mark.analysis
def test_save_raw_overwrites_existing_resume_marker(tmp_path):
    """_save_raw replaces a resume-marker dict with a clean list."""
    from scrape import _save_raw
    path = tmp_path / "output.json"
    path.write_text(json.dumps({"_resume_from_page": 10, "records": []}), encoding="utf-8")
    _save_raw([{"url": "http://x.com/final"}], path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)