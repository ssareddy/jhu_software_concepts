"""
tests/test_scrape_selenium.py
------------------------------
Real coverage for incremental_scraper.py's Selenium- and network-dependent functions:
check_robots_txt, _build_driver, _get_page_source, _safe_quit, and
scrape_data.

These were previously excluded from coverage via `# pragma: no cover`
on the theory that they require a live browser/network. That's not
true — every external dependency (urllib, Selenium's WebDriver/Wait)
is mocked here, so these tests are fast, deterministic, and hit no
network or real browser, while still exercising the real logic
(retry loops, rate-limit pause/rebuild, resume behavior, robots.txt
parsing, hang-detection fallback).

Note on mock targets: incremental_scraper.py imports ChromeWebDriver directly from
selenium.webdriver.chrome.webdriver (not via `webdriver.Chrome`, which
pylint on some Selenium versions flags as a false-positive
`not-callable`), so tests must patch `scrape.ChromeWebDriver`.
"""
import os
import sys
import time
import urllib.error
from unittest.mock import MagicMock, patch, call

import pytest
from selenium.common.exceptions import TimeoutException, WebDriverException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "worker"))

# Import via the qualified package path (etl.incremental_scraper), matching
# how consumer.py imports it (`from etl.incremental_scraper import
# scrape_data`). Importing under a *different* name here (a bare
# `import incremental_scraper`) would create a second, independent module
# object for the same file — Python doesn't dedupe imports across
# different sys.modules keys — which can leave coverage.py only tracking
# whichever copy happened to load first, undercounting real coverage.
import etl.incremental_scraper as scrape  # noqa: E402


# ---------------------------------------------------------------------------
# check_robots_txt
# ---------------------------------------------------------------------------

ROBOTS_ALLOW = """
User-agent: ClaudeBot
Disallow: /

User-agent: *
Disallow: /signin
Disallow: /register
"""

ROBOTS_DISALLOW = """
User-agent: *
Disallow: /survey/
Disallow: /signin
"""


def _mock_urlopen(content: str):
    """Build a context-manager mock standing in for urllib.request.urlopen."""
    resp = MagicMock()
    resp.read.return_value = content.encode("utf-8")
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


@pytest.mark.analysis
def test_check_robots_txt_allows_survey_when_not_disallowed():
    """/survey/ is allowed when the wildcard block doesn't disallow it."""
    with patch("etl.incremental_scraper.urllib.request.urlopen", return_value=_mock_urlopen(ROBOTS_ALLOW)):
        assert scrape.check_robots_txt() is True


@pytest.mark.analysis
def test_check_robots_txt_disallows_when_survey_blocked():
    """/survey/ is disallowed when the wildcard block explicitly blocks it."""
    with patch("etl.incremental_scraper.urllib.request.urlopen", return_value=_mock_urlopen(ROBOTS_DISALLOW)):
        assert scrape.check_robots_txt() is False


@pytest.mark.analysis
def test_check_robots_txt_ignores_named_bot_blocks():
    """A named-bot Disallow (e.g. ClaudeBot) must not affect the wildcard
    (browser UA) result, since incremental_scraper.py uses a standard browser UA."""
    with patch("etl.incremental_scraper.urllib.request.urlopen", return_value=_mock_urlopen(ROBOTS_ALLOW)):
        assert scrape.check_robots_txt() is True


@pytest.mark.analysis
def test_check_robots_txt_returns_false_on_fetch_error():
    """A network error fetching robots.txt fails safe (returns False,
    so the caller aborts rather than scraping blind)."""
    with patch(
        "etl.incremental_scraper.urllib.request.urlopen",
        side_effect=urllib.error.URLError("no route to host"),
    ):
        assert scrape.check_robots_txt() is False


@pytest.mark.analysis
def test_check_robots_txt_wildcard_block_ends_at_named_agent():
    """The wildcard (*) block ends when a different named User-agent
    line follows it directly (no blank-line separator) — exercises the
    'elif in_wildcard_block' branch that closes the block early."""
    robots_no_blank_separator = (
        "User-agent: *\n"
        "Disallow: /signin\n"
        "User-agent: ClaudeBot\n"
        "Disallow: /\n"
    )
    with patch("etl.incremental_scraper.urllib.request.urlopen",
               return_value=_mock_urlopen(robots_no_blank_separator)):
        # /survey/ isn't in the wildcard block's disallow list, so still allowed.
        assert scrape.check_robots_txt() is True


# ---------------------------------------------------------------------------
# _build_driver
# ---------------------------------------------------------------------------

@pytest.mark.analysis
def test_build_driver_constructs_headless_chrome():
    """_build_driver instantiates ChromeWebDriver with headless Options,
    without ever launching a real browser."""
    fake_driver = MagicMock()
    with patch("etl.incremental_scraper.ChromeWebDriver", return_value=fake_driver) as mock_chrome:
        driver = scrape._build_driver()

    assert driver is fake_driver
    mock_chrome.assert_called_once()
    _, kwargs = mock_chrome.call_args
    options = kwargs["options"]
    assert "--headless=new" in options.arguments


@pytest.mark.analysis
def test_build_driver_uses_explicit_paths_when_env_vars_set():
    """When CHROME_BIN / CHROMEDRIVER_PATH are set (as in the worker
    Docker image, which installs Chromium directly), _build_driver uses
    them explicitly instead of relying on Selenium Manager's runtime
    auto-download — which fails under a non-root container user with a
    'Permission denied' error trying to write its cache directory."""
    fake_driver = MagicMock()
    env = {"CHROME_BIN": "/usr/bin/chromium", "CHROMEDRIVER_PATH": "/usr/bin/chromedriver"}
    with patch.dict(os.environ, env), \
         patch("etl.incremental_scraper.ChromeWebDriver", return_value=fake_driver) as mock_chrome, \
         patch("etl.incremental_scraper.ChromeService") as mock_service_cls:
        driver = scrape._build_driver()

    assert driver is fake_driver
    mock_service_cls.assert_called_once_with(executable_path="/usr/bin/chromedriver")
    _, kwargs = mock_chrome.call_args
    assert kwargs["options"].binary_location == "/usr/bin/chromium"
    assert kwargs["service"] is mock_service_cls.return_value


# ---------------------------------------------------------------------------
# _get_page_source
# ---------------------------------------------------------------------------

@pytest.mark.analysis
def test_get_page_source_success_first_attempt():
    """Returns page_source immediately when the wait succeeds first try."""
    driver = MagicMock()
    driver.page_source = "<html>ok</html>"
    driver.title = "Grad Cafe"

    with patch("etl.incremental_scraper.WebDriverWait") as mock_wait, patch("etl.incremental_scraper.time.sleep"):
        mock_wait.return_value.until.return_value = True
        result = scrape._get_page_source(driver, "https://example.com/survey/?page=1")

    assert result == "<html>ok</html>"
    driver.get.assert_called_once_with("https://example.com/survey/?page=1")


@pytest.mark.analysis
def test_get_page_source_retries_then_succeeds():
    """Retries after a timeout on the first attempt, succeeds on the second."""
    driver = MagicMock()
    driver.page_source = "<html>ok</html>"
    driver.title = "Grad Cafe"

    with patch("etl.incremental_scraper.WebDriverWait") as mock_wait, patch("etl.incremental_scraper.time.sleep") as mock_sleep:
        mock_wait.return_value.until.side_effect = [TimeoutException("no body"), True]
        result = scrape._get_page_source(driver, "https://example.com", retries=2)

    assert result == "<html>ok</html>"
    assert mock_sleep.called  # retry backoff was invoked


@pytest.mark.analysis
def test_get_page_source_returns_none_after_all_retries_exhausted():
    """Returns None (not an exception) once every retry attempt fails."""
    driver = MagicMock()

    with patch("etl.incremental_scraper.WebDriverWait") as mock_wait, patch("etl.incremental_scraper.time.sleep"):
        mock_wait.return_value.until.side_effect = TimeoutException("no body")
        result = scrape._get_page_source(driver, "https://example.com", retries=2)

    assert result is None
    assert driver.get.call_count == 3  # initial attempt + 2 retries


# ---------------------------------------------------------------------------
# _safe_quit
# ---------------------------------------------------------------------------

@pytest.mark.analysis
def test_safe_quit_normal_quit_within_timeout():
    """When driver.quit() returns quickly, no force-kill fallback is used."""
    driver = MagicMock()
    driver.quit.return_value = None

    # _safe_quit does `import os` *inside* the function body, so the name
    # `os` in its local namespace resolves to the real global os module —
    # patch that directly rather than `scrape.os` (which doesn't exist as
    # a module-level attribute).
    with patch("os.kill") as mock_kill:
        scrape._safe_quit(driver, timeout=2)

    driver.quit.assert_called_once()
    mock_kill.assert_not_called()


@pytest.mark.analysis
def test_safe_quit_force_kills_when_quit_hangs():
    """When driver.quit() hangs past the timeout, falls back to os.kill()
    on the chromedriver process PID."""
    driver = MagicMock()
    driver.service.process.pid = 12345

    def _hanging_quit():
        time.sleep(0.5)  # longer than the 0.1s timeout below

    driver.quit.side_effect = _hanging_quit

    # create=True: signal.SIGKILL doesn't exist on Windows at all (it's a
    # Unix-only signal), so patch() must be told it's fine to create the
    # attribute rather than requiring it to already exist. The real code's
    # own getattr(signal, "SIGKILL", signal.SIGTERM) already handles this
    # platform difference at runtime — this is purely about letting the
    # test patch a name that may not be present on every OS.
    with patch("os.kill") as mock_kill, patch("signal.SIGKILL", 9, create=True):
        scrape._safe_quit(driver, timeout=0.1)

    mock_kill.assert_called_once_with(12345, 9)


@pytest.mark.analysis
def test_safe_quit_swallows_quit_exception():
    """An exception from driver.quit() itself (e.g. already-dead session)
    is swallowed, not propagated."""
    driver = MagicMock()
    driver.quit.side_effect = WebDriverException("session already terminated")

    # Should not raise.
    scrape._safe_quit(driver, timeout=2)


@pytest.mark.analysis
def test_safe_quit_swallows_kill_failure_after_hang():
    """If the force-kill fallback itself fails (e.g. process already gone,
    raising ProcessLookupError/OSError), that failure is swallowed too —
    _safe_quit must never raise, since it's called from a `finally` block."""
    driver = MagicMock()
    driver.service.process.pid = 12345

    def _hanging_quit():
        time.sleep(0.5)

    driver.quit.side_effect = _hanging_quit

    with patch("os.kill", side_effect=ProcessLookupError("no such process")):
        # Should not raise even though os.kill() itself fails.
        scrape._safe_quit(driver, timeout=0.1)


# ---------------------------------------------------------------------------
# scrape_data — main loop, mocking every external dependency
# ---------------------------------------------------------------------------

@pytest.mark.analysis
def test_scrape_data_raises_when_robots_txt_disallows():
    """Aborts immediately (no driver built) when robots.txt disallows /survey/."""
    with patch("etl.incremental_scraper.check_robots_txt", return_value=False):
        with pytest.raises(RuntimeError, match="robots.txt"):
            scrape.scrape_data(max_pages=1, output_file=None)


@pytest.mark.analysis
def test_scrape_data_happy_path_two_pages(tmp_path):
    """Scrapes two pages successfully, saves a checkpoint file, and quits
    the driver — with every external dependency mocked."""
    out_file = tmp_path / "raw_results.json"
    fake_driver = MagicMock()

    def fake_parse_page(_html):
        # A fresh dict each call — scrape_data mutates the dicts it gets
        # back (adding source_page/source_url), so a shared/reused dict
        # across pages would let a later page's write clobber an earlier
        # one, which is a test bug, not real behavior.
        return [{"raw_institution_program": "Test U"}]

    with patch("etl.incremental_scraper.check_robots_txt", return_value=True), \
         patch("etl.incremental_scraper._build_driver", return_value=fake_driver), \
         patch("etl.incremental_scraper._get_page_source", return_value="<html>content</html>"), \
         patch("etl.incremental_scraper._parse_page", side_effect=fake_parse_page), \
         patch("etl.incremental_scraper._safe_quit") as mock_quit, \
         patch("etl.incremental_scraper.time.sleep"):
        records = scrape.scrape_data(max_pages=2, output_file=out_file, start_page=1)

    assert len(records) == 2  # one record per page, 2 pages
    assert records[0]["source_page"] == 1
    assert records[1]["source_page"] == 2
    mock_quit.assert_called_once_with(fake_driver)
    assert out_file.exists()


@pytest.mark.analysis
def test_scrape_data_pauses_and_rebuilds_on_rate_limit(tmp_path):
    """When a page fails to load, writes a resume marker, tears down and
    rebuilds the driver, and retries the same page — without ever
    sleeping for the real RATE_LIMIT_PAUSE duration."""
    out_file = tmp_path / "raw_results.json"
    driver_1, driver_2 = MagicMock(), MagicMock()
    build_calls = [driver_1, driver_2]

    # First call to _get_page_source fails (None); second succeeds.
    get_page_results = [None, "<html>content</html>"]

    with patch("etl.incremental_scraper.check_robots_txt", return_value=True), \
         patch("etl.incremental_scraper._build_driver", side_effect=build_calls), \
         patch("etl.incremental_scraper._get_page_source", side_effect=get_page_results), \
         patch("etl.incremental_scraper._parse_page", return_value=[{"raw_institution_program": "Test U"}]), \
         patch("etl.incremental_scraper._safe_quit") as mock_quit, \
         patch("etl.incremental_scraper.time.sleep") as mock_sleep:
        records = scrape.scrape_data(max_pages=1, output_file=out_file, start_page=1)

    assert len(records) == 1
    # driver was torn down once for the failed page, once at the end
    assert mock_quit.call_count == 2
    # rate-limit countdown used time.sleep rather than blocking for real
    assert mock_sleep.called
    # resume marker should have been written during the pause
    import json
    with open(out_file) as fh:
        saved = json.load(fh)
    assert isinstance(saved, list)  # final save is a clean list (marker cleared)


@pytest.mark.analysis
def test_scrape_data_returns_in_memory_when_no_output_file():
    """output_file=None (used by app.py's Pull Data flow) skips writing
    to disk entirely and returns records in memory."""
    fake_driver = MagicMock()

    with patch("etl.incremental_scraper.check_robots_txt", return_value=True), \
         patch("etl.incremental_scraper._build_driver", return_value=fake_driver), \
         patch("etl.incremental_scraper._get_page_source", return_value="<html>content</html>"), \
         patch("etl.incremental_scraper._parse_page", return_value=[{"raw_institution_program": "Test U"}]), \
         patch("etl.incremental_scraper._safe_quit"), \
         patch("etl.incremental_scraper._save_raw") as mock_save, \
         patch("etl.incremental_scraper.time.sleep"):
        records = scrape.scrape_data(max_pages=1, output_file=None, start_page=1)

    assert len(records) == 1
    mock_save.assert_not_called()


@pytest.mark.analysis
def test_scrape_data_logs_loaded_existing_records(tmp_path, capsys):
    """When _load_existing_records returns prior records (e.g. resuming
    a previous run), scrape_data logs how many were loaded before
    continuing to scrape."""
    out_file = tmp_path / "raw_results.json"
    fake_driver = MagicMock()
    existing = [{"raw_institution_program": "Prior U", "source_page": 1}]

    with patch("etl.incremental_scraper.check_robots_txt", return_value=True), \
         patch("etl.incremental_scraper._load_existing_records", return_value=existing), \
         patch("etl.incremental_scraper._build_driver", return_value=fake_driver), \
         patch("etl.incremental_scraper._get_page_source", return_value="<html>content</html>"), \
         patch("etl.incremental_scraper._parse_page", return_value=[{"raw_institution_program": "New U"}]), \
         patch("etl.incremental_scraper._safe_quit"), \
         patch("etl.incremental_scraper.time.sleep"):
        records = scrape.scrape_data(max_pages=1, output_file=out_file, start_page=1)

    assert len(records) == 2  # 1 existing + 1 newly scraped
    out = capsys.readouterr().out
    assert "Loaded 1 existing records" in out


@pytest.mark.analysis
def test_scrape_data_writes_checkpoint_every_50_pages(tmp_path):
    """Every 50th successfully scraped page triggers an incremental
    checkpoint save (not just the final save at the end)."""
    out_file = tmp_path / "raw_results.json"
    fake_driver = MagicMock()

    with patch("etl.incremental_scraper.check_robots_txt", return_value=True), \
         patch("etl.incremental_scraper._build_driver", return_value=fake_driver), \
         patch("etl.incremental_scraper._get_page_source", return_value="<html>content</html>"), \
         patch("etl.incremental_scraper._parse_page", side_effect=lambda _html: [{"raw_institution_program": "Test U"}]), \
         patch("etl.incremental_scraper._safe_quit"), \
         patch("etl.incremental_scraper.time.sleep"), \
         patch("etl.incremental_scraper._save_raw") as mock_save:
        scrape.scrape_data(max_pages=50, output_file=out_file, start_page=1)

    # One checkpoint save at page 50, plus one final save at the end.
    assert mock_save.call_count == 2
