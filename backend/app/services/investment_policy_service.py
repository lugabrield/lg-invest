"""Serviço de Investment Policy (Sprint 24, Fase 3).

Não é uma engine — só orquestra leitura/escrita de `InvestmentPolicy`
(banco). Os valores default aplicados na primeira leitura (quando a
carteira ainda não tem uma política salva) são um PONTO DE PARTIDA
sensato baseado no perfil descrito pelo usuário (investidor jovem,
horizonte 50+ anos, Buy and Hold, tolerância moderada/alta a
volatilidade, internacionalização crescente) — nunca uma recomendação
financeira, e sempre editável em Configurações. A LG INVEST não é uma
consultoria e não afirma que estes números são "ideais" para ninguém.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models.investment_policy import InvestmentPolicy
from backend.app.infrastructure.repositories.investment_policy_repository import (
    InvestmentPolicyRepository,
)
from backend.app.schemas.investment_policy import InvestmentPolicyUpdate, InvestmentPolicyView

# Defaults de primeira execução — ver docstring do módulo. Nenhum destes
# valores é usado por uma engine "por baixo dos panos": eles só existem
# aqui, na primeira vez que a política é lida, e viram uma linha real e
# editável no banco a partir daí.
_DEFAULT_NOTES = (
    "Política inicial sugerida com base no perfil descrito: investidor jovem, "
    "horizonte de longuíssimo prazo (50+ anos), filosofia Buy and Hold, tolerância "
    "moderada/alta a volatilidade, intenção de aumentar exposição internacional ao "
    "longo do tempo, FIIs úteis para renda mas sem dependência excessiva de renda "
    "imobiliária local, Bitcoin pequeno e limitado por peso máximo. Isto NÃO é uma "
    "recomendação financeira — é só um ponto de partida editável."
)

_DEFAULTS: dict[str, object] = {
    "investor_profile": "Buy and Hold - crescimento de longuíssimo prazo",
    "horizon_years": 50,
    "base_currency": "BRL",
    "risk_tolerance": "moderado-alto",
    "max_asset_weight": Decimal("0.15"),
    "max_crypto_weight": Decimal("0.05"),
    "target_international_min": Decimal("0.30"),
    "target_international_max": Decimal("0.60"),
    "target_fii_max": Decimal("0.15"),
    "target_brazil_equity": Decimal("0.25"),
    "target_us_equity": Decimal("0.30"),
    "target_etf": Decimal("0.15"),
    "target_reit": Decimal("0.05"),
    "target_fixed_income": Decimal("0.10"),
    "rebalance_threshold": Decimal("0.05"),
    "monthly_contribution_default": Decimal("1000.00"),
    "notes": _DEFAULT_NOTES,
}


def _to_view(policy: InvestmentPolicy) -> InvestmentPolicyView:
    return InvestmentPolicyView(
        portfolio_id=policy.portfolio_id,
        investor_profile=policy.investor_profile,
        horizon_years=policy.horizon_years,
        base_currency=policy.base_currency,
        risk_tolerance=policy.risk_tolerance,
        max_asset_weight=policy.max_asset_weight,
        max_crypto_weight=policy.max_crypto_weight,
        target_international_min=policy.target_international_min,
        target_international_max=policy.target_international_max,
        target_fii_max=policy.target_fii_max,
        target_brazil_equity=policy.target_brazil_equity,
        target_us_equity=policy.target_us_equity,
        target_etf=policy.target_etf,
        target_reit=policy.target_reit,
        target_fixed_income=policy.target_fixed_income,
        rebalance_threshold=policy.rebalance_threshold,
        monthly_contribution_default=policy.monthly_contribution_default,
        notes=policy.notes,
    )


class InvestmentPolicyService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = InvestmentPolicyRepository(db)

    def get_or_create(self, portfolio_id: int) -> InvestmentPolicyView:
        policy = self.repo.get_by_portfolio(portfolio_id)
        if policy is None:
            policy = InvestmentPolicy(portfolio_id=portfolio_id, **_DEFAULTS)
            policy = self.repo.create(policy)
        return _to_view(policy)

    def update(self, portfolio_id: int, update: InvestmentPolicyUpdate) -> InvestmentPolicyView:
        policy = self.repo.get_by_portfolio(portfolio_id)
        if policy is None:
            policy = InvestmentPolicy(portfolio_id=portfolio_id, **_DEFAULTS)
            policy = self.repo.create(policy)

        data = update.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(policy, field, value)

        policy = self.repo.update(policy)
        return _to_view(policy)
