"""Entidade IncomeEvent — histórico/calendário de proventos (Sprint 23.2).

Proventos são EVENTOS/HISTÓRICO, nunca estado atual de carteira — por
isso vivem numa tabela própria, nunca dentro de `positions`. Um evento
pode ou não ter `ticker`/`asset_id` (ex.: o agregado mensal por carteira
do Dividendos.me não é quebrado por ativo — ver `income_parser.py`).

Fonte principal hoje: Dividendos.me, com um teto de dado real e
documentado (ver docs/DIVIDENDOS_ME_INTEGRATION.md): não há evento
individual por ativo com data+tipo+valor-por-cota disponível na conta
investigada — só (a) total mensal agregado por carteira (BR/USD),
(b) calendário futuro por ativo (status "anunciado", não realizado) e,
fora desta tabela, (c) um total acumulado all-time por ticker (ver
Extrato) que NÃO é gravado aqui para não colidir/duplicar com o
agregado mensal.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.database.base import Base, TimestampMixin

# Vocabulário fechado de tipo de evento — "outro" cobre o agregado mensal
# por carteira (que não corresponde a um único tipo) e qualquer provento
# que o parser não conseguiu classificar com segurança.
INCOME_EVENT_TYPES = ("dividendo", "jcp", "rendimento_fii", "amortizacao", "outro")

# "recebido": já pago (agregado mensal, meses passados/atual);
# "provisionado"/"anunciado": já comunicado pela empresa mas ainda não
# pago (calendário futuro do Dividendos.me); "estimado": projeção sem
# confirmação oficial — não usado nesta sprint (nunca inventamos estimativa).
INCOME_EVENT_STATUSES = ("recebido", "provisionado", "anunciado", "estimado")


class IncomeEvent(Base, TimestampMixin):
    """Um evento de provento/dividendo — histórico (recebido) ou agendado
    (anunciado), nunca um estado de carteira."""

    __tablename__ = "income_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id"), index=True, nullable=False
    )
    # Nullable de propósito: o agregado mensal por carteira (Análise do
    # Dividendos.me) não é quebrado por ativo.
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), index=True, nullable=True)
    ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Origem + diferenciador de sub-fonte (ex.: "dividendos_me:income_monthly:brasil"
    # vs "dividendos_me:income_calendar") — ver `income_parser.py`.
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    ex_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    declared_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    amount_per_share: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    amount_total: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # Payload bruto já sanitizado (nunca HTML, nunca dado sensível) usado
    # para diagnóstico/auditoria — ex.: {"kind": "aggregate_monthly_by_wallet",
    # "wallet": "brasil", "year": 2026, "month": 3}.
    raw_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<IncomeEvent id={self.id} ticker={self.ticker!r} "
            f"event_type={self.event_type!r} status={self.status!r} "
            f"amount_total={self.amount_total}>"
        )
