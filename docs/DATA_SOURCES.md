# Fontes de Dados — LG INVEST (atualizado na Sprint 13)

Contrato de cada fonte externa usada pela plataforma: o que ela
fornece, cadência, limitações conhecidas e a cadeia de fallback quando
falha. Nenhuma fonte paga é usada sem aprovação explícita prévia.

## Preços de ativos

**Fonte:** Yahoo Finance, via biblioteca `yfinance`.
**Provider:** `backend/app/etl/providers/yahoo_provider.py` (`YahooFinanceProvider`).
**Campos coletados:** open, high, low, close, adjusted close, volume, por data.
**Cadência:** sob demanda (botão "Atualizar preços" em Configurações/Ativos), coleta incremental a partir do último preço salvo.
**Limitações conhecidas:**
- Gratuita, mas não documentada oficialmente como API estável — sujeita a mudanças de formato sem aviso.
- Sem SLA; falhas de rede ou bloqueio temporário são possíveis.
- Não cobre Tesouro Direto nem outros ativos sem ticker de bolsa.
**Fallback:** nenhum — se o Yahoo falhar para um ativo, ele permanece no
último preço salvo (ou sem preço, se nunca teve); o Dashboard sinaliza
isso como preço "estimado" (fallback para `average_price`) ou "sem
preço", nunca inventa uma cotação.
**Ativos fora desta fonte:** ativos marcados `is_manual=True` (ex.:
Tesouro Direto) nunca são consultados aqui — o preço é sempre cadastrado
manualmente na tela Ativos.

## Câmbio USD/BRL

**Fonte primária:** Banco Central do Brasil, API de dados abertos (PTAX),
endpoint OData público, sem chave de API:
`https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata`.
**Provider:** `backend/app/etl/providers/bcb_fx_provider.py` (`BcbFxProvider`).
**Campos coletados:** `cotacaoCompra`, `cotacaoVenda`, `dataHoraCotacao` do
pregão mais recente dentro de uma janela de até 7 dias anteriores à
data alvo. A taxa usada é a média simples entre compra e venda.
**Cadência:** sob demanda (botão "Atualizar câmbio automático" em Configurações).
**Limitações conhecidas:**
- Não há cotação em finais de semana e feriados — por isso a janela de
  busca (walk-back) em vez de uma única data fixa.
- API pública sem SLA formal; resposta pode mudar de formato.
**Fallback:** se o BCB falhar (rede, formato inesperado, sem cotação na
janela), o serviço tenta o Yahoo Finance (`USDBRL=X`,
`yahoo_fx_provider.py`). Se ambos falharem, mantém a última cotação já
salva em `data/app_settings.json` — nunca deixa o Dashboard sem número,
mas sinaliza a data da última atualização. O usuário também pode
sobrescrever manualmente a qualquer momento.
**Flag de controle:** `settings.bcb_fx_enabled` (`.env`: `BCB_FX_ENABLED`)
— desligar pula direto para Yahoo.

## Fundamentos (ROE, margens, múltiplos, EBITDA/FCF/dívida) — parcialmente implementado (Sprint 13)

**Fonte:** Yahoo Finance, via `yfinance` (`Ticker.info` e
`Ticker.income_stmt`/`Ticker.balance_sheet`/`Ticker.cashflow`).
**Provider:** `backend/app/etl/providers/yahoo_fundamentals_provider.py`
(`YahooFundamentalsProvider`).
**Campos coletados:** snapshot "TTM" via `.info` (ROE, ROA, margens,
P/L, P/VP, EV/EBITDA, dividend yield, payout, EPS, beta, dívida líquida,
dívida/EBITDA) + até 4 snapshots anuais históricos via demonstrativos
(receita, lucro líquido, EBITDA, EBIT, FCF, dívida líquida) — sem os
múltiplos, que só existem para o período mais recente.
**Cadência:** sob demanda (botões "Coletar fundamentos" na tela Ativos,
por ativo ou em lote).
**Limitações conhecidas:**
- Cobertura inconsistente: FIIs, small caps e a maioria dos ativos fora
  de ações/ETFs trazem `info` quase vazio.
- Nomenclatura de campos pode mudar sem aviso entre versões do
  `yfinance` (mesmo risco documentado para preços).
- `dividendYield`/`payoutRatio` são usados como o `yfinance` os
  retorna (fração).
**Fallback:** nenhum — campo ausente ou não numérico vira `None`
explícito (nunca um valor inventado); `FundamentalSnapshotResult`
expõe `coverage_pct`/`missing_fields` para a UI e para engines
futuras saberem exatamente quanto do indicador está disponível.
**Ativos fora desta fonte:** ativos `is_manual=True` e classes sem
fundamentos de empresa aplicáveis (`crypto`, `cash`, `bond`) nunca são
consultados — pulados com razão explícita antes de chamar o provider.
**Fora do escopo desta sprint:** cálculo de indicadores derivados
(Fundamentals Engine puro — CAGR, scores de qualidade/crescimento) é a
Sprint 14; ver `docs/FUNDAMENTALS_ENGINE_PLAN.md`.

## Regra geral de qualidade de dado

Em qualquer fonte, falha ou dado ausente nunca é preenchido com um
valor otimista ou inventado — o sistema sinaliza a ausência
explicitamente (status "estimado"/"manual"/"sem preço" no preço, nota
neutra + razão no LG Score/Conviction Score) e deixa a decisão final
com o usuário.
