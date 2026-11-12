import { SUPPORTED_TICKERS, type Ticker } from "@/lib/tickers"

export function TickerBar({
  ticker,
  onChange,
  disabled,
}: {
  ticker: string
  onChange: (ticker: Ticker) => void
  disabled?: boolean
}) {
  return (
    <label className="flex items-center gap-2 text-xs text-muted-foreground">
      <span className="sr-only sm:not-sr-only">Ticker</span>
      <select
        value={ticker}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value as Ticker)}
        className="h-8 rounded-md border border-input bg-background px-2 text-sm text-foreground disabled:opacity-50"
      >
        {SUPPORTED_TICKERS.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  )
}
