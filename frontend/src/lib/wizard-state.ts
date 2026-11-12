import { SUPPORTED_TICKERS, type Ticker } from "@/lib/tickers"

export type GrowthModel = "fade" | "constant"

export type WizardSearch = {
  ticker: Ticker
  years: number
  /** Terminal growth in percent, matching the slider range (1-5). */
  terminal: number
  model: GrowthModel
  /** WACC override in percent; undefined means "use the engine default". */
  wacc?: number
}

export const DEFAULT_SEARCH: WizardSearch = {
  ticker: "KO",
  years: 5,
  terminal: 2.5,
  model: "fade",
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high)
}

function toNumber(value: unknown, fallback: number): number {
  const parsed = typeof value === "number" ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

/**
 * Parse and clamp URL search params.
 *
 * Deliberately forgiving: a hand-edited or stale link should still render a
 * working page instead of a router error, so bad values fall back to defaults
 * rather than throwing.
 */
export function validateWizardSearch(
  search: Record<string, unknown>,
): WizardSearch {
  const rawTicker = String(search.ticker ?? DEFAULT_SEARCH.ticker).toUpperCase()
  const ticker = (SUPPORTED_TICKERS as readonly string[]).includes(rawTicker)
    ? (rawTicker as Ticker)
    : DEFAULT_SEARCH.ticker

  const model = search.model === "constant" ? "constant" : "fade"

  const waccValue = search.wacc === undefined ? undefined : toNumber(search.wacc, NaN)
  const wacc =
    waccValue !== undefined && Number.isFinite(waccValue) && waccValue > 0
      ? clamp(waccValue, 1, 30)
      : undefined

  return {
    ticker,
    years: Math.round(clamp(toNumber(search.years, DEFAULT_SEARCH.years), 3, 10)),
    terminal: clamp(toNumber(search.terminal, DEFAULT_SEARCH.terminal), 1, 5),
    model,
    wacc,
  }
}

/** Percent form -> decimal rate for the API. */
export function toRate(percent: number): number {
  return Math.round((percent / 100) * 1e6) / 1e6
}
