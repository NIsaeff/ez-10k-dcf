import { Search01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { useEffect, useRef, useState } from "react"

import { searchTickers, type TickerSuggestion } from "@/lib/api"

const DEBOUNCE_MS = 150

export function TickerSearch({
  ticker,
  size = "md",
  onSelect,
}: {
  ticker: string
  size?: "md" | "lg"
  onSelect: (ticker: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [options, setOptions] = useState<TickerSuggestion[]>([])
  const [highlight, setHighlight] = useState(0)
  const [loading, setLoading] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLoading(true)

    const timer = setTimeout(() => {
      searchTickers(query, 20)
        .then((response) => {
          if (cancelled) return
          setOptions(response.results)
          setHighlight(0)
        })
        .catch(() => {
          if (!cancelled) setOptions([])
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }, DEBOUNCE_MS)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [open, query])

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", onPointerDown)
    return () => document.removeEventListener("mousedown", onPointerDown)
  }, [open])

  const choose = (option: TickerSuggestion) => {
    onSelect(option.ticker)
    setOpen(false)
    setQuery("")
  }

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault()
      setHighlight((current) => Math.min(current + 1, options.length - 1))
    } else if (event.key === "ArrowUp") {
      event.preventDefault()
      setHighlight((current) => Math.max(current - 1, 0))
    } else if (event.key === "Enter") {
      const picked = options[highlight]
      if (picked) {
        event.preventDefault()
        choose(picked)
      }
    } else if (event.key === "Escape") {
      setOpen(false)
    }
  }

  const large = size === "lg"

  return (
    <div ref={containerRef} className="relative w-full">
      <div
        className={`flex items-center gap-2.5 rounded-xl border border-input bg-background px-3 shadow-sm transition-colors focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/20 ${
          large ? "h-12" : "h-9"
        }`}
      >
        <HugeiconsIcon
          icon={Search01Icon}
          strokeWidth={2}
          className={`shrink-0 text-muted-foreground ${large ? "size-5" : "size-4"}`}
        />
        <input
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls="ticker-options"
          aria-autocomplete="list"
          aria-label="Search for a company ticker"
          autoComplete="off"
          spellCheck={false}
          value={open ? query : ticker}
          placeholder={
            open ? "Type a ticker or company name…" : ticker
          }
          onFocus={() => {
            setOpen(true)
            setQuery("")
          }}
          onChange={(event) => {
            setOpen(true)
            setQuery(event.target.value.toUpperCase())
          }}
          onKeyDown={onKeyDown}
          className={`w-full bg-transparent outline-none placeholder:text-muted-foreground ${
            large ? "text-base" : "text-sm"
          }`}
        />
      </div>

      {open ? (
        <div
          id="ticker-options"
          role="listbox"
          className="absolute left-0 right-0 z-50 mt-2 max-h-80 overflow-y-auto rounded-xl border bg-popover p-1.5 text-popover-foreground shadow-xl"
        >
          {loading && options.length === 0 ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">
              Searching SEC filings…
            </p>
          ) : null}

          {!loading && options.length === 0 ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">
              No matches. SEC lists US filers only — no ETFs or indices.
            </p>
          ) : null}

          {options.map((option, index) => (
            <button
              key={option.ticker}
              type="button"
              role="option"
              aria-selected={index === highlight}
              onMouseDown={(event) => event.preventDefault()}
              onMouseEnter={() => setHighlight(index)}
              onClick={() => choose(option)}
              className={`flex w-full items-baseline gap-3 rounded-lg px-3 text-left ${
                large ? "py-2.5" : "py-1.5"
              } ${index === highlight ? "bg-muted" : ""}`}
            >
              <span
                className={`shrink-0 font-semibold tabular-nums ${
                  large ? "w-16 text-sm" : "w-14 text-xs"
                }`}
              >
                {option.ticker}
              </span>
              <span
                className={`min-w-0 flex-1 truncate text-muted-foreground ${
                  large ? "text-sm" : "text-xs"
                }`}
              >
                {option.name}
              </span>
              {option.pilot ? (
                <span className="shrink-0 rounded-full border border-border/60 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-muted-foreground">
                  pilot
                </span>
              ) : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
