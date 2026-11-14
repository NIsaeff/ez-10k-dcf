import { useEffect, useRef, useState } from "react"

import { useTheme } from "@/components/theme-provider"
import type { FilingClaim, FilingSection } from "@/lib/api"

/**
 * Renders the filing itself in a sandboxed same-origin iframe.
 *
 * The backend serves a script-stripped copy with an injected highlighter; this
 * component only talks to it over postMessage, so no DOM access is needed and
 * the sandbox can stay without allow-same-origin.
 */
export function FilingFrame({
  src,
  active,
  sections,
}: {
  src: string
  active: FilingClaim | null
  sections: FilingSection[]
}) {
  const frameRef = useRef<HTMLIFrameElement>(null)
  const [ready, setReady] = useState(false)
  const [highlight, setHighlight] = useState<"idle" | "found" | "missing">("idle")
  const { resolvedTheme } = useTheme()

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type === "ready") setReady(true)
      if (event.data?.type === "highlighted") {
        setHighlight(event.data.found ? "found" : "missing")
      }
    }
    window.addEventListener("message", onMessage)
    return () => window.removeEventListener("message", onMessage)
  }, [])

  useEffect(() => {
    setReady(false)
  }, [src])

  useEffect(() => {
    if (!ready) return
    const quote = active?.quote
    if (!quote) return
    setHighlight("idle")
    frameRef.current?.contentWindow?.postMessage(
      { type: "highlight", quote, section: active?.section ?? null },
      "*",
    )
  }, [ready, active])

  useEffect(() => {
    if (!ready) return
    frameRef.current?.contentWindow?.postMessage({ type: "theme", mode: resolvedTheme }, "*")
  }, [ready, resolvedTheme])

  const post = (message: unknown) => {
    frameRef.current?.contentWindow?.postMessage(message, "*")
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex flex-wrap gap-1.5">
        {sections
          .filter((section) => section.id !== "Preamble")
          .map((section) => (
            <button
              key={section.id}
              type="button"
              onClick={() => post({ type: "section", label: section.id })}
              title={section.label}
              className="rounded-full border border-border/60 px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {section.id}
            </button>
          ))}
      </div>

      {highlight === "missing" ? (
        <p className="mb-1.5 rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-700 dark:text-amber-300">
          Couldn&rsquo;t locate that quote in the rendered document.
        </p>
      ) : null}

      <div
        data-highlight={highlight}
        data-highlight-for={active?.id ?? ""}
        className="relative min-h-0 flex-1 overflow-hidden rounded-md border"
      >
        {!ready ? (
            <p className="absolute inset-x-0 top-0 z-10 bg-background/90 p-2 text-xs text-muted-foreground">
            Rendering the filing…
          </p>
        ) : null}
        <iframe
          ref={frameRef}
          src={src}
          title="10-K source document"
          sandbox="allow-scripts"
          className="h-full w-full bg-white"
        />
      </div>
    </div>
  )
}
