import {
  Cancel01Icon,
  CheckmarkCircle02Icon,
} from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import { useChatPanel, type ProposalEntry } from "@/components/chat/ChatPanel"
import type { ProposalChange } from "@/lib/chat"

const PERCENT_KEYS = new Set(["growth", "tax", "capex", "wacc", "terminal"])

export function confidenceClasses(confidence: number): string {
  if (confidence >= 0.9) return "border-emerald-500/50 bg-emerald-500/10"
  if (confidence >= 0.8) return "border-yellow-500/50 bg-yellow-500/10"
  if (confidence >= 0.7) return "border-orange-500/50 bg-orange-500/10"
  return "border-red-500/50 bg-red-500/10"
}

export function formatChangeValue(
  key: string,
  value: number | string | null,
): string {
  if (value === null || value === undefined) return "—"
  if (typeof value === "string") return value
  if (PERCENT_KEYS.has(key)) return `${value.toFixed(1)}%`
  if (key === "years") return `${Math.round(value)}y`
  if (key === "shares") return `${Math.round(value)}M`
  return String(value)
}

function ChangeRow({ change }: { change: ProposalChange }) {
  return (
    <div className="flex items-baseline gap-1.5 text-[11px]">
      <span className="text-muted-foreground">{change.label}</span>
      <span className="tabular-nums text-muted-foreground">
        {formatChangeValue(change.key, change.before)}
      </span>
      <span className="text-muted-foreground">→</span>
      <span className="font-medium tabular-nums">
        {formatChangeValue(change.key, change.after)}
      </span>
    </div>
  )
}

export function ProposalCard({ entry }: { entry: ProposalEntry }) {
  const { apply, discard } = useChatPanel()
  const { proposal, status } = entry
  const tint = confidenceClasses(proposal.confidence)

  return (
    <div className={`mt-2 rounded-lg border p-2.5 ${tint}`}>
      <div className="flex items-start gap-2">
        <p className="min-w-0 flex-1 text-xs font-medium">{proposal.title}</p>
        <span className="shrink-0 rounded-full border border-current/30 px-1.5 py-0.5 text-[9px] uppercase tracking-wide">
          {Math.round(proposal.confidence * 100)}%
        </span>
        {status !== "pending" ? (
          <span className="shrink-0 text-[9px] uppercase tracking-wide text-muted-foreground">
            {status}
          </span>
        ) : null}
      </div>

      <div className="mt-1.5 space-y-0.5">
        {proposal.changes.map((change) => (
          <ChangeRow key={change.key} change={change} />
        ))}
      </div>

      {proposal.impact ? (
        <p className="mt-1.5 text-[11px] text-muted-foreground">
          Value / share{" "}
          <span className="tabular-nums">
            ${proposal.impact.value_before.toFixed(2)} → $
            {proposal.impact.value_after.toFixed(2)}
          </span>
        </p>
      ) : null}

      {proposal.rationale ? (
        <p className="mt-1 text-[11px] text-muted-foreground">
          {proposal.rationale}
        </p>
      ) : null}

      {proposal.evidence.length > 0 ? (
        <ul className="mt-1 space-y-0.5">
          {proposal.evidence.slice(0, 3).map((item, index) => (
            <li key={`${item.ref}-${index}`} className="text-[10px] text-muted-foreground">
              {item.quote ? `“${item.quote}”` : item.label}
              {item.ref ? (
                <span className="ml-1 font-mono text-[9px] opacity-70">
                  {item.ref}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {status === "pending" ? (
        <div className="mt-2 flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => apply(entry)}
            className="inline-flex items-center gap-1 rounded-md border border-emerald-600/50 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-700 transition-colors hover:bg-emerald-500/20 dark:text-emerald-300"
          >
            <HugeiconsIcon icon={CheckmarkCircle02Icon} strokeWidth={2} className="size-3" />
            Apply
          </button>
          <button
            type="button"
            onClick={() => discard(entry)}
            className="inline-flex items-center gap-1 rounded-md border border-red-500/40 px-2 py-0.5 text-[10px] text-red-600 transition-colors hover:bg-red-500/10 dark:text-red-400"
          >
            <HugeiconsIcon icon={Cancel01Icon} strokeWidth={2} className="size-3" />
            Discard
          </button>
        </div>
      ) : null}
    </div>
  )
}

export function ProposalQueue() {
  const {
    pending,
    active,
    activeIndex,
    setActiveIndex,
    apply,
    discard,
    undo,
    redo,
    canUndo,
    canRedo,
  } = useChatPanel()

  if (pending.length === 0 && !canUndo && !canRedo) return null

  return (
    <div className="mb-2 flex w-full items-center gap-1.5 rounded-md border border-border/60 bg-muted/30 px-2 py-1 text-[10px]">
      {active ? (
        <>
          <button
            type="button"
            onClick={() => setActiveIndex(Math.max(0, activeIndex - 1))}
            disabled={activeIndex <= 0}
            aria-label="Previous proposal"
            className="rounded px-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30"
          >
            ◀
          </button>
          <span className="min-w-0 flex-1 truncate">
            {active.proposal.title}{" "}
            <span className="text-muted-foreground">
              {activeIndex + 1}/{pending.length} ·{" "}
              {Math.round(active.proposal.confidence * 100)}%
            </span>
          </span>
          <button
            type="button"
            onClick={() =>
              setActiveIndex(Math.min(pending.length - 1, activeIndex + 1))
            }
            disabled={activeIndex >= pending.length - 1}
            aria-label="Next proposal"
            className="rounded px-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30"
          >
            ▶
          </button>
          <button
            type="button"
            onClick={() => apply(active)}
            aria-label="Apply proposal"
            className="rounded border border-emerald-600/40 px-1 text-emerald-700 hover:bg-emerald-500/10 dark:text-emerald-300"
          >
            ✓
          </button>
          <button
            type="button"
            onClick={() => discard(active)}
            aria-label="Discard proposal"
            className="rounded border border-red-500/40 px-1 text-red-600 hover:bg-red-500/10 dark:text-red-400"
          >
            ✗
          </button>
        </>
      ) : null}

      <span className="ml-auto flex items-center gap-1">
        <button
          type="button"
          onClick={undo}
          disabled={!canUndo}
          className="rounded border border-border px-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30"
        >
          Undo
        </button>
        <button
          type="button"
          onClick={redo}
          disabled={!canRedo}
          className="rounded border border-border px-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30"
        >
          Redo
        </button>
      </span>
    </div>
  )
}
