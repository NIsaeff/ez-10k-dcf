import type { ValuationResult } from "@/lib/chat"

export type GrowthModel = "fade" | "constant"

export type DcfOverrides = {
  projection_years?: number
  terminal_growth_rate?: number
  growth_rate?: number
  growth_model?: GrowthModel
  wacc?: number
}

export type SensitivityGrid = {
  wacc_values: number[]
  growth_values: number[]
  values: (number | null)[][]
  base_wacc: number
  base_terminal_growth: number
}

export type TickerSuggestion = {
  ticker: string
  name: string
  cik: string
  pilot: boolean
}

export type TickerSearchResponse = {
  query: string
  results: TickerSuggestion[]
  total: number
}

export type FilingBlock = {
  index: number
  section: string
  text: string
}

export type FilingSection = {
  id: string
  label: string
  block: number
}

export type FilingClaim = {
  id: string
  statement: string
  kind: string | null
  quote: string | null
  section: string | null
  block: number | null
  start: number | null
  end: number | null
  verified: boolean
  confidence: string | null
  children: FilingClaim[]
}

export type FilingAnalysis = {
  ticker: string
  company_name: string
  accession: string
  document_url: string
  document_view_url: string
  filed: string
  fiscal_year_end: string
  sections: FilingSection[]
  claims: FilingClaim[]
  blocks: FilingBlock[]
  flags: string[]
  cached: boolean
}

export type AssumptionEvidence = {
  claim_id: string
  statement: string
  quote: string | null
  section: string | null
  verified: boolean
}

export type AssumptionReview = {
  key: string
  label: string
  engine_value: number
  engine_source: string
  stance: "supported" | "challenged" | "context_only"
  lean: "higher" | "lower" | "neutral" | null
  suggested_range: number[] | null
  rationale: string | null
  evidence: AssumptionEvidence[]
}

export type AssumptionReviewResponse = {
  ticker: string
  accession: string
  reviews: AssumptionReview[]
  flags: string[]
  cached: boolean
}

export type WaccInput = {
  key: string
  label: string
  value: number | null
  source: string
  detail: string | null
}

export type WaccBreakdown = {
  ticker: string
  wacc: number
  cost_of_equity: number | null
  cost_of_debt: number | null
  weight_equity: number | null
  weight_debt: number | null
  market_cap: number | null
  price: number | null
  as_of: string | null
  inputs: WaccInput[]
  flags: string[]
}

type ErrorBody = {
  error?: string
  detail?: string
  missing_fields?: string[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    let body: ErrorBody = {}
    try {
      body = (await response.json()) as ErrorBody
    } catch {
      // Non-JSON error bodies are allowed; fall back to the status code.
    }
    const detail =
      body.detail ??
      body.error ??
      (body.missing_fields?.length
        ? `missing: ${body.missing_fields.join(", ")}`
        : undefined)
    throw new Error(detail ?? `Request failed: ${response.status}`)
  }
  return (await response.json()) as T
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}

export function analyzeTicker(ticker: string): Promise<ValuationResult> {
  return request<ValuationResult>(
    `/api/analyze/${encodeURIComponent(ticker)}`,
    { method: "POST" },
  )
}

export function recalcDcf(
  ticker: string,
  overrides: DcfOverrides,
): Promise<ValuationResult> {
  return postJson<ValuationResult>(
    `/api/dcf/${encodeURIComponent(ticker)}`,
    overrides,
  )
}

export function fetchSensitivity(
  ticker: string,
  overrides: DcfOverrides,
): Promise<SensitivityGrid> {
  return postJson<SensitivityGrid>(
    `/api/dcf/${encodeURIComponent(ticker)}/sensitivity`,
    overrides,
  )
}

export function searchTickers(
  query: string,
  limit = 20,
): Promise<TickerSearchResponse> {
  const params = new URLSearchParams({ q: query, limit: String(limit) })
  return request<TickerSearchResponse>(`/api/tickers?${params.toString()}`)
}

export function fetchFiling(ticker: string): Promise<FilingAnalysis> {
  return request<FilingAnalysis>(`/api/filing/${encodeURIComponent(ticker)}`)
}

export function fetchAssumptions(
  ticker: string,
): Promise<AssumptionReviewResponse> {
  return request<AssumptionReviewResponse>(
    `/api/assumptions/${encodeURIComponent(ticker)}`,
  )
}

export function fetchWacc(ticker: string): Promise<WaccBreakdown> {
  return request<WaccBreakdown>(`/api/wacc/${encodeURIComponent(ticker)}`)
}
