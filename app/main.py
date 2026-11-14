import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import llm
from app.config import settings
from app.schemas import (
    ChatRequest,
    ChatResponse,
    DcfOverrides,
    ErrorResponse,
    HealthResponse,
    SensitivityGrid,
    SensitivityRequest,
    TickerSearchResponse,
    TickerSuggestion,
    ValuationResult,
    WaccBreakdown,
)
from app.services import dcf, edgar, financials, market, valuation, wacc
from app.services.financials import InsufficientData
from app.services.valuation import (
    SUPPORTED_TICKERS,
    WACC_DEFAULTS,
    InvalidAssumptions,
    UnsupportedTicker,
)

app = FastAPI(title=settings.project_name)


def _last_user_message(payload: ChatRequest) -> str:
    for message in reversed(payload.messages):
        if message.role == "user":
            return message.content
    return payload.messages[-1].content


def _detect_ticker(text: str) -> str | None:
    supported = set(SUPPORTED_TICKERS)
    for token in re.findall(r"\b[A-Za-z]{1,5}\b", text):
        candidate = token.upper()
        if candidate in supported:
            return candidate
    return None


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm_model=settings.llm_model,
        llm_configured=bool(settings.openai_api_key),
        supported_tickers=SUPPORTED_TICKERS,
    )


def _valuation_or_error(
    ticker: str,
    overrides: DcfOverrides | None = None,
    *,
    allow_any: bool = False,
) -> ValuationResult | JSONResponse:
    """Map engine failures onto the documented error envelope."""
    try:
        return valuation.analyze(ticker, overrides, allow_any=allow_any)
    except UnsupportedTicker:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="unsupported_ticker",
                ticker=ticker.upper(),
                detail=f"Supported tickers: {', '.join(SUPPORTED_TICKERS)}",
            ).model_dump(),
        )
    except InvalidAssumptions as exc:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="invalid_assumptions",
                ticker=ticker.upper(),
                detail=exc.detail,
            ).model_dump(),
        )
    except InsufficientData as exc:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="insufficient_data",
                ticker=exc.ticker,
                missing_fields=exc.missing_fields,
            ).model_dump(),
        )
    except Exception as exc:  # noqa: BLE001 - map upstream failures to 502
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error="upstream_error",
                ticker=ticker.upper(),
                detail=f"{type(exc).__name__}: {exc}",
            ).model_dump(),
        )


@app.get("/api/tickers", response_model=TickerSearchResponse)
def tickers(q: str = "", limit: int = 20):
    """Search the SEC ticker universe. Empty query returns the pilot list."""
    bounded = max(1, min(limit, 50))
    results = edgar.search_tickers(q, limit=bounded, pilots=SUPPORTED_TICKERS)
    return TickerSearchResponse(
        query=q,
        results=[TickerSuggestion(**row) for row in results],
        total=len(results),
    )


@app.post("/api/analyze/{ticker}", response_model=ValuationResult)
def analyze_ticker(ticker: str):
    return _valuation_or_error(ticker)


@app.post("/api/dcf/{ticker}", response_model=ValuationResult)
def dcf_recalculate(ticker: str, overrides: DcfOverrides | None = None):
    """Re-run the engine with assumption overrides (wizard recalc)."""
    return _valuation_or_error(ticker, overrides, allow_any=True)


@app.post("/api/dcf/{ticker}/sensitivity", response_model=SensitivityGrid)
def dcf_sensitivity(ticker: str, request: SensitivityRequest | None = None):
    payload = request or SensitivityRequest()
    result = _valuation_or_error(ticker, payload, allow_any=True)
    if not isinstance(result, ValuationResult):
        return result
    if result.engine is None:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error="engine_unavailable",
                ticker=ticker.upper(),
            ).model_dump(),
        )

    engine = result.engine
    wacc_values, growth_values, values = dcf.sensitivity_grid(
        base_fcff=engine.base_fcff,
        growth_rate=engine.growth_rate,
        growth_model=engine.growth_model,
        terminal_growth_rate=engine.terminal_growth_rate,
        base_year=engine.base_year,
        years=engine.projection_years,
        wacc=engine.wacc,
        total_debt=engine.total_debt,
        cash_and_equivalents=engine.cash,
        shares_outstanding=engine.shares_outstanding,
        wacc_steps=payload.wacc_steps,
        growth_steps=payload.growth_steps,
        wacc_span=payload.wacc_span,
        growth_span=payload.growth_span,
    )
    return SensitivityGrid(
        wacc_values=wacc_values,
        growth_values=growth_values,
        values=values,
        base_wacc=engine.wacc,
        base_terminal_growth=engine.terminal_growth_rate,
    )


@app.get("/api/wacc/{ticker}", response_model=WaccBreakdown)
def wacc_breakdown(ticker: str):
    ticker = ticker.upper().strip()

    try:
        company = financials.load_company(ticker)
    except KeyError:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="unsupported_ticker",
                ticker=ticker,
                detail="Ticker not found in SEC company_tickers.json",
            ).model_dump(),
        )
    except InsufficientData as exc:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="insufficient_data",
                ticker=exc.ticker,
                missing_fields=exc.missing_fields,
            ).model_dump(),
        )
    except Exception as exc:  # noqa: BLE001 - map upstream failures to 502
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error="upstream_error",
                ticker=ticker,
                detail=f"{type(exc).__name__}: {exc}",
            ).model_dump(),
        )

    return wacc.build_wacc(
        company,
        market.market_inputs(ticker),
        fallback_wacc=WACC_DEFAULTS.get(ticker, valuation.GENERIC_WACC),
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    text = _last_user_message(payload)
    ticker = _detect_ticker(text)

    if ticker:
        try:
            result = valuation.analyze(ticker)
        except InsufficientData as exc:
            return ChatResponse(
                reply=(
                    f"I couldn't build a valuation for {ticker}: missing "
                    f"{', '.join(exc.missing_fields)} in the latest filing."
                )
            )
        except Exception as exc:  # noqa: BLE001 - chat stays 200 with a friendly reply
            return ChatResponse(
                reply=(
                    f"I couldn't fetch or value {ticker} right now "
                    f"({type(exc).__name__}). Try again in a moment."
                )
            )
        return ChatResponse(reply=llm.narrate_valuation(result), valuation=result)

    try:
        reply = llm.chat_reply(
            [message.model_dump() for message in payload.messages]
        )
    except Exception:  # noqa: BLE001 - chat fallback
        reply = (
            "I can value a supported ticker from its latest 10-K. "
            f"Try: 'value KO'. Supported: {', '.join(SUPPORTED_TICKERS)}."
        )
    return ChatResponse(reply=reply)


if settings.frontend_dist.is_dir():
    assets_dir = settings.frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        """Serve built files, and index.html for client-side routes.

        Registered last so every API route wins. Anything with a file extension
        that is not on disk returns 404 instead of HTML, which keeps a missing
        script from looking like a successful page load.
        """
        root = settings.frontend_dist.resolve()

        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)

        candidate = (root / full_path).resolve()
        if candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)

        if Path(full_path).suffix:
            raise HTTPException(status_code=404)

        return FileResponse(root / "index.html")

else:

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index() -> str:
        return (
            "<p>Frontend not built. Run "
            "<code>cd frontend &amp;&amp; bun run build</code>.</p>"
        )
