import { useState } from "react"

import { HugeiconsIcon } from "@hugeicons/react"
import {
  ArrowUpRight01Icon,
  DatabaseIcon,
  GlobeIcon,
  Search01Icon,
  SourceCodeIcon,
} from "@hugeicons/core-free-icons"

import { CodeBlock, CodeBlockContent } from "@/components/ui/code-block"
import {
  Trace,
  TraceCollapsible,
  TraceCollapsibleContent,
  TraceCollapsibleTrigger,
  TraceIcon,
  TraceLine,
  TraceTitle,
} from "@/components/ui/trace"
import type { SourceRef, TraceStep } from "@/lib/chat"

/**
 * Visibility into what the assistant did, built on the shadcn AI Elements
 * patterns: Chain of Thought (summary → steps), Tool (one step, input→output)
 * and Sources (the FRED series the answer rests on).
 *
 * There is no streaming yet, so `running` is the client's optimistic state
 * while the single /api/chat request is in flight.
 */
export function ChatTrace({
  trace,
  running = false,
}: {
  trace?: TraceStep[]
  running?: boolean
}) {
  if (running) {
    return (
      <Trace>
        <TraceLine status="running">
          <TraceIcon>
            <HugeiconsIcon icon={Search01Icon} strokeWidth={2} />
          </TraceIcon>
          <TraceTitle>Researching FRED…</TraceTitle>
        </TraceLine>
      </Trace>
    )
  }

  const steps = trace ?? []
  if (steps.length === 0) return null

  const failed = steps.filter((step) => step.status === "error").length
  const summary = failed
    ? `FRED research failed (${failed} of ${steps.length})`
    : `Researched FRED in ${steps.length} step${steps.length === 1 ? "" : "s"}`

  return (
    <Trace>
      <TraceCollapsible>
        <TraceCollapsibleTrigger>
          <TraceLine status={failed ? "error" : undefined}>
            <TraceIcon>
              <HugeiconsIcon icon={SourceCodeIcon} strokeWidth={2} />
            </TraceIcon>
            <TraceTitle>{summary}</TraceTitle>
          </TraceLine>
        </TraceCollapsibleTrigger>
        <TraceCollapsibleContent keepMounted>
          <Trace>
            {steps.map((step, index) => (
              <TraceStepRow key={`${step.tool}-${index}`} step={step} />
            ))}
          </Trace>
        </TraceCollapsibleContent>
      </TraceCollapsible>
    </Trace>
  )
}

function TraceStepRow({ step }: { step: TraceStep }) {
  const failed = step.status === "error"

  if (!step.output) {
    return (
      <TraceLine status={failed ? "error" : undefined}>
        <TraceIcon>
          <HugeiconsIcon icon={Search01Icon} strokeWidth={2} />
        </TraceIcon>
        <TraceTitle>{stepTitle(step)}</TraceTitle>
      </TraceLine>
    )
  }

  return (
    <TraceCollapsible>
      <TraceCollapsibleTrigger>
        <TraceLine status={failed ? "error" : undefined}>
          <TraceIcon>
            <HugeiconsIcon icon={DatabaseIcon} strokeWidth={2} />
          </TraceIcon>
          <TraceTitle>
            {stepTitle(step)}
            <span className="ms-1.5 text-muted-foreground/60 tabular-nums">
              {step.duration_ms} ms
            </span>
          </TraceTitle>
        </TraceLine>
      </TraceCollapsibleTrigger>
      <TraceCollapsibleContent>
        <CodeBlock size="sm">
          <CodeBlockContent wrap className="max-h-64">
            {prettyJson(step.output)}
          </CodeBlockContent>
        </CodeBlock>
      </TraceCollapsibleContent>
    </TraceCollapsible>
  )
}

export function ChatSources({ sources }: { sources?: SourceRef[] }) {
  const list = sources ?? []
  if (list.length === 0) return null

  return (
    <Trace>
      <TraceCollapsible>
        <TraceCollapsibleTrigger>
          <TraceLine>
            <TraceIcon>
              <HugeiconsIcon icon={DatabaseIcon} strokeWidth={2} />
            </TraceIcon>
            <TraceTitle>
              Used {list.length} source{list.length === 1 ? "" : "s"}
            </TraceTitle>
          </TraceLine>
        </TraceCollapsibleTrigger>
        <TraceCollapsibleContent>
          <Trace>
            {list.map((source) => (
              <a
                key={source.id}
                href={source.url}
                target="_blank"
                rel="noreferrer"
              >
                <TraceLine>
                  <TraceIcon>
                    <SourceFavicon url={source.url} />
                  </TraceIcon>
                  <TraceTitle>
                    {source.id}
                    {source.title ? ` · ${source.title}` : ""}
                    <span className="text-muted-foreground/60">
                      {source.units ? ` · ${source.units}` : ""}
                      {source.date ? ` · ${source.date}` : ""}
                    </span>
                  </TraceTitle>
                  <TraceIcon>
                    <HugeiconsIcon icon={ArrowUpRight01Icon} strokeWidth={2} />
                  </TraceIcon>
                  <span className="sr-only"> (opens in a new tab)</span>
                </TraceLine>
              </a>
            ))}
          </Trace>
        </TraceCollapsibleContent>
      </TraceCollapsible>
    </Trace>
  )
}

/**
 * The source's own favicon — FRED serves /favicon.ico. Falls back to a globe
 * glyph when the host has none or the image fails to load.
 */
function SourceFavicon({ url }: { url: string }) {
  const [failed, setFailed] = useState(false)
  const src = faviconUrl(url)

  if (!src || failed) {
    return <HugeiconsIcon icon={GlobeIcon} strokeWidth={2} />
  }

  return (
    <img
      src={src}
      alt=""
      aria-hidden="true"
      loading="lazy"
      className="size-3 rounded-[2px] object-contain"
      onError={() => setFailed(true)}
    />
  )
}

function faviconUrl(url: string): string | null {
  try {
    return `${new URL(url).origin}/favicon.ico`
  } catch {
    return null
  }
}

/** Readable one-liner for each MCP tool, matching the docs' tense rules. */function stepTitle(step: TraceStep): string {
  const failed = step.status === "error"
  const input = step.input

  switch (step.tool) {
    case "fred_get_series": {
      const series = asString(input.series_id) ?? "series"
      // Same series can be fetched twice with different FRED transforms.
      const units = asString(input.units)
      const transform = units && units !== "lin" ? ` (${units})` : ""
      return `${failed ? "Failed to fetch" : "Fetched"} ${series}${transform}`
    }
    case "fred_search": {
      const query = asString(input.search_text) ?? "macro data"
      return `${failed ? "Failed to search" : "Searched"} FRED for “${query}”`
    }
    case "fred_browse": {
      const kind = asString(input.browse_type)?.replaceAll("_", " ") ?? "the catalog"
      return `${failed ? "Failed to browse" : "Browsed"} ${kind}`
    }
    default:
      return `${failed ? "Failed" : "Ran"} ${step.tool}`
  }
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined
}

/** Tool output is JSON when the square brackets close; otherwise show it raw. */
function prettyJson(output: string): string {
  try {
    return JSON.stringify(JSON.parse(output), null, 2)
  } catch {
    return output
  }
}
