import { Search01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { useEffect, useRef, useState } from "react"

import { searchTickers, type TickerSuggestion } from "@/lib/api"

const DEBOUNCE_MS = 150

export function TickerSearch({
  ticker,
  disabled,
  onSelect,
}: {
  ticker: string
  disabled?: boolean
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

  return (
    <div ref={containerRef} className="relative">
      <div className="flex items-center gap-1.5 rounded-md border border-input bg-background px-2">
        <HugeiconsIcon
          icon={Search01Icon}
          strokeWidth={2}
          className="size-3.5 shrink-0 text-muted-foreground"
        />
        <input
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls="ticker-options"
          aria-autocomplete="list"
          autoComplete="off"
          spellCheck={false}
          disabled={disabled}
          value={open ? query : ticker}
          placeholder={open ? "Search a ticker or company…" : ticker}
          onFocus={() => {
            setOpen(true)
            setQuery("")
          }}
          onChange={(event) => {
            setOpen(true)
            setQuery(event.target.value.toUpperCase())
          }}
          onKeyDown={onKeyDown}
          className="h-8 w-40 bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:opacity-50 sm:w-56"
        />
      </div>

      {open ? (
        <div
          id="ticker-options"
          role="listbox"
          className="absolute right-0 z-50 mt-1 max-h-72 w-80 overflow-y-auto rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
        >
          {loading && options.length === 0 ? (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">Searching…</p>
          ) : null}

          {!loading && options.length === 0 ? (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">
              No matches. SEC lists US filers only.
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
              className={`flex w-full items-baseline gap-2 rounded px-2 py-1.5 text-left text-xs ${
                index === highlight ? "bg-muted" : ""
              }`}
            >
              <span className="w-14 shrink-0 font-medium">{option.ticker}</span>
              <span className="min-w-0 flex-1 truncate text-muted-foreground">
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
