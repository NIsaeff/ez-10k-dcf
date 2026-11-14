import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useMemo, useState } from "react"

import { ModeToggle } from "@/components/mode-toggle"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DcfPanel } from "@/components/wizard/DcfPanel"
import { FcffPanel } from "@/components/wizard/FcffPanel"
import { TickerSearch } from "@/components/wizard/TickerSearch"
import { WaccPanel } from "@/components/wizard/WaccPanel"
import {
  fetchSensitivity,
  fetchWacc,
  recalcDcf,
  type SensitivityGrid,
  type WaccBreakdown,
} from "@/lib/api"
import type { ValuationResult } from "@/lib/chat"
import { withPreview } from "@/lib/preview"
import { SUPPORTED_TICKERS } from "@/lib/tickers"
import {
  overridesFromSearch,
  validateWizardSearch,
  type WizardSearch,
} from "@/lib/wizard-state"

const DEBOUNCE_MS = 250

export const Route = createFileRoute("/wizard")({
  validateSearch: validateWizardSearch,
  component: WizardPage,
})

function WizardPage() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()

  const [valuation, setValuation] = useState<ValuationResult | null>(null)
  const [grid, setGrid] = useState<SensitivityGrid | null>(null)
  const [waccData, setWaccData] = useState<WaccBreakdown | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(true)

  const { ticker, years, terminal, model, wacc } = search

  useEffect(() => {
    let cancelled = false
    setPending(true)

    const overrides = overridesFromSearch({
      ticker,
      years,
      terminal,
      model,
      wacc,
    })

    const timer = setTimeout(() => {
      Promise.all([
        recalcDcf(ticker, overrides),
        fetchSensitivity(ticker, overrides),
      ])
        .then(([result, nextGrid]) => {
          if (cancelled) return
          setValuation(result)
          setGrid(nextGrid)
          setError(null)
        })
        .catch((cause: unknown) => {
          if (cancelled) return
          setValuation(null)
          setGrid(null)
          setError(cause instanceof Error ? cause.message : String(cause))
        })
        .finally(() => {
          if (!cancelled) setPending(false)
        })
    }, DEBOUNCE_MS)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [ticker, years, terminal, model, wacc])

  useEffect(() => {
    let cancelled = false
    setWaccData(null)
    fetchWacc(ticker)
      .then((data) => {
        if (!cancelled) setWaccData(data)
      })
      .catch(() => {
        if (!cancelled) setWaccData(null)
      })
    return () => {
      cancelled = true
    }
  }, [ticker])

  const previewed = useMemo(
    () => (valuation ? withPreview(valuation, search) : null),
    [valuation, search],
  )

  const update = (patch: Partial<WizardSearch>) =>
    navigate({
      to: "/wizard",
      search: (previous) => ({ ...previous, ...patch }),
      replace: true,
    })

  return (
    <>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger className="-ml-1" />
          <div className="min-w-0">
            <h1 className="text-lg font-semibold leading-tight">DCF Wizard</h1>
            <p className="truncate text-xs text-muted-foreground">
              Pick a company, then move the assumptions
            </p>
          </div>
        </div>
        <ModeToggle />
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <div className="mx-auto w-full max-w-5xl space-y-4">
          <section className="rounded-2xl border bg-card p-5 text-card-foreground shadow-sm">
            <h2 className="text-lg font-semibold">Value any US public company</h2>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              Search ~10,400 SEC filers by ticker or company name. Every number is
              derived from the company&rsquo;s latest 10-K — no market estimates.
            </p>

            <div className="mt-4 max-w-2xl">
              <TickerSearch
                ticker={ticker}
                size="lg"
                onSelect={(next) => update({ ticker: next })}
              />
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <span className="mr-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                Pilots
              </span>
              {SUPPORTED_TICKERS.map((pilot) => (
                <button
                  key={pilot}
                  type="button"
                  onClick={() => update({ ticker: pilot })}
                  className={`rounded-full border px-2.5 py-0.5 text-[11px] transition-colors ${
                    pilot === ticker
                      ? "border-primary bg-primary/10 font-medium text-foreground"
                      : "border-border/60 text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  {pilot}
                </button>
              ))}
            </div>

            {valuation ? (
              <div className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1 border-t border-border/60 pt-3 text-xs text-muted-foreground">
                <span className="text-sm font-semibold text-foreground">
                  {valuation.company_name}
                </span>
                <span>
                  FY{valuation.history.at(-1)?.fiscal_year} 10-K · filed{" "}
                  {valuation.filing.filed}
                </span>
                <a
                  href={valuation.filing.url}
                  target="_blank"
                  rel="noreferrer"
                  className="underline underline-offset-2 hover:text-foreground"
                >
                  source
                </a>
              </div>
            ) : null}
          </section>
          {error ? (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm">
              <p className="font-medium">Could not load {ticker}</p>
              <p className="text-xs text-muted-foreground">{error}</p>
            </div>
          ) : null}

          {!valuation && pending ? (
            <p className="text-sm text-muted-foreground">Loading {ticker}…</p>
          ) : null}

          {valuation && previewed ? (
            <Tabs defaultValue="fcff">
              <TabsList>
                <TabsTrigger value="fcff">FCFF</TabsTrigger>
                <TabsTrigger value="wacc">WACC</TabsTrigger>
                <TabsTrigger value="dcf">DCF</TabsTrigger>
              </TabsList>

              <TabsContent value="fcff" className="mt-4">
                <FcffPanel valuation={valuation} />
              </TabsContent>

              <TabsContent value="wacc" className="mt-4">
                <WaccPanel
                  wacc={waccData}
                  onApply={(percent) => update({ wacc: percent })}
                />
              </TabsContent>

              <TabsContent value="dcf" className="mt-4">
                <DcfPanel
                  valuation={previewed}
                  search={search}
                  onChange={update}
                  grid={grid}
                  pending={pending}
                />
              </TabsContent>
            </Tabs>
          ) : null}
        </div>
      </div>
    </>
  )
}
