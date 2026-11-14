import type { ValuationResult } from "@/lib/chat"
import { preview, type EngineParams } from "@/lib/dcf-engine"
import type { WizardSearch } from "@/lib/wizard-state"

/**
 * Recompute a result locally from the backend's engine inputs plus the current
 * URL assumptions, so sliders feel instant. The backend's response replaces
 * this on settle; `bun run check:parity` keeps the two in agreement.
 */
export function withPreview(
  result: ValuationResult,
  search: WizardSearch,
): ValuationResult {
  const engine = result.engine
  if (!engine) return result

  const params: EngineParams = {
    baseYear: engine.base_year,
    baseFcff: engine.base_fcff,
    growthRate: engine.growth_rate,
    terminalGrowth: search.terminal / 100,
    years: search.years,
    model: search.model,
    wacc: search.wacc === undefined ? engine.base_wacc : search.wacc / 100,
    totalDebt: engine.total_debt,
    cash: engine.cash,
    shares:
      search.shares === undefined
        ? engine.shares_outstanding
        : search.shares * 1_000_000,
  }

  let computed
  try {
    computed = preview(params)
  } catch {
    // e.g. WACC <= terminal growth while dragging; keep the last good result.
    return result
  }

  return {
    ...result,
    projection: computed.projection.map((row) => ({
      year: row.year,
      fcff: row.fcff,
      discount_factor: row.discountFactor,
      present_value: row.presentValue,
    })),
    valuation: {
      ...result.valuation,
      terminal_value: computed.summary.terminalValue,
      present_value_terminal: computed.summary.presentValueTerminal,
      enterprise_value: computed.summary.enterpriseValue,
      net_debt: computed.summary.netDebt,
      equity_value: computed.summary.equityValue,
      value_per_share: computed.summary.valuePerShare,
      total_debt: params.totalDebt,
      cash_and_equivalents: params.cash,
      shares_outstanding: params.shares,
    },
    assumptions: {
      ...result.assumptions,
      wacc: params.wacc,
      projection_years: params.years,
      terminal_growth_rate: params.terminalGrowth,
      growth_model: params.model,
    },
  }
}
