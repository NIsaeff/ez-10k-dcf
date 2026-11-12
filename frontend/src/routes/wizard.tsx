import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useState } from "react"

import { ModeToggle } from "@/components/mode-toggle"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { FcffPanel } from "@/components/wizard/FcffPanel"
import { TickerBar } from "@/components/wizard/TickerBar"
import { analyzeTicker } from "@/lib/api"
import type { ValuationResult } from "@/lib/chat"
import { validateWizardSearch } from "@/lib/wizard-state"

export const Route = createFileRoute("/wizard")({
  validateSearch: validateWizardSearch,
  component: WizardPage,
})

function WizardPage() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()

  const [valuation, setValuation] = useState<ValuationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    analyzeTicker(search.ticker)
      .then((result) => {
        if (!cancelled) setValuation(result)
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        setValuation(null)
        setError(cause instanceof Error ? cause.message : String(cause))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [search.ticker])

  return (
    <>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger className="-ml-1" />
          <div className="min-w-0">
            <h1 className="text-lg font-semibold leading-tight">DCF Wizard</h1>
            <p className="truncate text-xs text-muted-foreground">
              {valuation
                ? `${valuation.company_name} · FY${valuation.history.at(-1)?.fiscal_year} 10-K · filed ${valuation.filing.filed}`
                : "Inspecting the latest 10-K"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <TickerBar
            ticker={search.ticker}
            disabled={loading}
            onChange={(ticker) =>
              navigate({
                to: "/wizard",
                search: (previous) => ({ ...previous, ticker }),
              })
            }
          />
          <ModeToggle />
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <div className="mx-auto w-full max-w-5xl">
          {error ? (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm">
              <p className="font-medium">Could not load {search.ticker}</p>
              <p className="text-xs text-muted-foreground">{error}</p>
            </div>
          ) : null}

          {loading ? (
            <p className="text-sm text-muted-foreground">
              Loading {search.ticker}…
            </p>
          ) : null}

          {valuation ? (
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
                <p className="text-sm text-muted-foreground">
                  CAPM decomposition lands in the next phase.
                </p>
              </TabsContent>

              <TabsContent value="dcf" className="mt-4">
                <p className="text-sm text-muted-foreground">
                  Assumption controls and the sensitivity grid land in the next
                  phase.
                </p>
              </TabsContent>
            </Tabs>
          ) : null}
        </div>
      </div>
    </>
  )
}
