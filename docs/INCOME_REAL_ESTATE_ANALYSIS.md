# Análise de Renda Imobiliária — FIIs/REITs (Sprint 26, Fase 4)

## Objetivo e escopo declarado

FIIs e REITs não são analisados como empresas operacionais comuns:
**nunca recebem DCF** (não há reinvestimento de lucro no sentido
societário clássico — a distribuição é o próprio modelo) e **P/L não é
métrica relevante** (lucro contábil de FII costuma ser distorcido por
reavaliação de ativos, não geração de caixa recorrente). A análise gira
em torno de P/VP, Dividend Yield e a **estabilidade** desse yield ao
longo do tempo — um yield alto só é "atrativo" se for consistente com o
histórico do próprio ativo, nunca só porque o número do trimestre é
alto.

Escopo: `asset_class in ("fii", "reit")`. Nunca gera recomendação de
compra/venda.

## Arquitetura

```
IncomeRealEstateService (banco <-> engine)
    -> busca snapshot mais recente + histórico de dividend_yield
    -> IncomeRealEstateEngine.evaluate(...)  # puro, sem I/O
        -> stability.py    (coeficiente de variação do DY histórico)
        -> thresholds.py   (limiares isolados e documentados)
```

## P/VP

Reaproveita as mesmas bandas já usadas por
`engines/valuation/thresholds.py` (Valuation Engine v1) para FII/REIT:
`P/VP <= 0,9` soma ponto (barato); `P/VP >= 1,1` subtrai ponto (caro).

## Dividend Yield

Faixa de referência para o mercado brasileiro de FIIs: `DY >= 8%`
soma ponto (atrativo); `DY < 5%` subtrai ponto (baixo).

## Estabilidade do DY (`stability.py`)

Mede a consistência do yield histórico do PRÓPRIO ativo via
**coeficiente de variação** (desvio padrão / média) da série de
`dividend_yield` — nunca compara com pares do setor (não coletado).

- Menos de `MIN_PERIODS_FOR_STABILITY = 2` períodos com dado positivo
  → `"indeterminado"`, com motivo explícito.
- Coeficiente de variação `>= 0,35` → `"instável"` (subtrai ponto,
  gera aviso: "o número do período mais recente pode não representar
  a renda recorrente esperada").
- Caso contrário → `"estável"`.

## Score agregado e classificação

Soma simples dos três sinais acima (`-1` a `+2` pontos possíveis):
`score >= 2` → `"atrativo"`; `score <= -1` → `"pouco_atrativo"`;
caso contrário → `"neutro"`. P/VP e DY ambos ausentes → resultado
indeterminado com a mensagem literal "Dados insuficientes para
estimar valor justo com confiança."

## Confiança

`"alta"` (só FIIs) exige P/VP + DY disponíveis **e** estabilidade
calculável (não indeterminada). REITs nunca atingem `"alta"` — no
máximo `"média"` — por causa da limitação de FFO/AFFO abaixo. Com
apenas um dos dois métodos disponível: `"média"` para FII, `"baixa"`
para REIT. Nenhum método disponível: `"baixa"`.

## REITs e a limitação de FFO/AFFO

Idealmente, REITs (EUA) seriam analisados via FFO/AFFO (Funds/Adjusted
Funds From Operations), não via lucro contábil — mas este projeto
ainda não coleta esses campos (não expostos com confiança pelo
yfinance sem mapeamento dedicado). Em vez de aproximar FFO a partir de
um número que não é FFO (o que violaria "nunca inventar dado"), REITs
usam a mesma leitura de P/VP + DY que os FIIs, com **aviso explícito**
da limitação sempre emitido e confiança nunca `"alta"` — a estratégia
"melhor esforço + confiança baixa" aprovada para esta sprint.

## Arquivos

`engines/income_real_estate/{thresholds,stability,engine}.py`,
`schemas/income_real_estate.py`, `services/income_real_estate_service.py`.

## Integração com o Trap Detection Engine

`dy_own_history_average` calculado aqui é reaproveitado diretamente
pela FII Yield Trap (`docs/TRAP_DETECTION_ENGINE.md`) — nunca
recalculado duas vezes.

## UI (tela Ativos → "Análise Fundamentalista")

Para FIIs/REITs: badge de status + confiança, P/VP, Dividend Yield, DY
médio do histórico próprio, estabilidade do DY (com motivo quando
indeterminada), avisos e métodos usados. Ver
`docs/FUNDAMENTAL_ANALYSIS_UI.md`.

## Limitações conhecidas

- Bandas de P/VP e DY são heurística MVP fixa, não calibrada por
  segmento de FII (lajes corporativas, logística, papel, shoppings
  têm perfis de yield muito diferentes entre si — o engine não
  distingue).
- REITs nunca usam FFO/AFFO (ver seção acima) — confiança sempre
  limitada para essa subclasse.
- Estabilidade usa coeficiente de variação simples, não ajustado por
  sazonalidade (alguns FIIs distribuem de forma irregular por
  natureza do ativo-lastro, sem que isso signifique risco real).
