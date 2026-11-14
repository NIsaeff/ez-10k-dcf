import { ArrowUpRight01Icon, QuoteDownIcon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import type { FilingClaim } from "@/lib/api"

function KindBadge({ kind }: { kind: string | null }) {
  if (!kind) return null
  return (
    <span className="rounded-full border border-border/60 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-muted-foreground">
      {kind}
    </span>
  )
}

function SectionBadge({ section }: { section: string | null }) {
  if (!section) return null
  return (
    <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">
      {section}
    </span>
  )
}

function JumpLabel({ claim }: { claim: FilingClaim }) {
  if (claim.verified && claim.block !== null) {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground group-hover/claim:text-foreground">
        <span>jump to source</span>
        <HugeiconsIcon icon={ArrowUpRight01Icon} strokeWidth={2} className="size-3" />
      </span>
    )
  }
  return (
    <span className="text-[10px] text-amber-600 dark:text-amber-400">
      quote not found in document
    </span>
  )
}

function ClaimButton({
  claim,
  isActive,
  onJump,
}: {
  claim: FilingClaim
  isActive: boolean
  onJump: (claim: FilingClaim) => void
}) {
  const canJump = claim.verified && claim.block !== null

  return (
    <div
      className={`group/claim rounded-lg border px-2.5 py-2 transition-colors ${
        isActive
          ? "border-primary/60 bg-primary/10"
          : "border-border/60 bg-card hover:bg-muted/40"
      }`}
    >
      <button
        type="button"
        disabled={!canJump}
        onClick={() => canJump && onJump(claim)}
        className="block w-full text-left disabled:cursor-default"
      >
        <div className="flex items-start gap-2">
          <p className="min-w-0 flex-1 text-xs">{claim.statement}</p>
          <SectionBadge section={claim.section} />
        </div>
        {claim.quote ? (
          <blockquote className="mt-1.5 flex gap-1.5 border-l-2 border-border/60 pl-2 text-[11px] italic text-muted-foreground">
            <HugeiconsIcon
              icon={QuoteDownIcon}
              strokeWidth={2}
              className="mt-0.5 size-3 shrink-0"
            />
            <span>{claim.quote}</span>
          </blockquote>
        ) : null}
        <div className="mt-1.5 flex items-center gap-2">
          <KindBadge kind={claim.kind} />
          {claim.confidence ? (
            <span className="text-[9px] uppercase tracking-wide text-muted-foreground">
              {claim.confidence}
            </span>
          ) : null}
          <span className="ml-auto">
            <JumpLabel claim={claim} />
          </span>
        </div>
      </button>
    </div>
  )
}

function ClaimBranch({
  claim,
  depth,
  activeId,
  onJump,
}: {
  claim: FilingClaim
  depth: number
  activeId: string | null
  onJump: (claim: FilingClaim) => void
}) {
  const hasChildren = claim.children.length > 0

  if (!hasChildren) {
    return <ClaimButton claim={claim} isActive={activeId === claim.id} onJump={onJump} />
  }

  return (
    <details open={depth === 0} className="group/claim">
      <summary className="flex cursor-pointer list-none items-center gap-2 rounded-md px-1 py-1.5 text-xs hover:bg-muted/40">
        <span className="w-2 shrink-0 text-muted-foreground transition-transform group-open/claim:rotate-90">
          ▸
        </span>
        <span className="min-w-0 flex-1 font-medium">{claim.statement}</span>
        <SectionBadge section={claim.section} />
        <span className="shrink-0 text-[10px] text-muted-foreground">
          {claim.children.length}
        </span>
      </summary>
      <div className="ml-2 space-y-1.5 border-l border-border/60 pl-3">
        {claim.verified && claim.block !== null ? (
          <button
            type="button"
            onClick={() => onJump(claim)}
            className="text-[10px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            jump to this theme in the filing
          </button>
        ) : null}
        {claim.children.map((child) => (
          <ClaimBranch
            key={child.id}
            claim={child}
            depth={depth + 1}
            activeId={activeId}
            onJump={onJump}
          />
        ))}
      </div>
    </details>
  )
}

export function ClaimTree({
  claims,
  activeId,
  onJump,
}: {
  claims: FilingClaim[]
  activeId: string | null
  onJump: (claim: FilingClaim) => void
}) {
  if (claims.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No claims were extracted for this filing.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {claims.map((claim) => (
        <ClaimBranch
          key={claim.id}
          claim={claim}
          depth={0}
          activeId={activeId}
          onJump={onJump}
        />
      ))}
    </div>
  )
}
