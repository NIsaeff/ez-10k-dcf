export type ChatRole = "user" | "assistant";

export type GrowthModel = "fade" | "constant";

export type FilingInfo = {
  accession_number: string;
  form: string;
  fiscal_year_end: string;
  filed: string;
  url: string;
};

export type YearFinancials = {
  fiscal_year: number;
  revenue: number | null;
  ebit: number;
  pretax_income: number | null;
  tax_expense: number | null;
  depreciation_amortization: number;
  capital_expenditures: number;
  change_in_nwc: number | null;
  fcff: number;
};

export type Assumptions = {
  projection_years: number;
  terminal_growth_rate: number;
  wacc: number;
  wacc_source: string;
  tax_rate: number;
  tax_rate_source: string;
  growth_rate: number;
  growth_model: GrowthModel;
  growth_source: string;
  fcff_base: number;
  fcff_base_source: string;
  share_count_source: string;
  net_debt_treatment: string;
};

export type ProjectionYear = {
  year: number;
  fcff: number;
  discount_factor: number;
  present_value: number;
};

export type EngineInputs = {
  base_fcff: number;
  growth_rate: number;
  growth_model: GrowthModel;
  terminal_growth_rate: number;
  projection_years: number;
  wacc: number;
  total_debt: number;
  cash: number;
  shares_outstanding: number;
  tax_rate: number;
  base_year: number;
};

export type ValuationSummary = {
  terminal_value: number;
  present_value_terminal: number;
  enterprise_value: number;
  total_debt: number;
  cash_and_equivalents: number;
  net_debt: number;
  equity_value: number;
  shares_outstanding: number;
  value_per_share: number;
};

export type SourceFact = {
  metric: string;
  tag: string;
  fiscal_year: number;
  value: number;
  unit: string;
  end: string | null;
  filed: string | null;
  form: string | null;
  accession_number: string | null;
  url: string;
};

export type ValuationResult = {
  ticker: string;
  company_name: string;
  cik: string;
  filing: FilingInfo;
  history: YearFinancials[];
  assumptions: Assumptions;
  projection: ProjectionYear[];
  valuation: ValuationSummary;
  engine?: EngineInputs | null;
  overrides_applied?: string[];
  flags: string[];
  sources: string[];
  source_facts?: SourceFact[];
  disclaimer: string;
};

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  valuation?: ValuationResult | null;
};

export type ChatReply = {
  reply: string;
  valuation: ValuationResult | null;
};

// TODO(chat-history): every request sends the full conversation, so payload
// size and model input tokens grow with each turn (roughly O(n^2) bytes per
// session). When persistence lands, send only { conversation_id, message }
// and keep history server-side — or at minimum trim to the last N messages /
// a token budget before calling the model.
export async function sendChat(messages: ChatMessage[]): Promise<ChatReply> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: messages.map(({ role, content }) => ({ role, content })),
    }),
  });

  if (!res.ok) throw new Error(`Chat request failed: ${res.status}`);

  const data = (await res.json()) as ChatReply;
  return { reply: data.reply, valuation: data.valuation ?? null };
}
