# Correção: moeda de BTC-USD (Sprint 24 — Fase 1)

## O problema

O Dividendos.me extrai a posição de BTC na tela "Criptomoedas → Extrato" com o
símbolo visual "R$" ao lado de cada número (quantidade, preço médio, preço
atual, valor total). A Sprint 23.2 interpretou isso literalmente e gravou
`currency="BRL"` para qualquer posição de cripto.

Isso está errado. Conferindo a conta com dados reais do usuário:

```
quantity        = 0.00584925
current_price   = 63121.45
current_value   = 366.20  (aprox.)

0.00584925 × 63121.45 ≈ 369.18
```

A única forma de essa multiplicação bater com `current_value` é se
`current_price`/`current_value` estiverem em **USD**. Se fossem BRL, o preço
implícito do BTC seria ~18x menor que o preço real de mercado — um valor
absurdo. O símbolo "R$" da tela é só uma escolha de exibição da interface do
Dividendos.me, não uma informação confiável sobre a moeda real dos números.

## Por que isso importava

`backend/app/services/dashboard_view_service.py` converte cada posição para
BRL no patrimônio consolidado assim:

```python
def to_brl(value: Decimal, currency: str) -> Decimal:
    if currency == "USD":
        return value * exchange_rate
    return value
```

Com `currency="BRL"` (o bug), o valor de BTC passava direto por essa função
**sem nunca ser multiplicado pelo câmbio** — o patrimônio em BTC ficava
subavaliado em torno de 5x (dependendo do câmbio USD/BRL do momento), porque
o número já vinha em USD mas era tratado como se já estivesse em BRL.

## A correção

`backend/app/integrations/dividendos_me/parser.py`, função `_normalize_crypto`:
qualquer ticker de cripto normalizado como par `"XXX-USD"` (convenção do
Yahoo Finance, fonte de preço da LG INVEST) tem `currency="USD"`. Isso vale
tanto para `BTC-USD` quanto para qualquer outra criptomoeda ainda não
validada (que continua `review_required=True` por outros motivos, mas com a
moeda já correta).

**Regra geral, não específica de BTC:** a moeda de um ativo cripto é sempre
inferida do próprio ticker/natureza do ativo, nunca do símbolo visual da tela
de origem. Isso é consistente com o resto do parser — ações dos EUA também
não usam o símbolo da tela como fonte de moeda, e sim o país/subgrupo do
ativo.

### Por que nenhuma outra camada precisou mudar

Investigação confirmou que toda a cadeia depende só do campo `currency` de
forma genérica, sem nenhum código específico para "cripto":

- `service.py` (`_apply_sync`, `_consolidate_positions`, `_apply_btc_fallback`):
  só propaga `currency` das posições extraídas para o banco — nunca converte.
- `dashboard_view_service.to_brl()`: já convertia corretamente qualquer
  posição `currency == "USD"` (é assim que ações americanas como VOO sempre
  funcionaram).
- `frontend/streamlit_app/pages_impl/carteira.py` e
  `frontend/streamlit_app/charts/allocation_charts.py`: agrupam
  Brasil/Exterior por `currency == "BRL"` vs. `!= "BRL"` — BTC passa a
  contar corretamente como exposição internacional (USD).
- `frontend/streamlit_app/pages_impl/dashboard.py` (`_international_weight`):
  soma exposição internacional por `currency != "BRL"` — mesmo raciocínio.
- `frontend/streamlit_app/components/tables.py`: exibe `p.currency` cru na
  coluna "Moeda" — passa a mostrar "USD" para BTC-USD automaticamente.

Ou seja: a correção de uma única função (`_normalize_crypto`) é suficiente
para propagar o comportamento certo por toda a plataforma, sem precisar de
nenhum tratamento especial em nenhuma outra camada.

## O que muda na prática

Depois de um novo dry-run/sync do Dividendos.me:

- `BTC-USD` aparece com `currency: "USD"` no preview e na carteira.
- O patrimônio consolidado em BRL passa a incluir o valor de BTC já
  convertido pelo câmbio configurado (igual a qualquer outra posição em USD).
- BTC passa a contar como exposição internacional (moeda estrangeira) nos
  gráficos e métricas de Brasil vs. Exterior — antes ficava incorretamente
  contado como parte da "carteira BRL".

Nenhuma posição existente é apagada ou recriada por essa correção sozinha —
ela só passa a valer a partir do próximo `replace`/`update` via
Dividendos.me (ou pode ser corrigida manualmente hoje, editando o campo
`currency` do ativo `BTC-USD` existente no banco, se o usuário não quiser
esperar pelo próximo sync).

## Testes

- `backend/tests/unit/test_dividendos_me_parser.py`: `_normalize_crypto`
  sempre retorna `currency == "USD"`.
- `backend/tests/unit/test_dividendos_me_client.py`: cards reais de
  "Criptomoedas → Extrato" mapeados com `currency == "USD"`.
- `backend/tests/unit/test_dividendos_me_service.py`: fixtures de
  BTC-USD consistentemente em `"USD"`.
- `backend/tests/unit/test_dashboard_view_service.py`: conversão pelo
  câmbio configurado, regressão-alvo contra a subavaliação antiga, e
  exposição por moeda contando BTC como USD.

## Limitações que continuam

Só `BTC-USD` foi validado ao vivo pelo usuário. Qualquer outra criptomoeda
(par `"XXX-USD"` diferente de BTC) já recebe `currency="USD"` pela mesma
regra geral, mas continua marcada `review_required=True` até ser confirmada
contra uma extração real — comportamento herdado das sprints anteriores,
sem mudança nesta correção.
