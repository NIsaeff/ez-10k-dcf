/**
 * Parity check: the TS engine must reproduce the backend's numbers.
 *
 *   uv run python -m scripts.dump_engine_reference
 *   bun run check:parity
 */

import reference from "../src/lib/__fixtures__/engine-reference.json"
import { buildValuation, projectFcff, type EngineParams } from "../src/lib/dcf-engine"

type ReferenceRow = {
  engine: {
    base_fcff: number
    growth_rate: number
    growth_model: "fade" | "constant"
    terminal_growth_rate: number
    projection_years: number
    wacc: number
    total_debt: number
    cash: number
    shares_outstanding: number
    base_year: number
  }
  value_per_share: number
  enterprise_value: number
  equity_value: number
}

const TOLERANCE = 1e-9

function close(a: number, b: number): boolean {
  const scale = Math.max(1, Math.abs(a), Math.abs(b))
  return Math.abs(a - b) <= TOLERANCE * scale
}

let failures = 0

for (const [ticker, row] of Object.entries(reference as Record<string, ReferenceRow>)) {
  const engine = row.engine
  const params: EngineParams = {
    baseYear: engine.base_year,
    baseFcff: engine.base_fcff,
    growthRate: engine.growth_rate,
    terminalGrowth: engine.terminal_growth_rate,
    years: engine.projection_years,
    model: engine.growth_model,
    wacc: engine.wacc,
    totalDebt: engine.total_debt,
    cash: engine.cash,
    shares: engine.shares_outstanding,
  }

  const projection = projectFcff(params)
  const summary = buildValuation(projection, params)

  const checks: Array<[string, number, number]> = [
    ["value_per_share", summary.valuePerShare, row.value_per_share],
    ["enterprise_value", summary.enterpriseValue, row.enterprise_value],
    ["equity_value", summary.equityValue, row.equity_value],
  ]

  for (const [field, actual, expected] of checks) {
    if (!close(actual, expected)) {
      failures += 1
      console.error(
        `${ticker} ${field}: ts=${actual} backend=${expected} (delta ${actual - expected})`,
      )
    }
  }
}

const tickers = Object.keys(reference).length
if (failures > 0) {
  console.error(`\n${failures} parity failure(s) across ${tickers} tickers`)
  process.exit(1)
}
console.log(`parity ok: ${tickers} tickers, value/EV/equity all match`)
