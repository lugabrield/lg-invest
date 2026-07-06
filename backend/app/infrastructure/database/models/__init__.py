"""Entidades ORM da LG INVEST.

Importar deste módulo garante que todas as classes sejam registradas
em `Base.metadata` antes de qualquer `create_all()` ou migration
Alembic ser executada.
"""

from backend.app.infrastructure.database.base import Base, TimestampMixin
from backend.app.infrastructure.database.models.asset import ASSET_CLASSES, Asset
from backend.app.infrastructure.database.models.decision_snapshot import DecisionSnapshot
from backend.app.infrastructure.database.models.external_sync_run import (
    SYNC_MODES,
    SYNC_PROVIDERS,
    SYNC_STATUSES,
    ExternalSyncRun,
)
from backend.app.infrastructure.database.models.fundamental_snapshot import (
    FUNDAMENTALS_SOURCES,
    FundamentalSnapshot,
)
from backend.app.infrastructure.database.models.income_event import (
    INCOME_EVENT_STATUSES,
    INCOME_EVENT_TYPES,
    IncomeEvent,
)
from backend.app.infrastructure.database.models.income_monthly_summary import (
    INCOME_MONTHLY_STATUSES,
    IncomeMonthlySummary,
)
from backend.app.infrastructure.database.models.investment_policy import (
    RISK_TOLERANCES,
    InvestmentPolicy,
)
from backend.app.infrastructure.database.models.investment_thesis import (
    THESIS_STATUSES,
    InvestmentThesis,
)
from backend.app.infrastructure.database.models.journal_entry import (
    JOURNAL_ACTIONS,
    JournalEntry,
)
from backend.app.infrastructure.database.models.portfolio import Portfolio
from backend.app.infrastructure.database.models.position import Position
from backend.app.infrastructure.database.models.price import Price
from backend.app.infrastructure.database.models.recommendation import Recommendation
from backend.app.infrastructure.database.models.target_allocation_rule import (
    TARGET_ALLOCATION_DIMENSIONS,
    TargetAllocationRule,
)
from backend.app.infrastructure.database.models.thesis_review import (
    REVIEW_CLASSIFICATIONS,
    ThesisReview,
)
from backend.app.infrastructure.database.models.watchlist_asset import (
    WATCHLIST_STATUSES,
    WatchlistAsset,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "Asset",
    "ASSET_CLASSES",
    "Portfolio",
    "Position",
    "Price",
    "Recommendation",
    "JournalEntry",
    "JOURNAL_ACTIONS",
    "InvestmentThesis",
    "THESIS_STATUSES",
    "ThesisReview",
    "REVIEW_CLASSIFICATIONS",
    "DecisionSnapshot",
    "FundamentalSnapshot",
    "FUNDAMENTALS_SOURCES",
    "ExternalSyncRun",
    "SYNC_PROVIDERS",
    "SYNC_MODES",
    "SYNC_STATUSES",
    "IncomeEvent",
    "INCOME_EVENT_TYPES",
    "INCOME_EVENT_STATUSES",
    "IncomeMonthlySummary",
    "INCOME_MONTHLY_STATUSES",
    "InvestmentPolicy",
    "RISK_TOLERANCES",
    "TargetAllocationRule",
    "TARGET_ALLOCATION_DIMENSIONS",
    "WatchlistAsset",
    "WATCHLIST_STATUSES",
]
