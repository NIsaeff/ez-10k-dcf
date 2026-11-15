"""Dump backend engine outputs so the TS mirror can be checked against them.

Run before `bun run check:parity`:

    uv run python -m scripts.dump_engine_reference
"""

import json
from pathlib import Path

from app.schemas import FilingInfo
from app.services import valuation
from app.services.financials import build_from_facts

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "src"
    / "lib"
    / "__fixtures__"
    / "engine-reference.json"
)


def main() -> None:
    reference: dict[str, dict] = {}

    for fixture in sorted(FIXTURE_DIR.glob("*.json")):
        ticker = fixture.stem
        data = json.loads(fixture.read_text())
        company = build_from_facts(
            ticker=ticker,
            company_name=data["company_name"],
            cik=data["cik"],
            filing=FilingInfo(**data["filing"]),
            facts=data,
        )
        result = valuation.analyze_from_company(company)
        assert result.engine is not None
        reference[ticker] = {
            "engine": result.engine.model_dump(),
            "value_per_share": result.valuation.value_per_share,
            "enterprise_value": result.valuation.enterprise_value,
            "equity_value": result.valuation.equity_value,
        }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(reference, indent=2) + "\n")
    print(f"wrote {len(reference)} tickers to {OUTPUT}")


if __name__ == "__main__":
    main()
