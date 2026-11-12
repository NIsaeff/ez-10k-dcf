import type { ValuationResult } from "@/lib/chat"
import { compact, pct, perShare, shareCount } from "@/lib/format"

import type { ChainLine } from "@/components/valuation/BreakdownChain"
import type { MetricItem } from "@/components/valuation/MetricGrid"

/** Metric tiles for a finished valuation. Shared by the chat card and wizard. */
export function buildMetricItems(valuation: ValuationResult): MetricItem[] {
  const summary = valuation.valuation
  const assumptions = valuation.assumptions

  return [
    { label: "Enterprise value", value: compact(summary.enterprise_value) },
    { label: "Equity value", value: compact(summary.equity_value) },
    { label: "Net debt", value: compact(summary.net_debt) },
    { label: "WACC", value: pct(assumptions.wacc) },
    { label: "Terminal value", value: compact(summary.terminal_value) },
    { label: "Terminal growth", value: pct(assumptions.terminal_growth_rate) },
    { label: "FCFF base", value: compact(assumptions.fcff_base) },
    { label: "Growth (year 1)", value: pct(assumptions.growth_rate) },
  ]
}

/** The EV -> equity -> per-share derivation, rendered identically everywhere. */
export function buildBreakdownLines(valuation: ValuationResult): ChainLine[] {
  const summary = valuation.valuation
  const assumptions = valuation.assumptions
  const pvFcff = valuation.projection.reduce(
    (total, year) => total + year.present_value,
    0,
  )

  return [
    {
      op: "+",
      label: `PV of FCFF (${valuation.projection.length}y)`,
      value: compact(pvFcff),
    },
    {
      op: "+",
      label: "PV of terminal value",
      hint: `TV ${compact(summary.terminal_value)} @ ${pct(assumptions.terminal_growth_rate)}`,
      value: compact(summary.present_value_terminal),
    },
    {
      op: "=",
      label: "Enterprise value",
      value: compact(summary.enterprise_value),
      emphasis: true,
    },
    {
      op: "−",
      label: "Net debt",
      hint: `debt ${compact(summary.total_debt)} − cash ${compact(summary.cash_and_equivalents)}`,
      value: compact(summary.net_debt),
    },
    {
      op: "=",
      label: "Equity value",
      value: compact(summary.equity_value),
      emphasis: true,
    },
    {
      op: "÷",
      label: "Diluted shares",
      hint: assumptions.share_count_source,
      value: shareCount(summary.shares_outstanding),
    },
    {
      op: "=",
      label: "Value per share",
      value: perShare(summary.value_per_share),
      emphasis: true,
      divider: true,
    },
  ]
}
