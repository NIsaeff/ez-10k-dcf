import { Badge } from "@/components/ui/badge"
import type { WaccBreakdown } from "@/lib/api"
import { compact, pct } from "@/lib/format"

function sourceTone(source: string): string {
  if (source.startsWith("sec:")) return "border-emerald-500/40 text-emerald-600 dark:text-emerald-400"
  if (source.startsWith("yahoo:")) return "border-sky-500/40 text-sky-600 dark:text-sky-400"
  if (source.startsWith("computed:")) return "border-border text-muted-foreground"
  if (source.startsWith("assumption:")) return "border-amber-500/40 text-amber-600 dark:text-amber-400"
  return "border-border text-muted-foreground"
}

function rate(value: number | null): string {
  return value === null ? "—" : pct(value, 2)
}

export function WaccPanel({
  wacc,
  onApply,
}: {
  wacc: WaccBreakdown | null
  onApply: (percent: number) => void
}) {
  if (!wacc) {
    return (
      <p className="text-sm text-muted-foreground">
        Market inputs unavailable for this ticker.
      </p>
    )
  }

  const appliedPercent = Math.round(wacc.wacc * 1000) / 10

  return (
    <div className="space-y-4">
      <section className="rounded-xl border bg-card p-4 text-card-foreground shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">CAPM cost of capital</h2>
            <p className="text-xs text-muted-foreground">
              rf + beta × ERP, weighted by market cap and book debt
              {wacc.as_of ? ` · market data ${wacc.as_of}` : ""}
            </p>
          </div>
          <div className="text-right">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
              WACC
            </p>
            <p className="text-2xl font-semibold tabular-nums">{pct(wacc.wacc, 2)}</p>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            { label: "Cost of equity", value: rate(wacc.cost_of_equity) },
            { label: "Cost of debt (after tax)", value: rate(wacc.cost_of_debt) },
            {
              label: "Equity weight",
              value: wacc.weight_equity === null ? "—" : pct(wacc.weight_equity, 1),
            },
            {
              label: "Market cap",
              value: wacc.market_cap === null ? "—" : compact(wacc.market_cap),
            },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-lg border border-border/60 bg-muted/30 p-2.5"
            >
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                {item.label}
              </p>
              <p className="mt-0.5 text-sm font-semibold tabular-nums">
                {item.value}
              </p>
            </div>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => onApply(appliedPercent)}
            className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 text-xs font-medium transition-colors hover:bg-primary/20"
          >
            Use {appliedPercent.toFixed(1)}% as the DCF WACC
          </button>
          {wacc.price !== null ? (
            <span className="text-[10px] text-muted-foreground">
              price ${wacc.price.toFixed(2)}
            </span>
          ) : null}
        </div>
      </section>

      <section className="rounded-xl border bg-card p-4 text-card-foreground shadow-sm">
        <h2 className="text-sm font-semibold">Where every input comes from</h2>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[34rem] text-left text-xs">
            <thead className="text-muted-foreground">
              <tr className="border-b">
                <th className="py-1.5 pr-3 font-medium">Input</th>
                <th className="py-1.5 pr-3 text-right font-medium">Value</th>
                <th className="py-1.5 font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {wacc.inputs.map((input) => (
                <tr key={input.key} className="border-b border-border/40">
                  <td className="py-1.5 pr-3">{input.label}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">
                    {input.key.includes("weight")
                      ? input.value === null
                        ? "—"
                        : pct(input.value, 1)
                      : input.key === "market_cap"
                        ? input.value === null
                          ? "—"
                          : compact(input.value)
                        : input.key === "beta"
                          ? (input.value?.toFixed(3) ?? "—")
                          : rate(input.value)}
                  </td>
                  <td className="py-1.5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Badge
                        variant="outline"
                        className={`font-mono text-[10px] ${sourceTone(input.source)}`}
                      >
                        {input.source}
                      </Badge>
                      {input.detail ? (
                        <span className="text-[10px] text-muted-foreground">
                          {input.detail}
                        </span>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {wacc.flags.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {wacc.flags.map((flag) => (
              <span
                key={flag}
                className="rounded-full border border-border/60 bg-muted/40 px-1.5 py-0.5 text-[10px] text-muted-foreground"
              >
                {flag}
              </span>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  )
}
