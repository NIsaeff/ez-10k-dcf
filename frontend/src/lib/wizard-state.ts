import type { DcfOverrides } from "@/lib/api"

export type GrowthModel = "fade" | "constant"

export type WizardSearch = {
  ticker: string
  years: number
  /** Terminal growth in percent, matching the slider range (1-5). */
  terminal: number
  model: GrowthModel
  /** WACC override in percent; undefined means "use the engine default". */
  wacc?: number
  /** Year-1 growth override in percent. */
  growth?: number
  /** Tax-rate override in percent. */
  tax?: number
  /** CapEx override as a percent of revenue. */
  capex?: number
  /** Share-count override, in millions. */
  shares?: number
  /** Active DCF tab. */
  tab?: "fcff" | "wacc" | "dcf"
}

const TICKER_PATTERN = /^[A-Z0-9.-]{1,10}$/

/** Any SEC symbol is allowed; the pilot list is only a default view. */
export function normalizeTicker(value: unknown, fallback = "KO"): string {
  const candidate = String(value ?? fallback)
    .toUpperCase()
    .trim()
  return TICKER_PATTERN.test(candidate) ? candidate : fallback
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
  const ticker = normalizeTicker(search.ticker, DEFAULT_SEARCH.ticker)

  const model = search.model === "constant" ? "constant" : "fade"

  const waccValue = search.wacc === undefined ? undefined : toNumber(search.wacc, NaN)
  const wacc =
    waccValue !== undefined && Number.isFinite(waccValue) && waccValue > 0
      ? clamp(waccValue, 1, 30)
      : undefined

  const optionalPercent = (
    raw: unknown,
    low: number,
    high: number,
  ): number | undefined => {
    if (raw === undefined) return undefined
    const value = toNumber(raw, NaN)
    return Number.isFinite(value) ? clamp(value, low, high) : undefined
  }

  const sharesValue = search.shares === undefined ? undefined : toNumber(search.shares, NaN)
  const shares =
    sharesValue !== undefined && Number.isFinite(sharesValue) && sharesValue > 0
      ? clamp(sharesValue, 1, 100_000)
      : undefined

  return {
    ticker,
    years: Math.round(clamp(toNumber(search.years, DEFAULT_SEARCH.years), 3, 10)),
    terminal: clamp(toNumber(search.terminal, DEFAULT_SEARCH.terminal), 1, 5),
    model,
    wacc,
    growth: optionalPercent(search.growth, 0, 25),
    tax: optionalPercent(search.tax, 0, 40),
    capex: optionalPercent(search.capex, 0, 40),
    shares,
    tab:
      search.tab === "fcff" || search.tab === "wacc" || search.tab === "dcf"
        ? search.tab
        : undefined,
  }
}

/** Full default search for programmatic navigation to /wizard. */
export function defaultWizardSearch(ticker: string = DEFAULT_SEARCH.ticker): WizardSearch {
  return { ...DEFAULT_SEARCH, ticker }
}

/** Percent form -> decimal rate for the API. */
export function toRate(percent: number): number {
  return Math.round((percent / 100) * 1e6) / 1e6
}

/** Search params -> engine overrides. Fields equal to the defaults are harmless. */
export function overridesFromSearch(search: WizardSearch): DcfOverrides {
  return {
    projection_years: search.years,
    terminal_growth_rate: toRate(search.terminal),
    growth_model: search.model,
    ...(search.wacc === undefined ? {} : { wacc: toRate(search.wacc) }),
    ...(search.growth === undefined
      ? {}
      : { growth_rate: toRate(search.growth) }),
    ...(search.tax === undefined ? {} : { tax_rate: toRate(search.tax) }),
    ...(search.capex === undefined ? {} : { capex_rate: toRate(search.capex) }),
    ...(search.shares === undefined
      ? {}
      : { shares_outstanding: search.shares * 1_000_000 }),
  }
}
