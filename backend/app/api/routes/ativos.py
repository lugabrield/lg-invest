"""Rotas de Ativos (v1.1, Fase 6 — ver docs/API_CONTRACT.md).

Camada fina sobre os mesmos services que `pages_impl/ativos.py` já usa:
`LGScoreService`, `ConvictionScoreService`, `DataQualityService`,
`FundamentalsAnalysisService`, `ValuationService`, `ValuationServiceV2`,
`IncomeRealEstateService`, `PortfolioAdequacyService`,
`TrapDetectionService`, `DataCoverageService`, `FundamentalsService`,
`FundamentalsImportService`, `MarketDataService`. Nenhuma regra nova —
só rotas HTTP + os schemas de composição (Fase 6: `AssetRowView`,
`AssetDetailBundle`, `asset_actions.py`).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_portfolio_id
from backend.app.infrastructure.database.models.price import Price
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.infrastructure.repositories.price_repository import PriceRepository
from backend.app.schemas.asset_actions import (
    CollectFundamentalsBatchResponse,
    CollectFundamentalsResponse,
    FundamentalsImportResultView,
    ManualFlagRequest,
    ManualFlagResponse,
    ManualPriceRequest,
    ManualPriceResponse,
    RefreshPriceResponse,
)
from backend.app.schemas.asset_detail import AssetDetailBundle
from backend.app.schemas.asset_row import AssetRowView
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.services.conviction_score_service import ConvictionScoreService
from backend.app.services.data_coverage_service import DataCoverageService
from backend.app.services.data_quality_service import DataQualityService
from backend.app.services.fundamentals_analysis_service import FundamentalsAnalysisService
from backend.app.services.fundamentals_import_service import FundamentalsImportService
from backend.app.services.fundamentals_service import FundamentalsService
from backend.app.services.income_real_estate_service import IncomeRealEstateService
from backend.app.services.lg_score_service import LGScoreService
from backend.app.services.market_data_service import MarketDataService
from backend.app.services.portfolio_adequacy_service import PortfolioAdequacyService
from backend.app.services.trap_detection_service import TrapDetectionService
from backend.app.services.valuation_service import ValuationService
from backend.app.services.valuation_v2_service import ValuationServiceV2

router = APIRouter(tags=["ativos"])

_ALLOWED_IMPORT_SUFFIXES = {".csv", ".xlsx", ".xls"}

# Mesma classificação de `pages_impl/ativos.py::_STOCK_CLASSES` etc. —
# duplicada deliberadamente (não importada de dentro da UI Streamlit).
_STOCK_CLASSES = ("stock",)
_INCOME_REAL_ESTATE_CLASSES = ("fii", "reit")
_NO_TRADITIONAL_VALUATION_CLASSES = ("etf", "crypto", "bond")

# Mesmos campos de `backend/app/services/fundamentals_service.py` — ver
# também `FundamentalSnapshotResult._RATIO_FIELDS` (privado ao schema,
# duplicado aqui pela mesma razão que a UI Streamlit já duplicava).
_FUNDAMENTAL_FIELDS = (
    "roe",
    "roa",
    "net_margin",
    "ebitda_margin",
    "revenue",
    "net_income",
    "ebitda",
    "ebit",
    "free_cash_flow",
    "net_debt",
    "debt_to_ebitda",
    "pe_ratio",
    "pb_ratio",
    "ev_ebitda",
    "dividend_yield",
    "payout_ratio",
    "eps",
    "revenue_per_share",
    "beta",
    "market_cap",
    "enterprise_value",
    "forward_pe",
    "operating_margin",
    "total_debt",
    "total_cash",
    "operating_cash_flow",
    "gross_profit",
    "shares_outstanding",
)


def _price_status(asset, latest_price) -> str:
    if asset.is_manual:
        return "manual"
    if latest_price is None:
        return "missing"
    if latest_price.source == "manual":
        return "manual"
    return "automatic"


def _snapshot_result(ticker: str, snapshot) -> FundamentalSnapshotResult:
    return FundamentalSnapshotResult(
        ticker=ticker,
        period_end=snapshot.period_end,
        source=snapshot.source,
        collected_at=snapshot.updated_at,
        **{field: getattr(snapshot, field) for field in _FUNDAMENTAL_FIELDS},
    )


@router.get("/ativos", response_model=list[AssetRowView])
def list_ativos(db: Session = Depends(get_db)) -> list[AssetRowView]:
    assets = AssetRepository(db).list_all()
    prices = PriceRepository(db)
    rows = []
    for asset in assets:
        latest = prices.get_latest(asset.id)
        rows.append(
            AssetRowView(
                ticker=asset.ticker,
                name=asset.name,
                asset_class=asset.asset_class,
                country=asset.country,
                currency=asset.currency,
                sector=asset.sector,
                price=str(latest.close) if latest is not None else None,
                price_status=_price_status(asset, latest),
                is_manual=asset.is_manual,
                updated_at=latest.updated_at.isoformat() if latest and latest.updated_at else None,
            )
        )
    return rows


@router.get("/ativos/{ticker}", response_model=AssetDetailBundle)
def get_ativo_detail(
    ticker: str,
    portfolio_id: int = Depends(get_portfolio_id),
    db: Session = Depends(get_db),
) -> AssetDetailBundle:
    asset = AssetRepository(db).get_by_ticker(ticker)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Ativo '{ticker}' não encontrado.")

    lg_score = LGScoreService(db).score_ticker(ticker)
    conviction = ConvictionScoreService(db).score_ticker(ticker)
    data_quality = DataQualityService(db).evaluate_ticker(
        ticker, asset.id, asset.asset_class, is_manual=asset.is_manual
    )

    latest_snapshot = FundamentalsRepository(db).get_latest(asset.id)
    fundamentals = _snapshot_result(ticker, latest_snapshot) if latest_snapshot else None
    fundamentals_analysis = FundamentalsAnalysisService(db).analyze_ticker(ticker)
    legacy_valuation = ValuationService(db).evaluate_ticker(ticker)

    valuation_v2 = None
    income_real_estate = None
    adequacy = None
    if asset.asset_class in _STOCK_CLASSES:
        valuation_v2 = ValuationServiceV2(db).evaluate_ticker(ticker)
    elif asset.asset_class in _INCOME_REAL_ESTATE_CLASSES:
        income_real_estate = IncomeRealEstateService(db).evaluate_ticker(ticker)
    elif asset.asset_class in _NO_TRADITIONAL_VALUATION_CLASSES:
        adequacy = PortfolioAdequacyService(db).evaluate_ticker(ticker, portfolio_id)

    trap_detection = TrapDetectionService(db).evaluate_ticker(ticker)
    coverage = DataCoverageService(db).evaluate_ticker(ticker)

    return AssetDetailBundle(
        ticker=asset.ticker,
        name=asset.name,
        asset_class=asset.asset_class,
        currency=asset.currency,
        is_manual=asset.is_manual,
        lg_score=lg_score,
        conviction=conviction,
        data_quality=data_quality,
        fundamentals=fundamentals,
        fundamentals_analysis=fundamentals_analysis,
        legacy_valuation=legacy_valuation,
        valuation_v2=valuation_v2,
        income_real_estate=income_real_estate,
        adequacy=adequacy,
        trap_detection=trap_detection,
        coverage=coverage,
    )


@router.patch("/ativos/{ticker}/manual-flag", response_model=ManualFlagResponse)
def set_manual_flag(
    ticker: str, payload: ManualFlagRequest, db: Session = Depends(get_db)
) -> ManualFlagResponse:
    asset = AssetRepository(db).get_by_ticker(ticker)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Ativo '{ticker}' não encontrado.")
    asset.is_manual = payload.is_manual
    db.commit()
    return ManualFlagResponse(ticker=asset.ticker, is_manual=asset.is_manual)


@router.post("/ativos/{ticker}/manual-price", response_model=ManualPriceResponse)
def set_manual_price(
    ticker: str, payload: ManualPriceRequest, db: Session = Depends(get_db)
) -> ManualPriceResponse:
    from datetime import date

    if payload.price <= 0:
        raise HTTPException(status_code=422, detail="O preço deve ser maior que zero.")

    asset = AssetRepository(db).get_by_ticker(ticker)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Ativo '{ticker}' não encontrado.")

    price_repo = PriceRepository(db)
    today = date.today()
    existing = price_repo.get_by_asset_and_date(asset.id, today)
    if existing is not None:
        existing.close = payload.price
        existing.source = "manual"
        db.commit()
    else:
        price_repo.create(
            Price(asset_id=asset.id, date=today, close=payload.price, source="manual")
        )

    return ManualPriceResponse(ticker=asset.ticker, price=str(payload.price))


@router.post("/ativos/{ticker}/refresh-price", response_model=RefreshPriceResponse)
def refresh_price(ticker: str, db: Session = Depends(get_db)) -> RefreshPriceResponse:
    from backend.app.etl.providers.yahoo_provider import YahooFinanceProvider

    try:
        result = MarketDataService(db, YahooFinanceProvider()).update_asset_prices(ticker)
    except Exception as exc:  # noqa: BLE001 - nunca vazar detalhe de exceção não prevista
        raise HTTPException(
            status_code=502,
            detail="Não foi possível atualizar o preço agora — sem internet ou fonte indisponível.",
        ) from exc
    return RefreshPriceResponse(result=result)


@router.post("/ativos/{ticker}/collect-fundamentals", response_model=CollectFundamentalsResponse)
def collect_fundamentals(ticker: str, db: Session = Depends(get_db)) -> CollectFundamentalsResponse:
    from backend.app.etl.providers.yahoo_fundamentals_provider import YahooFundamentalsProvider

    try:
        result = FundamentalsService(db, YahooFundamentalsProvider()).collect_for_asset(ticker)
    except Exception as exc:  # noqa: BLE001 - nunca vazar detalhe de exceção não prevista
        raise HTTPException(
            status_code=502,
            detail="Não foi possível coletar fundamentos agora — sem internet ou fonte indisponível.",
        ) from exc
    return CollectFundamentalsResponse(result=result)


@router.post("/ativos/collect-fundamentals-batch", response_model=CollectFundamentalsBatchResponse)
def collect_fundamentals_batch(db: Session = Depends(get_db)) -> CollectFundamentalsBatchResponse:
    from backend.app.etl.providers.yahoo_fundamentals_provider import YahooFundamentalsProvider

    try:
        result = FundamentalsService(db, YahooFundamentalsProvider()).collect_all()
    except Exception as exc:  # noqa: BLE001 - nunca vazar detalhe de exceção não prevista
        raise HTTPException(
            status_code=502,
            detail="Não foi possível coletar fundamentos agora — sem internet ou fonte indisponível.",
        ) from exc
    return CollectFundamentalsBatchResponse(result=result)


@router.post("/ativos/fundamentals-import", response_model=FundamentalsImportResultView)
async def import_fundamentals(
    file: UploadFile,
    overwrite: bool = False,
    portfolio_id: int = Depends(get_portfolio_id),
    db: Session = Depends(get_db),
) -> FundamentalsImportResultView:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_IMPORT_SUFFIXES:
        raise HTTPException(
            status_code=422,
            detail=f"Formato não suportado ({suffix or 'sem extensão'}). Use .csv, .xlsx ou .xls.",
        )

    contents = await file.read()
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        result = FundamentalsImportService(db).import_file(
            tmp_path, portfolio_id, confirm_overwrite=overwrite
        )
    finally:
        if tmp_path is not None:
            Path(tmp_path).unlink(missing_ok=True)

    return FundamentalsImportResultView(**result.as_dict())
