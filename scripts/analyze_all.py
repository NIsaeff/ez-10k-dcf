"""Run the deterministic analyzer across the supported tickers.

Usage:
    uv run python -m scripts.analyze_all
"""

from app.services.valuation import SUPPORTED_TICKERS, analyze


def main() -> int:
    failures = 0
    for ticker in SUPPORTED_TICKERS:
        try:
            result = analyze(ticker)
        except Exception as exc:  # noqa: BLE001 - report any per-ticker failure
            failures += 1
            print(f"{ticker:6} FAIL {type(exc).__name__}: {exc}")
            continue

        v = result.valuation
        print(
            f"{ticker:6} OK  FY{result.history[-1].fiscal_year} "
            f"per_share=${v.value_per_share:,.2f} "
            f"EV=${v.enterprise_value / 1e9:,.1f}B "
            f"WACC={result.assumptions.wacc:.1%} "
            f"flags={','.join(result.flags) or 'none'}"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
