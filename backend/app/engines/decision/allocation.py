"""Distribuição do aporte entre ativos selecionados (Volume 7, seção 7).

Regras:
- Seleciona os melhores ativos por score de compra, limitado pelo nº
  recomendado para a faixa do aporte.
- Distribui proporcionalmente ao score de compra.
- Respeita mínimo de 10% e máximo de 50% por ativo.
- A soma alocada nunca ultrapassa o aporte.

A distribuição usa centavos (Decimal com 2 casas) e ajusta o
arredondamento na última posição para que a soma feche exatamente.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from backend.app.engines.decision.inputs import DecisionConfig
from backend.app.engines.decision.scoring import BuyScore

_CENTS = Decimal("0.01")


@dataclass
class Allocation:
    ticker: str
    amount: Decimal
    buy_score: Decimal


def _round_down_cents(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_DOWN)


def select_and_distribute(
    scores: list[BuyScore],
    amount: Decimal,
    config: DecisionConfig,
    new_asset_tickers: frozenset[str] = frozenset(),
) -> list[Allocation]:
    """Seleciona ativos e distribui o aporte respeitando os limites.

    `new_asset_tickers` (Sprint 25, Parte 2.5): tickers vindos da
    Watchlist/Radar que ainda não são posição — recebem o teto mais
    conservador `config.max_new_asset_weight` em vez do teto padrão
    `config.max_single_weight`. Vazio por padrão: nenhum comportamento
    muda para quem não usa `allow_watchlist_candidates`.
    """
    if amount <= 0 or not scores:
        return []

    # Ordena por score desc e limita pela faixa do aporte.
    ordered = sorted(scores, key=lambda s: s.score, reverse=True)
    max_assets = config.assets_for_amount(amount)
    selected = ordered[:max_assets]

    # Remove scores não-positivos (não há razão para aportar).
    selected = [s for s in selected if s.score > 0]
    if not selected:
        return []

    # Quantos ativos cabem respeitando o mínimo de 10%?
    # Com mínimo de 10%, no máximo 1/min_single_weight ativos.
    max_by_min = int(Decimal("1") / config.min_single_weight)
    if len(selected) > max_by_min:
        selected = selected[:max_by_min]

    total_score = sum((s.score for s in selected), start=Decimal("0"))
    if total_score <= 0:
        return []

    # Pesos proporcionais ao score, depois ajustados para respeitar os
    # limites mínimo (10%) e máximo (50%, ou o teto reduzido de ativo
    # novo) por ativo sem violá-los.
    raw_weights = {s.ticker: (s.score / total_score) for s in selected}
    final_weights = _apply_min_max(raw_weights, config, new_asset_tickers)

    allocations: list[Allocation] = []
    running = Decimal("0")
    for i, s in enumerate(selected):
        if i < len(selected) - 1:
            value = _round_down_cents(amount * final_weights[s.ticker])
        else:
            # Última posição recebe o resto, mas nunca acima do teto
            # (o teto de ativo novo, se aplicável, prevalece).
            cap = _round_down_cents(amount * _hi_for(s.ticker, config, new_asset_tickers))
            value = min(_round_down_cents(amount - running), cap)
        running += value
        allocations.append(Allocation(ticker=s.ticker, amount=value, buy_score=s.score))

    return allocations


def _hi_for(ticker: str, config: DecisionConfig, new_asset_tickers: frozenset[str]) -> Decimal:
    """Teto máximo de peso para um ticker: o teto padrão, ou o teto
    reduzido de ativo novo da Watchlist quando aplicável — nunca o maior
    dos dois (o teto de ativo novo é sempre mais restritivo)."""
    if ticker in new_asset_tickers:
        return min(config.max_single_weight, config.max_new_asset_weight)
    return config.max_single_weight


def _apply_min_max(
    weights: dict[str, Decimal],
    config: DecisionConfig,
    new_asset_tickers: frozenset[str] = frozenset(),
) -> dict[str, Decimal]:
    """Ajusta pesos para o intervalo [min, teto_por_ativo].

    Diferente de uma renormalização ingênua, aqui o teto máximo é
    inviolável: pesos são limitados ao teto (padrão ou reduzido, para
    ativos novos da Watchlist) e, se a soma ultrapassar 1.0, o excedente
    é cortado (a sobra fica não alocada e é reportada como tal). Pesos
    abaixo do mínimo sobem ao mínimo.
    """
    lo = config.min_single_weight
    hi_by_ticker = {t: _hi_for(t, config, new_asset_tickers) for t in weights}

    clamped = {t: min(hi_by_ticker[t], max(lo, w)) for t, w in weights.items()}
    total = sum(clamped.values(), start=Decimal("0"))

    if total <= Decimal("1"):
        return clamped

    # Soma passou de 1.0: reduz proporcionalmente os pesos que estão
    # acima do mínimo, mantendo o teto de cada ativo, até a soma caber em 1.0.
    excess = total - Decimal("1")
    reducible = {t: w - lo for t, w in clamped.items() if w > lo}
    reducible_total = sum(reducible.values(), start=Decimal("0"))
    if reducible_total <= 0:
        return clamped

    adjusted = dict(clamped)
    for t, room in reducible.items():
        cut = excess * (room / reducible_total)
        adjusted[t] = max(lo, min(hi_by_ticker[t], clamped[t] - cut))
    return adjusted
