import { ArrowUpRight01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import type { AssumptionReview } from "@/lib/api"
import { pct } from "@/lib/format"

const STANCE_STYLES: Record<AssumptionReview["stance"], string> = {
  challenged:
    "border-amber-500/50 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  supported:
    "border-emerald-500/50 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  context_only: "border-border bg-muted/40 text-muted-foreground",
}

export function StanceChip({ review }: { review: AssumptionReview }) {
  return (
    <span
      className={`rounded-full border px-1.5 py-0.5 text-[9px] uppercase tracking-wide ${STANCE_STYLES[review.stance]}`}
    >
      {review.stance.replace("_", " ")}
    </span>
  )
}

export function GrowthEvidenceContent({
  review,
  ticker,
  onApply,
}: {
  review: AssumptionReview
  ticker: string
  onApply: (percent: number) => void
}) {
  const range = review.suggested_range
  const low = range?.[0] ?? null
  const high = range?.[1] ?? null
  const midpoint = low !== null && high !== null ? (low + high) / 2 : null
  const applyPercent =
    midpoint === null ? null : Math.round(midpoint * 1000) / 10

  return (
    <div className="space-y-2">
      {review.rationale ? (
        <p className="text-xs text-muted-foreground">{review.rationale}</p>
      ) : null}

      <div className="space-y-1.5">
        {review.evidence.map((item) => (
          <div
            key={item.claim_id}
            className="rounded-md border border-border/60 bg-background/60 p-2"
          >
            <p className="text-xs">{item.statement}</p>
            {item.quote ? (
              <blockquote className="mt-1 border-l-2 border-border/60 pl-2 text-[11px] italic text-muted-foreground">
                “{item.quote}”
              </blockquote>
            ) : null}
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              {item.section ? (
                <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">
                  {item.section}
                </span>
              ) : null}
              <a
                href={`/filing?ticker=${encodeURIComponent(ticker)}&claim=${encodeURIComponent(item.claim_id)}`}
                className="inline-flex items-center gap-1 text-[10px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
              >
                view in filing
                <HugeiconsIcon
                  icon={ArrowUpRight01Icon}
                  strokeWidth={2}
                  className="size-3"
                />
              </a>
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-border/60 pt-2 text-[11px] text-muted-foreground">
        <span>
          Engine {pct(review.engine_value)} ·{" "}
          {review.engine_source.replaceAll("_", " ")}
        </span>
        {low === null && review.lean && review.lean !== "neutral" ? (
          <span
            className={
              review.lean === "higher"
                ? "text-emerald-700 dark:text-emerald-400"
                : "text-amber-700 dark:text-amber-400"
            }
          >
            language leans {review.lean}
          </span>
        ) : null}
        {low !== null && high !== null ? (
          <span>
            filing suggests {pct(low)}–{pct(high)}
          </span>
        ) : null}
        {applyPercent !== null ? (
          <button
            type="button"
            onClick={() => onApply(applyPercent)}
            className="ml-auto rounded-md border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] font-medium transition-colors hover:bg-primary/20"
          >
            Apply {applyPercent.toFixed(1)}%
          </button>
        ) : null}
      </div>
    </div>
  )
}
