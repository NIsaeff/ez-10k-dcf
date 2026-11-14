"""Ticker search over the SEC universe."""

from app.services import edgar, valuation

PILOTS = ("AAPL", "MSFT", "KO")


def test_empty_query_returns_only_pilots() -> None:
    rows = edgar.search_tickers("", limit=10, pilots=PILOTS)
    assert {row["ticker"] for row in rows} == set(PILOTS)
    assert all(row["pilot"] for row in rows)


def test_pilot_matches_rank_first() -> None:
    rows = edgar.search_tickers("ko", limit=10, pilots=PILOTS)
    assert rows[0]["ticker"] == "KO"
    assert rows[0]["pilot"] is True


def test_ticker_prefix_beats_name_match() -> None:
    rows = edgar.search_tickers("ko", limit=20, pilots=PILOTS)
    ticker_prefix = [row for row in rows if row["ticker"].startswith("KO")]
    assert ticker_prefix, "expected ticker-prefix matches"
    positions = {row["ticker"]: index for index, row in enumerate(rows)}
    name_only = [row for row in rows if not row["ticker"].startswith("KO")]
    if name_only:
        assert positions[ticker_prefix[0]["ticker"]] < positions[name_only[0]["ticker"]]


def test_name_search_finds_company() -> None:
    rows = edgar.search_tickers("johnson", limit=10, pilots=PILOTS)
    assert any(row["ticker"] == "JNJ" for row in rows)
    assert all(row["pilot"] is False for row in rows)


def test_limit_is_respected() -> None:
    rows = edgar.search_tickers("a", limit=3, pilots=PILOTS)
    assert len(rows) == 3


def test_unknown_query_returns_empty() -> None:
    assert edgar.search_tickers("zzzznotacompany", pilots=PILOTS) == []


def test_non_pilot_ticker_uses_generic_wacc(monkeypatch) -> None:
    from tests.conftest import company_from_fixture

    def fake_load(ticker: str):
        company = company_from_fixture("KO")
        company.ticker = ticker
        return company

    monkeypatch.setattr(valuation.financials, "load_company", fake_load)

    result = valuation.analyze("JNJ", allow_any=True)

    assert result.ticker == "JNJ"
    assert result.assumptions.wacc == valuation.GENERIC_WACC
    assert "wacc_generic_default" in result.flags


def test_pilot_allowlist_still_guards_chat(monkeypatch) -> None:
    def fake_load(ticker: str):
        raise AssertionError("should not reach the loader")

    monkeypatch.setattr(valuation.financials, "load_company", fake_load)

    try:
        valuation.analyze("JNJ")
    except valuation.UnsupportedTicker:
        return
    raise AssertionError("expected UnsupportedTicker without allow_any")
