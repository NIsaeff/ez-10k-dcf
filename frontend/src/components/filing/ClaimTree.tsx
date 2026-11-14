import {
  ArrowUpRight01Icon,
  Cancel01Icon,
  CheckmarkCircle02Icon,
  PencilEdit01Icon,
  QuoteDownIcon,
  RotateLeft01Icon,
} from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { useEffect, useRef, useState } from "react"

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

function PencilButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      title="Rephrase this claim"
      aria-label="Rephrase this claim"
      onClick={(event) => {
        event.preventDefault()
        event.stopPropagation()
        onClick()
      }}
      className="shrink-0 rounded p-0.5 text-muted-foreground/70 transition-colors hover:bg-muted hover:text-foreground focus-visible:text-foreground"
    >
      <HugeiconsIcon icon={PencilEdit01Icon} strokeWidth={2} className="size-3" />
    </button>
  )
}

function ClaimEditor({
  value,
  onSave,
  onCancel,
}: {
  value: string
  onSave: (statement: string) => void
  onCancel: () => void
}) {
  const [draft, setDraft] = useState(value)
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    ref.current?.focus()
    ref.current?.setSelectionRange(value.length, value.length)
  }, [value])

  const save = () => {
    const trimmed = draft.trim()
    if (trimmed && trimmed !== value) onSave(trimmed)
    else onCancel()
  }

  return (
    <div
      className="space-y-1.5"
      onClick={(event) => {
        event.preventDefault()
        event.stopPropagation()
      }}
    >
      <textarea
        ref={ref}
        value={draft}
        rows={2}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault()
            onCancel()
          } else if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault()
            save()
          }
        }}
        className="w-full resize-y rounded-md border border-input bg-background p-1.5 text-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/20"
      />
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={save}
          className="inline-flex items-center gap-1 rounded-md border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] font-medium transition-colors hover:bg-primary/20"
        >
          <HugeiconsIcon icon={CheckmarkCircle02Icon} strokeWidth={2} className="size-3" />
          Save
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-muted"
        >
          <HugeiconsIcon icon={Cancel01Icon} strokeWidth={2} className="size-3" />
          Cancel
        </button>
        <span className="text-[10px] text-muted-foreground">
          Enter saves · Esc cancels
        </span>
      </div>
    </div>
  )
}

function EditedBadge() {
  return (
    <span className="rounded-full border border-primary/40 bg-primary/10 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-primary">
      edited
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

type Handlers = {
  activeId: string | null
  textFor: (claim: FilingClaim) => string
  isOverridden: (claim: FilingClaim) => boolean
  onJump: (claim: FilingClaim) => void
  onSave: (claim: FilingClaim, statement: string) => void
  onReset: (claim: FilingClaim) => void
}

function ClaimCard({
  claim,
  handlers,
}: {
  claim: FilingClaim
  handlers: Handlers
}) {
  const [editing, setEditing] = useState(false)
  const [resetting, setResetting] = useState(false)
  const isActive = handlers.activeId === claim.id
  const canJump = claim.verified && claim.block !== null
  const overridden = handlers.isOverridden(claim)

  return (
    <div
      className={`group/claim rounded-lg border px-2.5 py-2 transition-colors ${
        isActive
          ? "border-primary/60 bg-primary/10"
          : "border-border/60 bg-card hover:bg-muted/40"
      }`}
    >
      {editing ? (
        <ClaimEditor
          value={handlers.textFor(claim)}
          onSave={(statement) => {
            handlers.onSave(claim, statement)
            setEditing(false)
          }}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <>
          <div className="flex items-start gap-1.5">
            <button
              type="button"
              disabled={!canJump}
              onClick={() => canJump && handlers.onJump(claim)}
              className="min-w-0 flex-1 text-left disabled:cursor-default"
            >
              <p className="text-xs">{handlers.textFor(claim)}</p>
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
            </button>
            <PencilButton onClick={() => setEditing(true)} />
          </div>

          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <KindBadge kind={claim.kind} />
            {claim.confidence ? (
              <span className="text-[9px] uppercase tracking-wide text-muted-foreground">
                {claim.confidence}
              </span>
            ) : null}
            {overridden ? <EditedBadge /> : null}
            {overridden ? (
              <button
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  if (resetting) {
                    handlers.onReset(claim)
                    setResetting(false)
                    return
                  }
                  setResetting(true)
                  window.setTimeout(() => setResetting(false), 2500)
                }}
                className="text-[9px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
              >
                {resetting ? "confirm reset" : "reset"}
              </button>
            ) : null}
            <span className="ml-auto">
              <JumpLabel claim={claim} />
            </span>
          </div>
        </>
      )}
    </div>
  )
}

function ClaimBranch({
  claim,
  depth,
  handlers,
}: {
  claim: FilingClaim
  depth: number
  handlers: Handlers
}) {
  const [editing, setEditing] = useState(false)
  const hasChildren = claim.children.length > 0

  if (!hasChildren) {
    return <ClaimCard claim={claim} handlers={handlers} />
  }

  return (
    <details open={depth === 0} className="group/claim">
      <summary className="flex cursor-pointer list-none items-center gap-2 rounded-md px-1 py-1.5 text-xs hover:bg-muted/40">
        <span className="w-2 shrink-0 text-muted-foreground transition-transform group-open/claim:rotate-90">
          ▸
        </span>
        <span className="min-w-0 flex-1 font-medium">{handlers.textFor(claim)}</span>
        {handlers.isOverridden(claim) ? <EditedBadge /> : null}
        <PencilButton onClick={() => setEditing((current) => !current)} />
        <SectionBadge section={claim.section} />
        <span className="shrink-0 text-[10px] text-muted-foreground">
          {claim.children.length}
        </span>
      </summary>

      {editing ? (
        <div className="mb-1.5 px-1">
          <ClaimEditor
            value={handlers.textFor(claim)}
            onSave={(statement) => {
              handlers.onSave(claim, statement)
              setEditing(false)
            }}
            onCancel={() => setEditing(false)}
          />
        </div>
      ) : null}

      <div className="ml-2 space-y-1.5 border-l border-border/60 pl-3">
        {claim.verified && claim.block !== null ? (
          <button
            type="button"
            onClick={() => handlers.onJump(claim)}
            className="text-[10px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            jump to this theme in the filing
          </button>
        ) : null}
        {claim.children.map((child) => (
          <ClaimBranch key={child.id} claim={child} depth={depth + 1} handlers={handlers} />
        ))}
      </div>
    </details>
  )
}

export function ClaimTree({
  claims,
  activeId,
  overrides,
  onJump,
  onSave,
  onReset,
}: {
  claims: FilingClaim[]
  activeId: string | null
  overrides: Record<string, string>
  onJump: (claim: FilingClaim) => void
  onSave: (claim: FilingClaim, statement: string) => void
  onReset: (claim: FilingClaim) => void
}) {
  if (claims.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No claims were extracted for this filing.
      </p>
    )
  }

  const handlers: Handlers = {
    activeId,
    textFor: (claim) => overrides[claim.id] ?? claim.statement,
    isOverridden: (claim) => claim.id in overrides,
    onJump,
    onSave,
    onReset,
  }

  return (
    <div className="space-y-2">
      {claims.map((claim) => (
        <ClaimBranch key={claim.id} claim={claim} depth={0} handlers={handlers} />
      ))}
    </div>
  )
}
