import { BreakdownChain } from "@/components/valuation/BreakdownChain"
import { MetricGrid } from "@/components/valuation/MetricGrid"
import { GrowthEvidence } from "@/components/wizard/GrowthEvidence"
import { SensitivityGrid } from "@/components/wizard/SensitivityGrid"
import { Slider } from "@/components/ui/slider"
import { Input } from "@/components/ui/input"
import type { AssumptionReview, SensitivityGrid as Grid } from "@/lib/api"
import type { ValuationResult } from "@/lib/chat"
import { buildBreakdownLines } from "@/lib/derivation"
import { compact, pct, perShare } from "@/lib/format"
import type { WizardSearch } from "@/lib/wizard-state"

function ResetButton({
  onClick,
  disabled,
}: {
  onClick: () => void
  disabled: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="shrink-0 rounded-md border border-border px-2 py-1 text-[10px] text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40"
    >
      default
    </button>
  )
}

function Control({
  label,
  value,
  children,
}: {
  label: string
  value: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="text-xs font-medium tabular-nums">{value}</span>
      </div>
      {children}
    </div>
  )
}

export function DcfPanel({
  valuation,
  search,
  onChange,
  grid,
  pending,
  growthReview,
}: {
  valuation: ValuationResult
  search: WizardSearch
  onChange: (patch: Partial<WizardSearch>) => void
  grid: Grid | null
  pending: boolean
  growthReview: AssumptionReview | null
}) {
  const summary = valuation.valuation
  const assumptions = valuation.assumptions
  const pvFcff = valuation.projection.reduce(
    (total, year) => total + year.present_value,
    0,
  )
  const terminalShare =
    summary.enterprise_value === 0
      ? null
      : summary.present_value_terminal / summary.enterprise_value

  const defaultWacc = valuation.engine?.base_wacc ?? null
  const latestYear = valuation.history[valuation.history.length - 1]
  const filingCapexRate =
    latestYear && latestYear.revenue
      ? latestYear.capital_expenditures / latestYear.revenue
      : null

  return (
    <div className="space-y-4">
      <section className="rounded-xl border bg-card p-4 text-card-foreground shadow-sm">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold">Assumptions</h2>
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {pending ? "recalculating…" : "up to date"}
          </span>
        </div>

        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <Control label="Projection years" value={`${search.years}`}>
            <Slider
              min={3}
              max={10}
              step={1}
              value={[search.years]}
              onValueChange={(next) => {
                const raw = Array.isArray(next) ? next[0] : next
                if (typeof raw === "number") {
                  onChange({ years: Math.round(raw) })
                }
              }}
            />
          </Control>

          <Control
            label="Terminal growth"
            value={pct(assumptions.terminal_growth_rate)}
          >
            <Slider
              min={1}
              max={5}
              step={0.1}
              value={[search.terminal]}
              onValueChange={(next) => {
                const raw = Array.isArray(next) ? next[0] : next
                if (typeof raw === "number") {
                  onChange({ terminal: Math.round(raw * 10) / 10 })
                }
              }}
            />
          </Control>

          <Control
            label="Growth model"
            value={search.model === "fade" ? "fade to terminal" : "constant"}
          >
            <div className="flex gap-1.5">
              {(["fade", "constant"] as const).map((model) => (
                <button
                  key={model}
                  type="button"
                  onClick={() => onChange({ model })}
                  className={`flex-1 rounded-md border px-2 py-1 text-xs transition-colors ${
                    search.model === model
                      ? "border-primary bg-primary/10 font-medium text-foreground"
                      : "border-border text-muted-foreground hover:bg-muted"
                  }`}
                >
                  {model}
                </button>
              ))}
            </div>
          </Control>

          <Control label="WACC (override)" value={pct(assumptions.wacc)}>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={1}
                max={30}
                step={0.1}
                placeholder={defaultWacc === null ? "default" : pct(defaultWacc)}
                value={search.wacc ?? ""}
                onChange={(event) => {
                  const raw = event.target.value
                  onChange({
                    wacc: raw === "" ? undefined : Number(raw),
                  })
                }}
                className="h-8"
              />
              <button
                type="button"
                onClick={() => onChange({ wacc: undefined })}
                disabled={search.wacc === undefined}
                className="shrink-0 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40"
              >
                default
              </button>
            </div>
          </Control>

          <Control
            label="Growth (year 1)"
            value={pct((search.growth ?? assumptions.growth_rate * 100) / 100)}
          >
            <div className="flex items-center gap-2">
              <div className="min-w-0 flex-1">
                <Slider
                  min={0}
                  max={25}
                  step={0.1}
                  value={[search.growth ?? Math.round(assumptions.growth_rate * 1000) / 10]}
                  onValueChange={(next) => {
                    const raw = Array.isArray(next) ? next[0] : next
                    if (typeof raw === "number") {
                      onChange({ growth: Math.round(raw * 10) / 10 })
                    }
                  }}
                />
              </div>
              <ResetButton
                onClick={() => onChange({ growth: undefined })}
                disabled={search.growth === undefined}
              />
            </div>
          </Control>

          <Control
            label="Tax rate"
            value={pct((search.tax ?? assumptions.tax_rate * 100) / 100)}
          >
            <div className="flex items-center gap-2">
              <div className="min-w-0 flex-1">
                <Slider
                  min={0}
                  max={40}
                  step={0.5}
                  value={[search.tax ?? Math.round(assumptions.tax_rate * 1000) / 10]}
                  onValueChange={(next) => {
                    const raw = Array.isArray(next) ? next[0] : next
                    if (typeof raw === "number") {
                      onChange({ tax: Math.round(raw * 10) / 10 })
                    }
                  }}
                />
              </div>
              <ResetButton
                onClick={() => onChange({ tax: undefined })}
                disabled={search.tax === undefined}
              />
            </div>
          </Control>

          <Control
            label="CapEx (% of revenue)"
            value={
              filingCapexRate === null
                ? "n/a"
                : pct((search.capex ?? filingCapexRate * 100) / 100)
            }
          >
            <div className="flex items-center gap-2">
              <div className="min-w-0 flex-1">
                <Slider
                  min={0}
                  max={30}
                  step={0.5}
                  disabled={filingCapexRate === null}
                  value={[search.capex ?? Math.round(filingCapexRate! * 1000) / 10]}
                  onValueChange={(next) => {
                    const raw = Array.isArray(next) ? next[0] : next
                    if (typeof raw === "number") {
                      onChange({ capex: Math.round(raw * 10) / 10 })
                    }
                  }}
                />
              </div>
              <ResetButton
                onClick={() => onChange({ capex: undefined })}
                disabled={search.capex === undefined}
              />
            </div>
          </Control>

          <Control
            label="Shares outstanding (M)"
            value={
              (
                (search.shares ?? (valuation.engine?.shares_outstanding ?? 0) / 1_000_000) /
                1
              ).toFixed(1)
            }
          >
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={1}
                step={1}
                placeholder="engine"
                value={search.shares ?? ""}
                onChange={(event) => {
                  const raw = event.target.value
                  onChange({
                    shares: raw === "" ? undefined : Number(raw),
                  })
                }}
                className="h-8"
              />
              <ResetButton
                onClick={() => onChange({ shares: undefined })}
                disabled={search.shares === undefined}
              />
            </div>
          </Control>
        </div>

        {growthReview ? (
          <GrowthEvidence
            review={growthReview}
            ticker={valuation.ticker}
            onApply={(percent) => onChange({ growth: percent })}
          />
        ) : null}
      </section>

      <section className="rounded-xl border bg-card p-4 text-card-foreground shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Valuation</h2>
            <p className="text-xs text-muted-foreground">
              {valuation.ticker} · FY{valuation.history.at(-1)?.fiscal_year} ·
              growth {pct(assumptions.growth_rate)} ({assumptions.growth_model})
            </p>
          </div>
          <div className="text-right">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Value per share
            </p>
            <p className="text-2xl font-semibold tabular-nums">
              {perShare(summary.value_per_share)}
            </p>
          </div>
        </div>

        <div className="mt-3">
          <MetricGrid
            items={[
              {
                label: "PV of FCFF",
                value: compact(pvFcff),
                hint: `${valuation.projection.length}y`,
              },
              {
                label: "PV of terminal value",
                value: compact(summary.present_value_terminal),
                hint:
                  terminalShare === null
                    ? undefined
                    : `${pct(terminalShare)} of EV`,
              },
              { label: "Enterprise value", value: compact(summary.enterprise_value) },
              { label: "Equity value", value: compact(summary.equity_value) },
              { label: "Net debt", value: compact(summary.net_debt) },
              { label: "Effective WACC", value: pct(assumptions.wacc) },
              { label: "Terminal value", value: compact(summary.terminal_value) },
              {
                label: "Share count",
                value: compact(summary.shares_outstanding),
                hint: assumptions.share_count_source,
              },
            ]}
          />
        </div>

        <div className="mt-3">
          <BreakdownChain lines={buildBreakdownLines(valuation)} />
        </div>
      </section>

      <section className="rounded-xl border bg-card p-4 text-card-foreground shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold">Sensitivity</h2>
          <p className="text-xs text-muted-foreground">
            ±2% WACC · ±1% terminal growth · net debt applied
          </p>
        </div>
        <div className="mt-3">
          {grid ? (
            <SensitivityGrid
              grid={grid}
              currentWacc={assumptions.wacc}
              currentTerminal={assumptions.terminal_growth_rate}
            />
          ) : (
            <p className="text-xs text-muted-foreground">No grid yet.</p>
          )}
        </div>
      </section>
    </div>
  )
}
