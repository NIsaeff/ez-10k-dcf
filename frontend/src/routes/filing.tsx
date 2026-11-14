import { UnfoldLessIcon, UnfoldMoreIcon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useState } from "react"

import { ClaimTree } from "@/components/filing/ClaimTree"
import { FilingFrame } from "@/components/filing/FilingFrame"
import { ModeToggle } from "@/components/mode-toggle"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { TickerSearch } from "@/components/wizard/TickerSearch"
import { fetchFiling, type FilingAnalysis, type FilingClaim } from "@/lib/api"
import { normalizeTicker } from "@/lib/wizard-state"

export const Route = createFileRoute("/filing")({
  validateSearch: (search: Record<string, unknown>) => ({
    ticker: normalizeTicker(search.ticker),
  }),
  component: FilingPage,
})

function FilingPage() {
  const { ticker } = Route.useSearch()
  const navigate = Route.useNavigate()

  const [data, setData] = useState<FilingAnalysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [active, setActive] = useState<FilingClaim | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [overrides, setOverrides] = useState<Record<string, string>>({})
  const [expandSignal, setExpandSignal] = useState(0)
  const [collapseSignal, setCollapseSignal] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setData(null)
    setActive(null)
    setElapsed(0)

    const startedAt = Date.now()
    const timer = setInterval(() => {
      if (!cancelled) setElapsed(Math.round((Date.now() - startedAt) / 1000))
    }, 1000)

    fetchFiling(ticker)
      .then((response) => {
        if (!cancelled) setData(response)
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : String(cause))
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
          clearInterval(timer)
        }
      })

    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [ticker])

  useEffect(() => {
    if (!data) {
      setOverrides({})
      return
    }
    setExpandSignal(0)
    setCollapseSignal(0)
    try {
      const stored = localStorage.getItem(`ez10k-claim-overrides:${data.accession}`)
      setOverrides(
        stored ? (JSON.parse(stored) as Record<string, string>) : {},
      )
    } catch {
      setOverrides({})
    }
  }, [data])

  useEffect(() => {
    if (!active || active.block === null) return
    document
      .getElementById(`block-${active.block}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" })
  }, [active])

  const persistOverrides = (next: Record<string, string>) => {
    if (data) {
      localStorage.setItem(
        `ez10k-claim-overrides:${data.accession}`,
        JSON.stringify(next),
      )
    }
    setOverrides(next)
  }

  const saveOverride = (claim: FilingClaim, statement: string) => {
    persistOverrides({ ...overrides, [claim.id]: statement })
  }

  const resetOverride = (claim: FilingClaim) => {
    const next = { ...overrides }
    delete next[claim.id]
    persistOverrides(next)
  }

  const jumpToClaim = (claim: FilingClaim) => setActive(claim)
  const claims = data?.claims ?? []
  const childCount = claims.reduce((total, claim) => total + claim.children.length, 0)
  const verifiedCount = claims.reduce(
    (total, claim) =>
      total + claim.children.filter((child) => child.verified).length,
    0,
  )

  return (
    <>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger className="-ml-1" />
          <div className="min-w-0">
            <h1 className="text-lg font-semibold leading-tight">10-K Analysis</h1>
            <p className="truncate text-xs text-muted-foreground">
              {data
                ? `${data.company_name} · filed ${data.filed} · ${data.accession}`
                : "Claims extracted from the filing, with the source text"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <TickerSearch
            ticker={ticker}
            onSelect={(next) =>
              navigate({
                to: "/filing",
                search: { ticker: next },
                replace: true,
              })
            }
          />
          <ModeToggle />
        </div>
      </header>

      {loading ? (
        <div className="border-b bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
          Reading {ticker}&rsquo;s 10-K and extracting claims… {elapsed}s
          {elapsed < 25 ? " (first run takes about a minute)" : ""}
        </div>
      ) : null}

      {error ? (
        <div className="m-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm">
          <p className="font-medium">Could not analyse {ticker}</p>
          <p className="text-xs text-muted-foreground">{error}</p>
        </div>
      ) : null}

      {data ? (
        <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
          <section className="min-h-0 overflow-y-auto border-b p-4 lg:border-b-0 lg:border-r">
            <div className="mb-3 flex flex-wrap items-baseline gap-2">
              <h2 className="text-sm font-semibold">Claims</h2>
              <span className="text-[11px] text-muted-foreground">
                {claims.length} themes · {childCount} supporting statements ·{" "}
                {verifiedCount} quoted verbatim
                {Object.keys(overrides).length > 0
                  ? ` · ${Object.keys(overrides).length} edited`
                  : ""}
              </span>
              {data.cached ? (
                <span className="rounded-full border border-border/60 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-muted-foreground">
                  cached
                </span>
              ) : null}
            </div>

            <div className="mb-3 flex flex-wrap items-center gap-1.5">
              {data.flags.map((flag) => (
                <span
                  key={flag}
                  className="rounded-full border border-border/60 bg-muted/40 px-1.5 py-0.5 text-[9px] text-muted-foreground"
                >
                  {flag}
                </span>
              ))}
              <div className="ml-auto flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setCollapseSignal((value) => value + 1)}
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <HugeiconsIcon icon={UnfoldLessIcon} strokeWidth={2} className="size-3" />
                  Collapse all
                </button>
                <button
                  type="button"
                  onClick={() => setExpandSignal((value) => value + 1)}
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <HugeiconsIcon icon={UnfoldMoreIcon} strokeWidth={2} className="size-3" />
                  Expand all
                </button>
              </div>
            </div>

            <ClaimTree
              claims={claims}
              activeId={active?.id ?? null}
              overrides={overrides}
              expandSignal={expandSignal}
              collapseSignal={collapseSignal}
              onJump={jumpToClaim}
              onSave={saveOverride}
              onReset={resetOverride}
            />
          </section>

          <section className="min-h-0 overflow-y-auto p-4">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-sm font-semibold">Source document</h2>
              <a
                href={data.document_url}
                target="_blank"
                rel="noreferrer"
                className="text-[11px] underline underline-offset-2 hover:text-foreground"
              >
                open on SEC
              </a>
            </div>

            <div className="h-[calc(100vh-15rem)] min-h-0">
              <FilingFrame
                src={data.document_view_url}
                sections={data.sections}
                active={active}
              />
            </div>
          </section>
        </div>
      ) : null}
    </>
  )
}
