import type { SourceFact, ValuationResult } from "@/lib/chat"

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

function shares(value: number): string {
  if (value >= 1e9) return `${(value / 1e9).toFixed(2)}B`
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`
  return value.toLocaleString()
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

const METRIC_LABELS: Record<string, string> = {
  revenue: "Revenue",
  ebit: "EBIT",
  pretax_income: "Pretax income",
  tax_expense: "Income tax expense",
  depreciation_amortization: "Depreciation & amortization",
  capital_expenditures: "Capital expenditures",
  current_assets: "Current assets",
  current_liabilities: "Current liabilities",
  cash: "Cash & equivalents",
  total_debt: "Total debt",
  shares_outstanding: "Shares outstanding",
}

type FactGroup = { metric: string; label: string; facts: SourceFact[] }

function groupFacts(facts: SourceFact[]): FactGroup[] {
  const order: string[] = []
  const byMetric = new Map<string, SourceFact[]>()
  for (const fact of facts) {
    if (!byMetric.has(fact.metric)) {
      byMetric.set(fact.metric, [])
      order.push(fact.metric)
    }
    byMetric.get(fact.metric)?.push(fact)
  }
  return order.map((metric) => ({
    metric,
    label: METRIC_LABELS[metric] ?? metric,
    facts: byMetric.get(metric) ?? [],
  }))
}

function FactValue({ fact }: { fact: SourceFact }) {
  return fact.unit === "shares" ? shares(fact.value) : compact(fact.value)
}

function Line({
  op,
  label,
  hint,
  value,
  emphasis,
}: {
  op: string
  label: string
  hint?: string
  value: string
  emphasis?: boolean
}) {
  return (
    <div className="flex items-baseline gap-2 py-1">
      <span className="w-3 shrink-0 text-muted-foreground">{op}</span>
      <span className={emphasis ? "font-semibold" : "text-muted-foreground"}>
        {label}
        {hint ? (
          <span className="ml-1 text-[10px] text-muted-foreground/80">({hint})</span>
        ) : null}
      </span>
      <span
        className={`ml-auto tabular-nums ${emphasis ? "font-semibold" : ""}`}
      >
        {value}
      </span>
    </div>
  )
}

export function ValuationCard({ valuation }: { valuation: ValuationResult }) {
  const summary = valuation.valuation
  const assumptions = valuation.assumptions
  const latest = valuation.history[valuation.history.length - 1]
  const facts = valuation.source_facts ?? []
  const groups = groupFacts(facts)
  const pvFcff = valuation.projection.reduce(
    (total, year) => total + year.present_value,
    0,
  )

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

      <div className="mt-4 rounded-lg border border-border/60 bg-muted/20 p-3">
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
          How this adds up
        </p>
        <div className="mt-1 text-xs">
          <Line
            op="+"
            label={`PV of FCFF (${valuation.projection.length}y)`}
            value={compact(pvFcff)}
          />
          <Line
            op="+"
            label="PV of terminal value"
            hint={`TV ${compact(summary.terminal_value)} @ ${pct(assumptions.terminal_growth_rate)}`}
            value={compact(summary.present_value_terminal)}
          />
          <Line
            op="="
            label="Enterprise value"
            value={compact(summary.enterprise_value)}
            emphasis
          />
          <Line
            op="−"
            label="Net debt"
            hint={`debt ${compact(summary.total_debt)} − cash ${compact(summary.cash_and_equivalents)}`}
            value={compact(summary.net_debt)}
          />
          <Line
            op="="
            label="Equity value"
            value={compact(summary.equity_value)}
            emphasis
          />
          <Line
            op="÷"
            label="Diluted shares"
            hint={assumptions.share_count_source}
            value={shares(summary.shares_outstanding)}
          />
          <div className="mt-1 border-t border-border/60 pt-1">
            <Line
              op="="
              label="Value per share"
              value={perShare(summary.value_per_share)}
              emphasis
            />
          </div>
        </div>
      </div>

      {groups.length > 0 ? (
        <div className="mt-3">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
            XBRL inputs ({facts.length} facts)
          </p>
          <div className="mt-1 divide-y divide-border/40 border-y border-border/40">
            {groups.map((group) => (
              <details key={group.metric} className="group">
                <summary className="flex cursor-pointer list-none items-center gap-2 py-1.5 text-xs hover:text-foreground">
                  <span className="w-3 shrink-0 text-muted-foreground transition-transform group-open:rotate-90">
                    ▸
                  </span>
                  <span className="shrink-0 font-medium">{group.label}</span>
                  <span className="min-w-0 flex-1 truncate font-mono text-[10px] text-muted-foreground">
                    {Array.from(new Set(group.facts.map((f) => f.tag))).join(", ")}
                  </span>
                  <span className="shrink-0 text-[10px] text-muted-foreground">
                    {group.facts.length}
                  </span>
                </summary>
                <div className="pb-2 pl-5">
                  <table className="w-full text-left text-[11px]">
                    <thead className="text-muted-foreground">
                      <tr>
                        <th className="py-0.5 pr-3 font-medium">FY</th>
                        <th className="py-0.5 pr-3 font-medium">Tag</th>
                        <th className="py-0.5 pr-3 font-medium">Value</th>
                        <th className="py-0.5 pr-3 font-medium">Filed / period</th>
                        <th className="py-0.5 font-medium">Source</th>
                      </tr>
                    </thead>
                    <tbody className="tabular-nums">
                      {group.facts.map((fact) => (
                        <tr
                          key={`${fact.metric}-${fact.tag}-${fact.fiscal_year}`}
                          className="border-t border-border/30"
                        >
                          <td className="py-0.5 pr-3">{fact.fiscal_year}</td>
                          <td className="max-w-[10rem] truncate py-0.5 pr-3 font-mono text-[10px] text-muted-foreground">
                            {fact.tag}
                          </td>
                          <td className="py-0.5 pr-3">
                            <FactValue fact={fact} />
                          </td>
                          <td className="py-0.5 pr-3 text-muted-foreground">
                            {fact.filed ?? "—"}
                            {fact.end ? ` · ${fact.end}` : ""}
                          </td>
                          <td className="py-0.5">
                            <a
                              href={fact.url}
                              target="_blank"
                              rel="noreferrer"
                              className="underline underline-offset-2 hover:text-foreground"
                            >
                              {fact.accession_number ?? "SEC filing"}
                            </a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            ))}
          </div>
        </div>
      ) : null}

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
