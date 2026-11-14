import { useState } from "react"

import { ArrowUpRight01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import { useChatPanel } from "@/components/chat/ChatPanel"
import {
  confidenceClasses,
  formatChangeValue,
} from "@/components/chat/ProposalCard"
import { BreakdownChain } from "@/components/valuation/BreakdownChain"
import { MetricGrid } from "@/components/valuation/MetricGrid"
import {
  GrowthEvidenceContent,
  StanceChip,
} from "@/components/wizard/GrowthEvidence"
import { SensitivityGrid } from "@/components/wizard/SensitivityGrid"
import { Modal } from "@/components/ui/modal"
import { Slider } from "@/components/ui/slider"
import { Input } from "@/components/ui/input"
import type { AssumptionReview, SensitivityGrid as Grid } from "@/lib/api"
import type { ProposalChange } from "@/lib/chat"
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
  change,
  onApply,
  onDiscard,
  children,
}: {
  label: string
  value: string
  change?: ProposalChange | null
  onApply?: () => void
  onDiscard?: () => void
  children: React.ReactNode
}) {
  return (
    <div
      className={
        change
          ? `rounded-lg border p-2.5 ${confidenceClasses(change.confidence)}`
          : "space-y-1.5"
      }
    >
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="text-xs font-medium tabular-nums">{value}</span>
      </div>
      {children}
      {change && onApply && onDiscard ? (
        <ChangeFooter change={change} onApply={onApply} onDiscard={onDiscard} />
      ) : null}
    </div>
  )
}

function ChangeFooter({
  change,
  onApply,
  onDiscard,
}: {
  change: ProposalChange
  onApply: () => void
  onDiscard: () => void
}) {
  return (
    <div className="mt-1 flex items-center gap-1.5 text-[10px]">
      <span className="tabular-nums text-muted-foreground">
        {formatChangeValue(change.key, change.before)} →{" "}
        <span className="font-medium text-foreground">
          {formatChangeValue(change.key, change.after)}
        </span>
      </span>
      <button
        type="button"
        onClick={onApply}
        aria-label="Apply proposed change"
        className="flex size-5 items-center justify-center rounded-md border border-emerald-600/50 bg-emerald-500/10 text-[11px] text-emerald-700 hover:bg-emerald-500/20 dark:text-emerald-300"
      >
        ✓
      </button>
      <button
        type="button"
        onClick={onDiscard}
        aria-label="Discard proposed change"
        className="flex size-5 items-center justify-center rounded-md border border-red-500/40 text-[11px] text-red-600 hover:bg-red-500/10 dark:text-red-400"
      >
        ✗
      </button>
    </div>
  )
}

function ProposedFrame({
  change,
  onApply,
  onDiscard,
  children,
}: {
  change: ProposalChange | null
  onApply: () => void
  onDiscard: () => void
  children: React.ReactNode
}) {
  if (!change) return <>{children}</>
  return (
    <div className={`rounded-lg border p-2.5 ${confidenceClasses(change.confidence)}`}>
      {children}
      <ChangeFooter
        change={change}
        onApply={onApply}
        onDiscard={onDiscard}
      />
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
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const { active: activeProposal, apply: applyProposal, discard: discardProposal } =
    useChatPanel()
  const changeFor = (key: string) =>
    activeProposal?.proposal.changes.find((change) => change.key === key) ?? null
  const growthChange = changeFor("growth")
  const applyActive = () => {
    if (activeProposal) applyProposal(activeProposal)
  }
  const discardActive = () => {
    if (activeProposal) discardProposal(activeProposal)
  }
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
          <Control
            label="Projection years"
            value={`${search.years}`}
            change={changeFor("years")}
            onApply={applyActive}
            onDiscard={discardActive}
          >
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
            change={changeFor("terminal")}
            onApply={applyActive}
            onDiscard={discardActive}
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
            change={changeFor("model")}
            onApply={applyActive}
            onDiscard={discardActive}
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

          <Control
            label="WACC (override)"
            value={pct(assumptions.wacc)}
            change={changeFor("wacc")}
            onApply={applyActive}
            onDiscard={discardActive}
          >
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

          <div
            role={growthReview ? "button" : undefined}
            tabIndex={growthReview ? 0 : undefined}
            aria-label={
              growthReview ? "What the filing says about growth" : undefined
            }
            onClick={() => growthReview && setEvidenceOpen(true)}
            onKeyDown={(event) => {
              if (!growthReview) return
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault()
                setEvidenceOpen(true)
              }
            }}
            className={`group relative rounded-lg border p-2.5 transition-colors ${
              growthChange
                ? confidenceClasses(growthChange.confidence)
                : "border-border/60 bg-muted/20"
            } ${
              growthReview
                ? "cursor-pointer hover:border-primary/40 hover:bg-muted/40 focus-visible:border-primary/50 focus-visible:outline-none"
                : ""
            }`}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-xs text-muted-foreground">
                Growth (year 1)
              </span>
              <span className="flex items-center gap-1.5">
                {growthReview ? <StanceChip review={growthReview} /> : null}
                <span className="text-xs font-medium tabular-nums">
                  {pct((search.growth ?? assumptions.growth_rate * 100) / 100)}
                </span>
              </span>
            </div>

            <div
              className="mt-2 flex items-center gap-2"
              onClick={(event) => event.stopPropagation()}
              onKeyDown={(event) => event.stopPropagation()}
            >
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

            {growthChange ? (
              <div
                onClick={(event) => event.stopPropagation()}
                className="mt-1"
              >
                <ChangeFooter
                  change={growthChange}
                  onApply={() => activeProposal && applyProposal(activeProposal)}
                  onDiscard={() =>
                    activeProposal && discardProposal(activeProposal)
                  }
                />
              </div>
            ) : null}

            {growthReview ? (
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation()
                  setEvidenceOpen(true)
                }}
                className="mt-1.5 inline-flex items-center gap-1 pr-8 text-[10px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
              >
                What the filing says · {growthReview.evidence.length} claims
              </button>
            ) : null}


            {growthReview ? (
              <span
                aria-hidden
                className="absolute bottom-2 right-2 flex size-5 items-center justify-center rounded-md border border-border/60 bg-background text-muted-foreground transition-colors group-hover:border-primary/50 group-hover:text-foreground"
              >
                <HugeiconsIcon
                  icon={ArrowUpRight01Icon}
                  strokeWidth={2}
                  className="size-3"
                />
              </span>
            ) : null}
          </div>

          <Control
            label="Tax rate"
            value={pct((search.tax ?? assumptions.tax_rate * 100) / 100)}
            change={changeFor("tax")}
            onApply={applyActive}
            onDiscard={discardActive}
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
            change={changeFor("capex")}
            onApply={applyActive}
            onDiscard={discardActive}
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
            change={changeFor("shares")}
            onApply={applyActive}
            onDiscard={discardActive}
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

      {growthReview ? (
        <Modal
          open={evidenceOpen}
          onClose={() => setEvidenceOpen(false)}
          title="What the filing says about growth"
          subtitle={`${valuation.ticker} · engine ${pct(assumptions.growth_rate)} · ${assumptions.growth_source.replaceAll("_", " ")}`}
        >
          <GrowthEvidenceContent
            review={growthReview}
            ticker={valuation.ticker}
            onApply={(percent) => {
              onChange({ growth: percent })
              setEvidenceOpen(false)
            }}
          />
        </Modal>
      ) : null}
    </div>
  )
}
