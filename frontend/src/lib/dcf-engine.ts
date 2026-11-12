/**
 * TypeScript mirror of `app/services/dcf.py` (project_fcff + build_valuation).
 *
 * The backend is authoritative. This exists only so a slider drag can preview
 * instantly instead of waiting for a round trip; `bun run check:parity` asserts
 * it reproduces the backend's numbers for every supported ticker.
 */

export type GrowthModel = "fade" | "constant"

export type EngineParams = {
  baseYear: number
  baseFcff: number
  growthRate: number
  terminalGrowth: number
  years: number
  model: GrowthModel
  wacc: number
  totalDebt: number
  cash: number
  shares: number
}

export type ProjectionRow = {
  year: number
  fcff: number
  discountFactor: number
  presentValue: number
}

export type ValuationSummary = {
  terminalValue: number
  presentValueTerminal: number
  enterpriseValue: number
  netDebt: number
  equityValue: number
  valuePerShare: number
}

export function projectFcff(params: EngineParams): ProjectionRow[] {
  const rows: ProjectionRow[] = []
  let fcff = params.baseFcff

  for (let index = 1; index <= params.years; index += 1) {
    const growth =
      params.model === "constant" || params.years <= 1
        ? params.growthRate
        : params.growthRate +
          ((params.terminalGrowth - params.growthRate) * (index - 1)) /
            (params.years - 1)

    fcff *= 1 + growth
    const discountFactor = 1 / (1 + params.wacc) ** index
    rows.push({
      year: params.baseYear + index,
      fcff,
      discountFactor,
      presentValue: fcff * discountFactor,
    })
  }

  return rows
}

export function terminalValue(
  finalFcff: number,
  terminalGrowth: number,
  wacc: number,
): number {
  if (wacc <= terminalGrowth) {
    throw new Error("WACC must be greater than terminal growth rate")
  }
  return (finalFcff * (1 + terminalGrowth)) / (wacc - terminalGrowth)
}

export function buildValuation(
  projection: ProjectionRow[],
  params: EngineParams,
): ValuationSummary {
  if (projection.length === 0) {
    throw new Error("projection cannot be empty")
  }
  if (params.shares <= 0) {
    throw new Error("shares outstanding must be positive")
  }

  const last = projection[projection.length - 1]
  if (!last) {
    throw new Error("projection cannot be empty")
  }
  const tv = terminalValue(last.fcff, params.terminalGrowth, params.wacc)
  const presentValueTerminal = tv * last.discountFactor
  const enterpriseValue =
    projection.reduce((total, row) => total + row.presentValue, 0) +
    presentValueTerminal

  const netDebt = params.totalDebt - params.cash
  const equityValue = enterpriseValue - netDebt

  return {
    terminalValue: tv,
    presentValueTerminal,
    enterpriseValue,
    netDebt,
    equityValue,
    valuePerShare: equityValue / params.shares,
  }
}

export function preview(params: EngineParams): {
  projection: ProjectionRow[]
  summary: ValuationSummary
} {
  const projection = projectFcff(params)
  return { projection, summary: buildValuation(projection, params) }
}
