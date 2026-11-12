import type { ValuationResult } from "@/lib/chat"
import { compact, pct } from "@/lib/format"

import { FcffChart } from "@/components/wizard/FcffChart"

function Row({
  label,
  hint,
  value,
  emphasis,
}: {
  label: string
  hint?: string
  value: string
  emphasis?: boolean
}) {
  return (
    <div className="flex items-baseline gap-2 py-1 text-xs">
      <span className={emphasis ? "font-semibold" : "text-muted-foreground"}>
        {label}
        {hint ? (
          <span className="ml-1 text-[10px] text-muted-foreground/80">
            ({hint})
          </span>
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

export function FcffPanel({ valuation }: { valuation: ValuationResult }) {
  const latest = valuation.history[valuation.history.length - 1]
  const oldest = valuation.history[0]
  const assumptions = valuation.assumptions

  if (!latest || !oldest) {
    return (
      <p className="text-sm text-muted-foreground">
        No usable fiscal years in the latest filing.
      </p>
    )
  }
  const taxRate = assumptions.tax_rate
  const ebitAfterTax = latest.ebit * (1 - taxRate)
  const changeInNwc = latest.change_in_nwc ?? 0

  const years = valuation.history.length - 1
  const cagr =
    years > 0 && oldest.fcff > 0 && latest.fcff > 0
      ? (latest.fcff / oldest.fcff) ** (1 / years) - 1
      : null

  return (
    <div className="space-y-4">
      <section className="rounded-xl border bg-card p-4 text-card-foreground shadow-sm">
        <h2 className="text-sm font-semibold">FCFF history</h2>
        <p className="text-xs text-muted-foreground">
          Free cash flow to the firm, derived from the filing — not reported.
        </p>

        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[34rem] text-left text-xs">
            <thead className="text-muted-foreground">
              <tr className="border-b">
                <th className="py-1.5 pr-3 font-medium">FY</th>
                <th className="py-1.5 pr-3 font-medium">Revenue</th>
                <th className="py-1.5 pr-3 font-medium">EBIT</th>
                <th className="py-1.5 pr-3 font-medium">D&amp;A</th>
                <th className="py-1.5 pr-3 font-medium">CapEx</th>
                <th className="py-1.5 pr-3 font-medium">Δ NWC</th>
                <th className="py-1.5 font-medium">FCFF</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {valuation.history.map((year) => (
                <tr key={year.fiscal_year} className="border-b border-border/40">
                  <td className="py-1.5 pr-3">{year.fiscal_year}</td>
                  <td className="py-1.5 pr-3">
                    {year.revenue === null ? "—" : compact(year.revenue)}
                  </td>
                  <td className="py-1.5 pr-3">{compact(year.ebit)}</td>
                  <td className="py-1.5 pr-3">
                    {compact(year.depreciation_amortization)}
                  </td>
                  <td className="py-1.5 pr-3">
                    {compact(year.capital_expenditures)}
                  </td>
                  <td className="py-1.5 pr-3">
                    {year.change_in_nwc === null
                      ? "—"
                      : compact(year.change_in_nwc)}
                  </td>
                  <td className="py-1.5">{compact(year.fcff)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-3">
          <FcffChart
            history={valuation.history}
            projection={valuation.projection}
          />
          <p className="text-[10px] text-muted-foreground">
            Solid bars: reported fiscal years. Lighter bars: projection.
          </p>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2">
        <section className="rounded-xl border bg-card p-4 text-card-foreground shadow-sm">
          <h2 className="text-sm font-semibold">
            Composition · FY{latest.fiscal_year}
          </h2>
          <div className="mt-2">
            <Row
              label="EBIT × (1 − tax)"
              hint={`tax ${pct(taxRate)}`}
              value={compact(ebitAfterTax)}
            />
            <Row label="+ D&A" value={compact(latest.depreciation_amortization)} />
            <Row
              label="− CapEx"
              value={compact(latest.capital_expenditures)}
            />
            <Row
              label="− Δ NWC"
              hint={latest.change_in_nwc === null ? "unavailable, treated as 0" : undefined}
              value={compact(changeInNwc)}
            />
            <div className="mt-1 border-t border-border/60 pt-1">
              <Row label="= FCFF" value={compact(latest.fcff)} emphasis />
            </div>
          </div>
        </section>

        <section className="rounded-xl border bg-card p-4 text-card-foreground shadow-sm">
          <h2 className="text-sm font-semibold">Growth inputs</h2>
          <div className="mt-2">
            <Row
              label="FCFF CAGR"
              hint={`${oldest.fiscal_year}→${latest.fiscal_year}`}
              value={cagr === null ? "n/a" : pct(cagr)}
            />
            <Row
              label="FCFF base"
              hint={assumptions.fcff_base_source.replaceAll("_", " ")}
              value={compact(assumptions.fcff_base)}
            />
            <Row
              label="Growth used"
              hint={`${assumptions.growth_model} · ${assumptions.growth_source.replaceAll("_", " ")}`}
              value={pct(assumptions.growth_rate)}
            />
            <Row
              label="Terminal growth"
              value={pct(assumptions.terminal_growth_rate)}
            />
          </div>
        </section>
      </div>
    </div>
  )
}
