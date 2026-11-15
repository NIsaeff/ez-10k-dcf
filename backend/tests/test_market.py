"""Market data tests. No network: every fetch is monkeypatched."""

import json
import os
import time

import httpx
import pytest

from app.services import market


def _prices_from_returns(returns: list[float], start: float = 100.0) -> list[float]:
    prices = [start]
    for value in returns:
        prices.append(prices[-1] * (1.0 + value))
    return prices


def _chart_payload(
    closes: list[float],
    *,
    start: int = 1_700_000_000,
    step: int = 604_800,
) -> dict:
    timestamps = [start + index * step for index in range(len(closes))]
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": closes[-1],
                        "regularMarketTime": timestamps[-1],
                    },
                    "timestamp": timestamps,
                    "indicators": {"quote": [{"close": closes}]},
                }
            ],
            "error": None,
        }
    }


class _Response:
    def __init__(self, status: int = 200, payload: dict | None = None, text: str = ""):
        self.status_code = status
        self._payload = payload or {}
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status {self.status_code}", request=None, response=None
            )

    def json(self) -> dict:
        return self._payload


class _StubSession:
    """Answers the crumb handshake and replays scripted quoteSummary responses."""

    def __init__(self, quote_responses: list[_Response]):
        self.quote_responses = list(quote_responses)
        self.crumb_calls = 0

    def get(self, url: str, **_kwargs) -> _Response:
        if url == market.COOKIE_URL:
            return _Response(404)
        if url == market.CRUMB_URL:
            self.crumb_calls += 1
            return _Response(200, text=f"crumb-{self.crumb_calls}")
        if url.startswith(market.QUOTE_SUMMARY_URL.split("{")[0]):
            return self.quote_responses.pop(0)
        raise AssertionError(f"unexpected url: {url}")


def test_compute_beta_recovers_known_slope() -> None:
    benchmark_returns = [0.01 * ((index % 7) - 3) for index in range(80)]
    asset_returns = [2.0 * value for value in benchmark_returns]

    timestamps = list(range(len(benchmark_returns) + 1))
    benchmark = dict(zip(timestamps, _prices_from_returns(benchmark_returns)))
    asset = dict(zip(timestamps, _prices_from_returns(asset_returns)))

    beta, observations, r_squared = market.compute_beta(asset, benchmark)
    assert beta == pytest.approx(2.0, abs=1e-9)
    assert observations == len(benchmark_returns)
    assert r_squared == pytest.approx(1.0)


def test_compute_beta_needs_enough_observations() -> None:
    timestamps = list(range(10))
    prices = {stamp: 100.0 + stamp for stamp in timestamps}
    beta, observations, r_squared = market.compute_beta(prices, prices)
    assert beta is None
    assert observations == 9
    assert r_squared is None


def test_compute_beta_rejects_flat_benchmark() -> None:
    timestamps = list(range(60))
    benchmark = {stamp: 100.0 for stamp in timestamps}
    asset = {stamp: 100.0 + stamp for stamp in timestamps}
    beta, observations, r_squared = market.compute_beta(asset, benchmark)
    assert beta is None
    assert observations == 59
    assert r_squared is None


def test_chart_price_and_closes() -> None:
    payload = _chart_payload([10.0, 11.0, 12.5])
    assert market._chart_price(payload) == 12.5
    assert list(market._closes(payload).values()) == [10.0, 11.0, 12.5]
    assert market._chart_time(payload) is not None


def test_market_inputs_parses_quote_and_charts(monkeypatch) -> None:
    quote = {
        "quoteSummary": {
            "result": [
                {
                    "price": {
                        "regularMarketPrice": {"raw": 70.5},
                        "marketCap": {"raw": 303_000_000_000},
                        "regularMarketTime": 1_762_300_000,
                    },
                    "defaultKeyStatistics": {"beta": {"raw": 0.55}},
                }
            ]
        }
    }
    returns = [0.01 * ((index % 5) - 2) for index in range(60)]
    payload = _chart_payload(_prices_from_returns(returns))

    monkeypatch.setattr(
        market, "quote_summary", lambda ticker, modules=market.QUOTE_MODULES: (quote, False)
    )
    monkeypatch.setattr(market, "chart", lambda symbol, **kwargs: (payload, False))
    monkeypatch.setattr(market, "risk_free_rate", lambda: 0.042)

    result = market.market_inputs("ko")

    assert result.ticker == "KO"
    assert result.price == 70.5
    assert result.market_cap == 303_000_000_000
    # Same payload for asset and benchmark -> beta of exactly 1.0.
    assert result.beta_computed == pytest.approx(1.0)
    assert result.beta_r_squared == pytest.approx(1.0)
    assert result.beta_observations == 60
    assert result.beta_reported == 0.55
    assert "beta_unreliable" not in result.flags
    assert result.risk_free_rate == 0.042
    assert result.available is True
    assert "beta_divergence" in result.flags
    assert "market_data_unavailable" not in result.flags


def test_market_inputs_degrades_when_yahoo_fails(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise market.MarketDataUnavailable("offline")

    monkeypatch.setattr(market, "quote_summary", boom)
    monkeypatch.setattr(market, "chart", boom)
    monkeypatch.setattr(market, "risk_free_rate", lambda: None)

    result = market.market_inputs("KO")

    assert result.available is False
    assert result.price is None
    assert result.beta_computed is None
    for flag in (
        "price_unavailable",
        "beta_unavailable",
        "risk_free_unavailable",
        "market_data_unavailable",
    ):
        assert flag in result.flags


def test_cached_json_serves_stale_on_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(market.settings, "data_dir", tmp_path)
    path = tmp_path / "raw" / "market" / "stale.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"value": 1}))
    old = time.time() - 10 * 24 * 60 * 60
    os.utime(path, (old, old))

    def boom() -> dict:
        raise RuntimeError("network down")

    payload, served_stale = market._cached_json("stale.json", boom)

    assert payload == {"value": 1}
    assert served_stale is True


def test_cached_json_writes_fresh_payload(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(market.settings, "data_dir", tmp_path)

    payload, served_stale = market._cached_json("fresh.json", lambda: {"value": 2})

    assert payload == {"value": 2}
    assert served_stale is False
    assert json.loads((tmp_path / "raw" / "market" / "fresh.json").read_text()) == {
        "value": 2
    }


def test_quote_summary_refreshes_crumb_once(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(market.settings, "data_dir", tmp_path)
    monkeypatch.setattr(market, "_crumb", None)

    stub = _StubSession(
        [
            _Response(401),
            _Response(200, {"quoteSummary": {"result": []}}),
        ]
    )
    monkeypatch.setattr(market, "_session", lambda: stub)

    payload, served_stale = market.quote_summary("KO")

    assert payload["quoteSummary"]["result"] == []
    assert served_stale is False
    # First attempt + refreshed crumb after the 401.
    assert stub.crumb_calls == 2


def test_quote_summary_gives_up_after_two_auth_failures(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(market.settings, "data_dir", tmp_path)
    monkeypatch.setattr(market, "_crumb", None)

    stub = _StubSession([_Response(401), _Response(401)])
    monkeypatch.setattr(market, "_session", lambda: stub)

    with pytest.raises(httpx.HTTPStatusError):
        market.quote_summary("KO")


def test_load_company_is_cached() -> None:
    from app.services import financials

    assert hasattr(financials.load_company, "cache_clear")


def test_market_inputs_flags_unreliable_beta(monkeypatch) -> None:
    # Asset returns independent of the benchmark -> R^2 near zero, so the point
    # estimate is noise and CAPM must not use it.
    benchmark_returns = [0.01 * ((index % 3) - 1) for index in range(60)]
    asset_returns = [0.01 * (1 if index % 2 else -1) for index in range(60)]
    asset_payload = _chart_payload(_prices_from_returns(asset_returns))
    benchmark_payload = _chart_payload(_prices_from_returns(benchmark_returns))

    def fake_chart(symbol, **_kwargs):
        if symbol == market.BENCHMARK:
            return benchmark_payload, False
        return asset_payload, False

    monkeypatch.setattr(market, "chart", fake_chart)
    monkeypatch.setattr(market, "quote_summary", lambda *a, **k: ({}, False))
    monkeypatch.setattr(market, "risk_free_rate", lambda: 0.042)

    result = market.market_inputs("KO")

    assert result.beta_r_squared is not None
    assert result.beta_r_squared < market.MIN_BETA_R2
    assert "beta_unreliable" in result.flags


def test_failed_fetch_backs_off(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(market.settings, "data_dir", tmp_path)
    calls = {"count": 0}

    def boom() -> dict:
        calls["count"] += 1
        raise RuntimeError("network down")

    with pytest.raises(RuntimeError):
        market._cached_json("down.json", boom)
    with pytest.raises(market.MarketDataUnavailable):
        market._cached_json("down.json", boom)

    assert calls["count"] == 1
