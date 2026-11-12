import type { ValuationResult } from "@/lib/chat"

function compact(value: number): string {
  const abs = Math.abs(value)
  const sign = value < 0 ? "-" : ""
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(0)}M`
  return `${sign}$${abs.toFixed(0)}`
}

function perShare(value: number): string {
  const sign = value < 0 ? "-" : ""
  return `${sign}$${Math.abs(value).toFixed(2)}`
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/60 bg-muted/30 p-2.5">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums">{value}</p>
    </div>
  )
}

export function ValuationCard({ valuation }: { valuation: ValuationResult }) {
  const summary = valuation.valuation
  const assumptions = valuation.assumptions
  const latest = valuation.history[valuation.history.length - 1]

  return (
    <section className="mt-2 w-full rounded-xl border bg-card p-4 text-card-foreground shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {valuation.ticker} · FY{latest?.fiscal_year} 10-K
          </p>
          <h3 className="truncate text-base font-semibold">{valuation.company_name}</h3>
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

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Metric label="Enterprise value" value={compact(summary.enterprise_value)} />
        <Metric label="Equity value" value={compact(summary.equity_value)} />
        <Metric label="Net debt" value={compact(summary.net_debt)} />
        <Metric label="WACC" value={pct(assumptions.wacc)} />
        <Metric label="Terminal value" value={compact(summary.terminal_value)} />
        <Metric label="Terminal growth" value={pct(assumptions.terminal_growth_rate)} />
        <Metric label="FCFF base" value={compact(assumptions.fcff_base)} />
        <Metric label="Growth (year 1)" value={pct(assumptions.growth_rate)} />
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
                <td className="py-1.5 pr-3">{compact(year.capital_expenditures)}</td>
                <td className="py-1.5">{compact(year.fcff)}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
