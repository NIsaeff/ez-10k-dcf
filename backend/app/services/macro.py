"""Deterministic FRED macro series for the engine and the valuation card.

The chat reaches FRED through the MCP sidecar, where the model chooses what to
fetch. This module is the other path: plain HTTPS, typed values, on-disk cache
and provenance, so a valuation can name the rate environment it was priced in.

Cached under ``data/raw/fred/`` (same TTL as the sidecar). If a refresh fails
the stale file is served and the input is marked ``stale`` rather than dropped.
Tests monkeypatch ``_fetch``, so nothing here touches the network.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.schemas import MacroInput, MacroSnapshot

API_URL = "https://api.stlouisfed.org/fred/series/observations"
SERIES_URL = "https://fred.stlouisfed.org/series/{series_id}"
CACHE_DIR = settings.data_dir / "raw" / "fred"
CACHE_TTL_SECONDS = 6 * 60 * 60
TIMEOUT_SECONDS = 10.0
OBSERVATION_LIMIT = 5


@dataclass(frozen=True)
class Series:
    role: str
    series_id: str
    label: str
    units: str
    # Older than this many days and the value is reported as stale.
    max_age_days: int


SERIES: dict[str, Series] = {
    "risk_free": Series(
        role="risk_free",
        series_id="DGS10",
        label="10-year Treasury constant maturity",
        units="Percent",
        max_age_days=7,
    ),
    "cpi": Series(
        role="cpi",
        series_id="CPIAUCSL",
        label="CPI, all urban consumers",
        units="Index 1982-1984=100",
        max_age_days=45,
    ),
    "real_gdp": Series(
        role="real_gdp",
        series_id="GDPC1",
        label="Real GDP",
        units="Billions of chained dollars",
        max_age_days=180,
    ),
    "unemployment": Series(
        role="unemployment",
        series_id="UNRATE",
        label="Unemployment rate",
        units="Percent",
        max_age_days=45,
    ),
}


class MacroUnavailable(Exception):
    """FRED could not be reached, or the key is missing."""


def _cache_path(series_id: str) -> Path:
    return CACHE_DIR / f"{series_id}.json"


def _read_cache(series_id: str) -> tuple[list[dict[str, Any]], float] | None:
    path = _cache_path(series_id)
    try:
        payload = json.loads(path.read_text())
        return list(payload["observations"]), float(payload["fetched_at"])
    except (OSError, KeyError, TypeError, ValueError):
        return None


def _write_cache(series_id: str, observations: list[dict[str, Any]], now: float) -> None:
    path = _cache_path(series_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"series_id": series_id, "fetched_at": now, "observations": observations}
            )
        )
    except OSError:
        pass


def _fetch(series_id: str, *, limit: int = OBSERVATION_LIMIT) -> list[dict[str, Any]]:
    """The only network edge in this module."""
    if not settings.fred_api_key:
        raise MacroUnavailable("FRED_API_KEY is not set")
    response = httpx.get(
        API_URL,
        params={
            "series_id": series_id,
            "api_key": settings.fred_api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        },
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return list(response.json().get("observations") or [])


def observations(series_id: str, *, now: float | None = None) -> tuple[list[dict[str, Any]], float, bool]:
    """Observations plus the fetch time and whether they came from a stale cache."""
    moment = time.time() if now is None else now
    cached = _read_cache(series_id)

    if cached is not None and moment - cached[1] < CACHE_TTL_SECONDS:
        return cached[0], cached[1], False

    try:
        fresh = _fetch(series_id)
    except Exception:
        if cached is not None:
            return cached[0], cached[1], True
        raise

    _write_cache(series_id, fresh, moment)
    return fresh, moment, False


def _latest(rows: list[dict[str, Any]]) -> tuple[float, str] | None:
    # FRED returns "." for missing observations.
    for row in rows:
        raw = row.get("value")
        if raw in (None, ".", ""):
            continue
        try:
            return float(raw), str(row.get("date") or "")
        except (TypeError, ValueError):
            continue
    return None


def _too_old(observation_date: str, max_age_days: int, moment: float) -> bool:
    try:
        observed = date.fromisoformat(observation_date)
    except ValueError:
        return True
    today = datetime.fromtimestamp(moment, tz=UTC).date()
    return (today - observed).days > max_age_days


def _iso(moment: float) -> str:
    return datetime.fromtimestamp(moment, tz=UTC).isoformat(timespec="seconds")


def input_for(role: str, *, now: float | None = None) -> MacroInput | None:
    """Latest observation for one role, or None when FRED has nothing usable."""
    spec = SERIES[role]
    moment = time.time() if now is None else now
    try:
        rows, fetched_at, served_stale = observations(spec.series_id, now=moment)
    except Exception:  # noqa: BLE001 - macro is context, never a hard failure here
        return None

    latest = _latest(rows)
    if latest is None:
        return None
    value, observed = latest

    return MacroInput(
        role=spec.role,
        series=spec.series_id,
        label=spec.label,
        value=value,
        units=spec.units,
        observation_date=observed,
        fetched_at=_iso(fetched_at),
        source="fred",
        url=SERIES_URL.format(series_id=spec.series_id),
        stale=served_stale or _too_old(observed, spec.max_age_days, moment),
    )


def risk_free(now: float | None = None) -> MacroInput | None:
    """The one series the engine actually consumes (as a percentage)."""
    return input_for("risk_free", now=now)


def snapshot(
    *,
    risk_free_fallback: MacroInput | None = None,
    now: float | None = None,
) -> MacroSnapshot:
    """Every configured series, plus a status that says how much to trust it."""
    moment = time.time() if now is None else now
    inputs: list[MacroInput] = []
    flags: list[str] = []

    for role in SERIES:
        item = input_for(role, now=moment)
        if item is None and role == "risk_free" and risk_free_fallback is not None:
            item = risk_free_fallback
            flags.append("risk_free_fallback")
        if item is None:
            flags.append(f"macro_{role}_missing")
            continue

        inputs.append(item)
        if item.stale:
            flags.append(f"macro_{role}_stale")

    risk_free_input = next((item for item in inputs if item.role == "risk_free"), None)
    if risk_free_input is None:
        status = "absent"
    else:
        untrusted = (
            risk_free_input.stale
            or risk_free_input.source != "fred"
            or any(flag.endswith("_stale") for flag in flags)
        )
        status = "degraded" if untrusted else "complete"

    as_of = max((item.observation_date for item in inputs), default="")
    return MacroSnapshot(
        status=status,
        as_of=as_of,
        inputs=inputs,
        flags=list(dict.fromkeys(flags)),
    )
