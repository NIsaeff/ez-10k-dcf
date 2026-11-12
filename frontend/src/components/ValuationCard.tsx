import { BreakdownChain } from "@/components/valuation/BreakdownChain"
import { FactTable } from "@/components/valuation/FactTable"
import { MetricGrid } from "@/components/valuation/MetricGrid"
import type { ValuationResult } from "@/lib/chat"
import { buildBreakdownLines, buildMetricItems } from "@/lib/derivation"
import { compact, perShare } from "@/lib/format"

export function ValuationCard({ valuation }: { valuation: ValuationResult }) {
  const summary = valuation.valuation
  const latest = valuation.history[valuation.history.length - 1]
  const facts = valuation.source_facts ?? []

  return (
    <section className="mt-2 w-full rounded-xl border bg-card p-4 text-card-foreground shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {valuation.ticker} · FY{latest?.fiscal_year} 10-K
          </p>
          <h3 className="truncate text-base font-semibold">
            {valuation.company_name}
          </h3>
          <p className="text-xs text-muted-foreground">
            Filed {valuation.filing.filed} · {valuation.filing.accession_number}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
            DCF value / share
          </p>
          <p className="text-2xl font-semibold tabular-nums">
            {perShare(summary.value_per_share)}
          </p>
        </div>
      </div>

      <div className="mt-4">
        <MetricGrid items={buildMetricItems(valuation)} />
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[30rem] text-left text-xs">
          <thead className="text-muted-foreground">
            <tr className="border-b">
              <th className="py-1.5 pr-3 font-medium">FY</th>
              <th className="py-1.5 pr-3 font-medium">EBIT</th>
              <th className="py-1.5 pr-3 font-medium">D&amp;A</th>
              <th className="py-1.5 pr-3 font-medium">CapEx</th>
              <th className="py-1.5 font-medium">FCFF</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {valuation.history.map((year) => (
              <tr key={year.fiscal_year} className="border-b border-border/40">
                <td className="py-1.5 pr-3">{year.fiscal_year}</td>
                <td className="py-1.5 pr-3">{compact(year.ebit)}</td>
                <td className="py-1.5 pr-3">
                  {compact(year.depreciation_amortization)}
                </td>
                <td className="py-1.5 pr-3">
                  {compact(year.capital_expenditures)}
                </td>
                <td className="py-1.5">{compact(year.fcff)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4">
        <BreakdownChain lines={buildBreakdownLines(valuation)} />
      </div>

      <div className="mt-3">
        <FactTable facts={facts} />
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {valuation.flags.map((flag) => (
          <span
            key={flag}
            className="rounded-full border border-border/60 bg-muted/40 px-1.5 py-0.5 text-[10px] text-muted-foreground"
          >
            {flag}
          </span>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[10px] text-muted-foreground">
        <a
          href={valuation.filing.url}
          target="_blank"
          rel="noreferrer"
          className="underline underline-offset-2 hover:text-foreground"
        >
          Source: SEC 10-K
        </a>
        <span>{valuation.disclaimer}</span>
      </div>
    </section>
  )
}
