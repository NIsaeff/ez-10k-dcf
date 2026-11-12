from typing import Any, Literal

from pydantic import BaseModel, Field

ChatRole = Literal["user", "assistant", "system"]


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
    growth_source: str
    fcff_base: float
    fcff_base_source: str
    share_count_source: str
    net_debt_treatment: str


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
    flags: list[str]
    sources: list[str]
    source_facts: list[SourceFact] = Field(default_factory=list)
    disclaimer: str


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
