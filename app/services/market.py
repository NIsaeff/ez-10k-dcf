"""Yahoo Finance market data for the CAPM inputs EDGAR cannot provide.

Fundamentals come from SEC filings (``financials.py``). This module fills only
the market gaps: price, beta, and the risk-free rate.

Yahoo's chart endpoint is unauthenticated, but ``quoteSummary`` requires a
cookie plus a crumb, and that endpoint rate-limits aggressively (429 seen in
practice). Everything here is therefore best-effort and optional: the chart
endpoint carries price, beta history and the risk-free rate, so a missing
quoteSummary only costs us Yahoo's published beta and market cap — both of
which the caller can derive (price x SEC shares outstanding).

Every response is cached under ``data/raw/market/`` with a 24h TTL. If a refresh
fails, a stale file is served rather than nothing and the caller flags it. Tests
monkeypatch the fetch functions, so none of them touch the network.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.config import settings

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
QUOTE_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
COOKIE_URL = "https://fc.yahoo.com"

QUOTE_MODULES = "price,summaryDetail,defaultKeyStatistics"

BENCHMARK = "^GSPC"
RISK_FREE_SYMBOL = "^TNX"

CACHE_TTL_SECONDS = 24 * 60 * 60
CRUMB_TTL_SECONDS = 60 * 60
# After a failed fetch, stop retrying this cache key for a while. Yahoo 429s
# hard, and a wizard session should not hammer it on every recalculation.
FAILURE_TTL_SECONDS = 10 * 60
MIN_BETA_OBSERVATIONS = 30
# Below this R^2 the regression explains almost nothing; the point estimate is
# noise and CAPM should fall back to a default beta instead of using it.
MIN_BETA_R2 = 0.05
BETA_SANE_RANGE = (0.2, 3.0)
BETA_DIVERGENCE = 0.30
# ^TNX quotes the 10-year yield in percent (4.21 -> 4.21%).
TREASURY_YIELD_DIVISOR = 100.0

HEADERS = {
    "User-Agent": settings.sec_user_agent,
    "Accept": "application/json",
}


class MarketDataUnavailable(Exception):
    """Yahoo could not be reached or returned an unusable payload."""


@dataclass
class MarketInputs:
    ticker: str
    price: float | None = None
    market_cap: float | None = None
    beta_computed: float | None = None
    beta_reported: float | None = None
    beta_observations: int = 0
    beta_r_squared: float | None = None
    risk_free_rate: float | None = None
    as_of: str | None = None
    available: bool = False
    flags: list[str] = field(default_factory=list)


_client: httpx.Client | None = None
_crumb: tuple[str, float] | None = None
_failures: dict[str, float] = {}


def _session() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(headers=HEADERS, follow_redirects=True)
    return _client


def _cache_path(name: str) -> Path:
    path = settings.data_dir / "raw" / "market" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _slug(symbol: str) -> str:
    return symbol.replace("^", "idx_").replace("/", "_")


def _cached_json(
    name: str,
    fetch: Callable[[], dict[str, Any]],
    *,
    max_age: float = CACHE_TTL_SECONDS,
) -> tuple[dict[str, Any], bool]:
    """Return (payload, served_stale)."""
    path = _cache_path(name)
    now = time.time()
    if path.exists() and (now - path.stat().st_mtime) <= max_age:
        return json.loads(path.read_text()), False

    blocked_until = _failures.get(name)
    if blocked_until is not None and blocked_until > now:
        if path.exists():
            return json.loads(path.read_text()), True
        raise MarketDataUnavailable(f"{name} failed recently; backing off")

    try:
        payload = fetch()
    except Exception:
        _failures[name] = now + FAILURE_TTL_SECONDS
        if path.exists():
            return json.loads(path.read_text()), True
        raise

    _failures.pop(name, None)

    path.write_text(json.dumps(payload))
    return payload, False


def _crumb_value(force: bool = False) -> str:
    global _crumb
    now = time.time()
    if not force and _crumb is not None and _crumb[1] > now:
        return _crumb[0]

    session = _session()
    try:
        # Returns 404 but still sets the cookies quoteSummary needs.
        session.get(COOKIE_URL, timeout=15)
    except httpx.HTTPError:
        pass

    response = session.get(CRUMB_URL, timeout=15)
    response.raise_for_status()
    value = response.text.strip()
    if not value:
        raise MarketDataUnavailable("Yahoo returned an empty crumb")
    _crumb = (value, now + CRUMB_TTL_SECONDS)
    return value


def chart(
    symbol: str,
    *,
    range_: str = "2y",
    interval: str = "1wk",
) -> tuple[dict[str, Any], bool]:
    """Fetch a Yahoo chart payload. Returns (payload, served_stale)."""
    params = {"range": range_, "interval": interval}
    url = CHART_URL.format(symbol=quote(symbol, safe=""))
    name = f"chart_{_slug(symbol)}_{range_}_{interval}.json"

    def fetch() -> dict[str, Any]:
        response = _session().get(url, params=params, timeout=20)
        response.raise_for_status()
        return response.json()

    return _cached_json(name, fetch)


def quote_summary(
    ticker: str, modules: str = QUOTE_MODULES
) -> tuple[dict[str, Any], bool]:
    """Fetch quoteSummary. Refreshes the crumb once on 401/403.

    Optional enrichment: this endpoint rate-limits (429), so callers must treat
    any failure as "no Yahoo-published beta or market cap" and carry on.
    """
    ticker = ticker.upper()
    name = f"quote_{ticker}.json"

    def fetch() -> dict[str, Any]:
        for attempt in (1, 2):
            crumb = _crumb_value(force=attempt == 2)
            response = _session().get(
                QUOTE_SUMMARY_URL.format(ticker=ticker),
                params={"modules": modules, "crumb": crumb},
                timeout=20,
            )
            if response.status_code in (401, 403) and attempt == 1:
                continue
            response.raise_for_status()
            return response.json()
        raise MarketDataUnavailable("Yahoo rejected the crumb twice")

    return _cached_json(name, fetch)


def _first_result(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    results = (payload.get(key) or {}).get("result") or []
    if not results:
        return None
    return results[0]


def _raw(node: Any) -> float | None:
    if isinstance(node, dict):
        value = node.get("raw")
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _iso_date(stamp: Any) -> str | None:
    if not isinstance(stamp, (int, float)):
        return None
    return datetime.fromtimestamp(float(stamp), tz=UTC).date().isoformat()


def _chart_node(payload: dict[str, Any]) -> dict[str, Any]:
    return _first_result(payload, "chart") or {}


def _chart_price(payload: dict[str, Any]) -> float | None:
    node = _chart_node(payload)
    price = _raw((node.get("meta") or {}).get("regularMarketPrice"))
    if price is not None:
        return price
    closes = _closes(payload)
    if not closes:
        return None
    return closes[max(closes)]


def _chart_time(payload: dict[str, Any]) -> str | None:
    node = _chart_node(payload)
    return _iso_date((node.get("meta") or {}).get("regularMarketTime"))


def _closes(payload: dict[str, Any]) -> dict[int, float]:
    """Map timestamp -> close, dropping nulls."""
    node = _chart_node(payload)
    timestamps = node.get("timestamp") or []
    quotes = (node.get("indicators") or {}).get("quote") or [{}]
    closes = quotes[0].get("close") or []

    result: dict[int, float] = {}
    for stamp, close in zip(timestamps, closes):
        if close is None:
            continue
        result[int(stamp)] = float(close)
    return result


def compute_beta(
    asset: dict[int, float],
    benchmark: dict[int, float],
) -> tuple[float | None, int, float | None]:
    """OLS slope of asset returns on benchmark returns.

    Returns (beta, observations, r_squared). Beta is None when there are too few
    aligned observations or the benchmark does not move.
    """
    common = sorted(set(asset) & set(benchmark))
    observations = max(len(common) - 1, 0)
    if observations < MIN_BETA_OBSERVATIONS:
        return None, observations, None

    asset_returns = [
        asset[common[i]] / asset[common[i - 1]] - 1.0 for i in range(1, len(common))
    ]
    benchmark_returns = [
        benchmark[common[i]] / benchmark[common[i - 1]] - 1.0
        for i in range(1, len(common))
    ]

    mean_asset = sum(asset_returns) / len(asset_returns)
    mean_benchmark = sum(benchmark_returns) / len(benchmark_returns)
    covariance = sum(
        (a - mean_asset) * (b - mean_benchmark)
        for a, b in zip(asset_returns, benchmark_returns)
    )
    variance_benchmark = sum((b - mean_benchmark) ** 2 for b in benchmark_returns)
    if variance_benchmark == 0:
        return None, observations, None

    variance_asset = sum((a - mean_asset) ** 2 for a in asset_returns)
    if variance_asset == 0:
        return None, observations, 0.0

    r_squared = covariance**2 / (variance_asset * variance_benchmark)
    return covariance / variance_benchmark, observations, r_squared


def reported_beta(payload: dict[str, Any]) -> float | None:
    """Yahoo's published beta from a quoteSummary payload."""
    node = _first_result(payload, "quoteSummary") or {}
    return _raw((node.get("defaultKeyStatistics") or {}).get("beta"))


def computed_beta(ticker: str) -> tuple[float | None, int, float | None]:
    """Beta from chart history: (beta, observations, r_squared)."""
    try:
        payload, _ = chart(ticker)
        benchmark_payload, _ = chart(BENCHMARK)
    except Exception:  # noqa: BLE001 - beta is optional
        return None, 0, None
    return compute_beta(_closes(payload), _closes(benchmark_payload))


def risk_free_rate() -> float | None:
    try:
        payload, _ = chart(RISK_FREE_SYMBOL, range_="5d", interval="1d")
    except Exception:  # noqa: BLE001 - risk-free is optional
        return None
    price = _chart_price(payload)
    if price is None:
        return None
    return price / TREASURY_YIELD_DIVISOR


def market_inputs(ticker: str) -> MarketInputs:
    """Best-effort market bundle. Never raises; degrades field by field."""
    ticker = ticker.upper().strip()
    result = MarketInputs(ticker=ticker)
    stale = False

    try:
        payload, served_stale = quote_summary(ticker)
        stale = stale or served_stale
        node = _first_result(payload, "quoteSummary") or {}
        price_node = node.get("price") or {}
        result.price = _raw(price_node.get("regularMarketPrice"))
        result.market_cap = _raw(price_node.get("marketCap"))
        result.beta_reported = reported_beta(payload)
        result.as_of = _iso_date(price_node.get("regularMarketTime"))
    except Exception:  # noqa: BLE001, S110 - the chart fallback below retries price
        pass

    beta_value, observations, r_squared = computed_beta(ticker)
    result.beta_computed = beta_value
    result.beta_observations = observations
    result.beta_r_squared = r_squared

    if beta_value is None:
        result.flags.append(
            "beta_unavailable" if observations == 0 else "beta_low_observations"
        )
    else:
        if observations < MIN_BETA_OBSERVATIONS:
            result.flags.append("beta_low_observations")
        low_r2 = r_squared is not None and r_squared < MIN_BETA_R2
        out_of_range = not (BETA_SANE_RANGE[0] <= beta_value <= BETA_SANE_RANGE[1])
        if low_r2 or out_of_range:
            result.flags.append("beta_unreliable")

    if result.price is None:
        try:
            payload, served_stale = chart(ticker)
            stale = stale or served_stale
            result.price = _chart_price(payload)
            result.as_of = result.as_of or _chart_time(payload)
        except Exception:  # noqa: BLE001, S110 - price is optional
            pass

    risk_free = risk_free_rate()
    if risk_free is None:
        result.flags.append("risk_free_unavailable")
    else:
        result.risk_free_rate = risk_free

    if result.price is None:
        result.flags.append("price_unavailable")

    if (
        result.beta_computed is not None
        and result.beta_reported is not None
        and abs(result.beta_computed - result.beta_reported) > BETA_DIVERGENCE
    ):
        result.flags.append("beta_divergence")

    if stale:
        result.flags.append("market_data_stale")

    result.available = any(
        value is not None
        for value in (result.price, result.beta_computed, result.risk_free_rate)
    )
    if not result.available:
        result.flags.append("market_data_unavailable")

    result.flags = list(dict.fromkeys(result.flags))
    return result
