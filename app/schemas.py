from typing import Any, Literal

from pydantic import BaseModel, Field

ChatRole = Literal["user", "assistant", "system"]
GrowthModel = Literal["fade", "constant"]


class ChatMessage(BaseModel):
    role: ChatRole
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)


class FilingInfo(BaseModel):
    accession_number: str
    form: str
    fiscal_year_end: str
    filed: str
    url: str


class SourceFact(BaseModel):
    """One XBRL fact behind a DCF input, for click-through provenance."""

    metric: str
    tag: str
    fiscal_year: int
    value: float
    unit: str = "USD"
    end: str | None = None
    filed: str | None = None
    form: str | None = None
    accession_number: str | None = None
    url: str


class YearFinancials(BaseModel):
    fiscal_year: int
    revenue: float | None = None
    ebit: float
    pretax_income: float | None = None
    tax_expense: float | None = None
    depreciation_amortization: float
    capital_expenditures: float
    change_in_nwc: float | None = None
    fcff: float


class Assumptions(BaseModel):
    projection_years: int
    terminal_growth_rate: float
    wacc: float
    wacc_source: str
    tax_rate: float
    tax_rate_source: str
    growth_rate: float
    growth_model: GrowthModel = "fade"
    growth_source: str
    fcff_base: float
    fcff_base_source: str
    share_count_source: str
    net_debt_treatment: str


class EngineInputs(BaseModel):
    """Everything the projection math consumes.

    The frontend mirrors ``project_fcff`` + ``build_valuation`` from exactly
    these values, so slider previews and backend results cannot diverge.
    """

    base_fcff: float
    growth_rate: float
    growth_model: GrowthModel
    terminal_growth_rate: float
    projection_years: int
    wacc: float
    base_wacc: float
    total_debt: float
    cash: float
    shares_outstanding: float
    tax_rate: float
    base_year: int


class DcfOverrides(BaseModel):
    projection_years: int | None = Field(default=None, ge=3, le=10)
    terminal_growth_rate: float | None = Field(default=None, ge=0.0, le=0.10)
    growth_rate: float | None = Field(default=None, ge=-0.50, le=1.00)
    growth_model: GrowthModel | None = None
    wacc: float | None = Field(default=None, ge=0.01, le=0.30)


class SensitivityRequest(DcfOverrides):
    wacc_steps: int = Field(default=5, ge=2, le=11)
    growth_steps: int = Field(default=5, ge=2, le=11)
    wacc_span: float = Field(default=0.02, ge=0.0, le=0.10)
    growth_span: float = Field(default=0.01, ge=0.0, le=0.05)


class SensitivityGrid(BaseModel):
    wacc_values: list[float]
    growth_values: list[float]
    values: list[list[float | None]]
    base_wacc: float
    base_terminal_growth: float


class WaccInput(BaseModel):
    key: str
    label: str
    value: float | None
    source: str
    detail: str | None = None


class WaccBreakdown(BaseModel):
    ticker: str
    wacc: float
    cost_of_equity: float | None = None
    cost_of_debt: float | None = None
    weight_equity: float | None = None
    weight_debt: float | None = None
    market_cap: float | None = None
    price: float | None = None
    as_of: str | None = None
    inputs: list[WaccInput] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)


class ProjectionYear(BaseModel):
    year: int
    fcff: float
    discount_factor: float
    present_value: float


class ValuationSummary(BaseModel):
    terminal_value: float
    present_value_terminal: float
    enterprise_value: float
    total_debt: float
    cash_and_equivalents: float
    net_debt: float
    equity_value: float
    shares_outstanding: float
    value_per_share: float


class ValuationResult(BaseModel):
    ticker: str
    company_name: str
    cik: str
    filing: FilingInfo
    history: list[YearFinancials]
    assumptions: Assumptions
    projection: list[ProjectionYear]
    valuation: ValuationSummary
    engine: EngineInputs | None = None
    overrides_applied: list[str] = Field(default_factory=list)
    flags: list[str]
    sources: list[str]
    source_facts: list[SourceFact] = Field(default_factory=list)
    disclaimer: str


class FilingBlock(BaseModel):
    index: int
    section: str
    text: str


class FilingSection(BaseModel):
    id: str
    label: str
    block: int


class ClaimNode(BaseModel):
    id: str
    statement: str
    kind: str | None = None
    quote: str | None = None
    section: str | None = None
    block: int | None = None
    start: int | None = None
    end: int | None = None
    verified: bool = False
    confidence: str | None = None
    children: list["ClaimNode"] = Field(default_factory=list)


class FilingAnalysis(BaseModel):
    ticker: str
    company_name: str
    accession: str
    document_url: str
    document_view_url: str
    filed: str
    fiscal_year_end: str
    sections: list[FilingSection]
    claims: list[ClaimNode]
    blocks: list[FilingBlock]
    flags: list[str] = Field(default_factory=list)
    cached: bool = False


class TickerSuggestion(BaseModel):
    ticker: str
    name: str
    cik: str
    pilot: bool


class TickerSearchResponse(BaseModel):
    query: str
    results: list[TickerSuggestion]
    total: int


class ChatResponse(BaseModel):
    reply: str
    valuation: ValuationResult | None = None


class ErrorResponse(BaseModel):
    error: str
    ticker: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    llm_model: str
    llm_configured: bool
    supported_tickers: list[str]
    extra: dict[str, Any] | None = None


ClaimNode.model_rebuild()
