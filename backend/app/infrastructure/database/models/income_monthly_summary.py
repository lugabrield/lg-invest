"""Entidade IncomeMonthlySummary — histórico mensal agregado de proventos
(Sprint 23.3).

Correção de modelagem: a aba "Central de Proventos" -> "Análise" do
Dividendos.me mostra uma tabela ANO x MÊS por carteira (BR/Dólar) — um
RESUMO agregado, nunca um evento individual (não tem ticker nem data
exata de pagamento). Antes da Sprint 23.3, esse resumo era forçado no
formato de `IncomeEvent` (com um `payment_date` de dia 1 inventado só
para caber no schema) — isso misturava dois conceitos diferentes na
mesma tabela. Esta entidade separa definitivamente: `income_events`
guarda só o calendário futuro por ticker (aba "Próximos Dividendos");
`income_monthly_summaries` guarda só o resumo mensal por carteira.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.database.base import Base, TimestampMixin

# "recebido": mês já fechado (passado ou mês atual — o Dividendos.me só
# preenche o valor quando o provento já caiu); "anunciado": mês futuro
# dentro do ano exibido na tabela, já comunicado mas ainda não pago.
INCOME_MONTHLY_STATUSES = ("recebido", "anunciado")


class IncomeMonthlySummary(Base, TimestampMixin):
    """Um resumo mensal agregado por carteira — nunca um evento por
    ticker (isso é `IncomeEvent`). Uma linha por
    portfolio_id+wallet_name+year+month+currency+source."""

    __tablename__ = "income_monthly_summaries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id"), index=True, nullable=False
    )

    # Rótulo exato exibido no seletor de carteira do Dividendos.me (ex.:
    # "Carteira (B3)", "Carteira Dolar") — preservado como veio, nunca
    # normalizado para um enum fechado (o próprio site pode adicionar
    # novas carteiras no futuro).
    wallet_name: Mapped[str] = mapped_column(String(60), nullable=False)

    year: Mapped[int] = mapped_column(nullable=False)
    month: Mapped[int] = mapped_column(nullable=False)  # 1-12

    amount_total: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # Origem (mesma convenção do Sprint 23): diferencia carteira BR de
    # internacional dentro do agregado mensal — ver `income_parser.py`.
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    # Vêm prontos da própria tabela "Análise" (colunas TOTAL/MÉDIA da
    # linha do ano) — nunca recalculados aqui, para nunca divergir do que
    # o Dividendos.me mostra. Nullable porque a coluna pode não ter sido
    # capturada em alguma extração antiga/parcial.
    annual_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    annual_average: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    # Payload bruto já sanitizado (nunca HTML, nunca dado sensível) usado
    # para diagnóstico/auditoria.
    raw_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<IncomeMonthlySummary id={self.id} wallet_name={self.wallet_name!r} "
            f"year={self.year} month={self.month} amount_total={self.amount_total} "
            f"status={self.status!r}>"
        )
