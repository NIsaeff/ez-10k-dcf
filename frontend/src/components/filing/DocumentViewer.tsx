import { memo } from "react"

import type { FilingBlock, FilingClaim, FilingSection } from "@/lib/api"

type Highlight = { block: number; start: number; end: number } | null

const Block = memo(function Block({
  block,
  highlight,
}: {
  block: FilingBlock
  highlight: Highlight
}) {
  const isTarget = highlight !== null && highlight.block === block.index

  let content: React.ReactNode = block.text
  if (isTarget && highlight) {
    const before = block.text.slice(0, highlight.start)
    const match = block.text.slice(highlight.start, highlight.end)
    const after = block.text.slice(highlight.end)
    content = (
      <>
        {before}
        <mark className="rounded bg-amber-300/70 px-0.5 text-foreground dark:bg-amber-400/40">
          {match}
        </mark>
        {after}
      </>
    )
  }

  return (
    <p
      id={`block-${block.index}`}
      className={`scroll-mt-24 rounded px-1 py-0.5 text-[12px] leading-relaxed ${
        isTarget ? "bg-amber-100/50 dark:bg-amber-500/10" : ""
      }`}
    >
      {content}
    </p>
  )
})

export function DocumentViewer({
  blocks,
  sections,
  active,
  onSection,
}: {
  blocks: FilingBlock[]
  sections: FilingSection[]
  active: FilingClaim | null
  onSection: (section: FilingSection) => void
}) {
  const highlight: Highlight =
    active && active.block !== null && active.start !== null && active.end !== null
      ? { block: active.block, start: active.start, end: active.end }
      : null

  return (
    <div>
      <div className="sticky top-0 z-10 -mx-1 mb-2 flex flex-wrap gap-1.5 bg-background/95 px-1 py-2 backdrop-blur">
        {sections
          .filter((section) => section.id !== "Preamble")
          .map((section) => (
            <button
              key={section.id}
              type="button"
              onClick={() => onSection(section)}
              title={section.label}
              className="rounded-full border border-border/60 px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {section.id}
            </button>
          ))}
      </div>

      <div className="space-y-1">
        {blocks.map((block) => (
          <Block key={block.index} block={block} highlight={highlight} />
        ))}
      </div>
    </div>
  )
}
