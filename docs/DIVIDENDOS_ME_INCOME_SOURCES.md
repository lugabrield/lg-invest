# Fontes de proventos do Dividendos.me (Sprint 24 — Fase 2)

A LG INVEST usa três fontes distintas e independentes de proventos do
Dividendos.me. Elas nunca se misturam entre si — nem no banco, nem na tela,
nem no CLI — porque representam conceitos diferentes: um agregado mensal,
um calendário futuro, e (ainda não implementado) um detalhamento por ativo.

## Fonte A — Histórico mensal agregado (implementada)

**Tela:** Renda Variável → Brasil → Central de Proventos → aba **Análise**
**Rota:** `https://app.dividendos.me/dividends` (hub único, troca de aba via
clique — nunca por URL separada)
**Formato:** tabela ano × mês, uma tabela por carteira (o site tem um
seletor de carteira, ex.: "Carteira (B3)", "Carteira Dolar"), com colunas
`ANO`, `JAN`...`DEZ`, `TOTAL`, `MÉDIA`.

Esta é a única fonte confiável de "quanto eu já recebi por mês", mas é um
**agregado por carteira** — não tem ticker nem data exata de pagamento.
Forçar isso no formato de "evento por ativo" (como uma versão anterior do
código fazia) inventaria um `payment_date` e um `ticker` que a fonte não
fornece — por isso vive numa tabela própria.

Implementação:
- Parser: `parse_monthly_summary` (`income_parser.py`) — meses com valor
  zero ou ausente são pulados (não representam provento real); `TOTAL`/
  `MÉDIA` são lidos direto das colunas da tabela, nunca recalculados.
- Status: `"recebido"` para mês já fechado (passado ou mês corrente),
  `"anunciado"` para mês futuro dentro do mesmo ano exibido na tabela —
  calculado por comparação de data real (`today`), nunca uma suposição.
- Moeda: detectada pelo rótulo da carteira (`"Dolar"`/`"internacional"` →
  USD; qualquer outra, incluindo "Carteira (B3)" → BRL).
- Tabela: `income_monthly_summaries` (migration `b2f6a1d84c33`).
- Dedup: `portfolio_id + wallet_name + year + month + currency + source`.
- Fluxo: `IncomeSyncService.build_monthly_preview` / `dry_run_monthly` /
  `import_monthly_summaries` — nunca escreve em dry-run, só adiciona
  (nunca remove/edita histórico já salvo).

Validado contra dados reais reportados pelo usuário (ano 2026 e totais
anuais de 2021-2025) — ver
`test_parse_monthly_summary_matches_real_2026_data_reported_by_user` e
`test_parse_monthly_summary_multi_year_matches_real_totals_reported_by_user`
em `backend/tests/unit/test_dividendos_me_income_parser.py`.

## Fonte B — Dividendos por ativo/mês (NÃO implementada — limitação documentada)

**Tela:** Renda Variável → Brasil → Gráficos → **Dividendos por Ativo**
**Rota:** `https://app.dividendos.me/dividendos-por-ativo?country=1`
**Formato observado:** seletor de carteira + seletor de ano, totais por
classe (ex.: "Ações: R$ 293,86", "FIIs: R$ 837,28") e um gráfico de barras
empilhado por mês, com legenda de tickers (ex.: ALUP4, B3SA3, HGLG11...).

Esta fonte teria o dado mais granular (provento por ativo por mês), mas os
valores vivem dentro de um gráfico interativo (tipicamente renderizado por
uma biblioteca como Highcharts/ApexCharts/Chart.js), não numa tabela HTML
simples com `<thead>`/`<tbody>` como as outras seções da plataforma.

**Por que não foi implementada nesta sprint:** extrair dado de um gráfico
de forma confiável exige uma de três abordagens — (1) ler a estrutura
interna de dados do gráfico via `page.evaluate()` sabendo o nome exato da
variável/API JS que o guarda, (2) interceptar uma chamada de rede que
alimenta o gráfico, ou (3) fazer parsing visual dos elementos SVG/canvas
renderizados. Todas exigem inspecionar a página ao vivo (DevTools, aba
Network, ou o próprio código-fonte servido) para confirmar qual mecanismo
o Dividendos.me usa — e este ambiente de desenvolvimento não tem acesso a
Playwright/rede ao vivo para fazer essa investigação.

Seguindo a regra do projeto de **nunca inventar dado**: em vez de assumir
um formato de extração sem confirmação, esta fonte fica marcada como
"detectada, não implementada". A tela "Sincronizar Dividendos.me" mostra
isso explicitamente na seção "5C. Proventos — Por ativo/mês", e nem o CLI
nem o banco recebem uma tabela `income_monthly_by_asset` até que a
extração real seja validada contra a página ao vivo.

**Próximo passo, quando houver acesso ao ambiente real:** abrir a tela com
DevTools, checar `window.__NEXT_DATA__`/variáveis globais do gráfico ou a
aba Network por uma chamada JSON que alimenta o componente, e só então
desenhar `income_monthly_by_asset` (schema já rascunhado abaixo, para não
perder o desenho quando isso for possível) com dedup
`portfolio_id + wallet_name + year + month + ticker + currency + source`
e `source = "dividendos_me:income_monthly_by_asset"`.

## Fonte C — Calendário futuro / próximos dividendos (implementada)

**Tela:** Central de Proventos → aba **Próximos Dividendos** (aba padrão do
mesmo hub da Fonte A)
**Formato:** lista agrupada por dia de pagamento, com ticker, tipo
(Div./JCP/Rend.) e valor (convertido em BRL + valor nativo).

Esta é a única fonte com ticker, mas é sempre **futura/anunciada** — nunca
"já recebida com data exata". Implementação em `parse_upcoming_dividends`,
gravada em `income_events` (nunca em `income_monthly_summaries`), com
status sempre `"anunciado"`.

## Por que as três nunca se misturam

| | Tem ticker? | Tem data exata? | É histórico ou futuro? | Tabela |
|---|---|---|---|---|
| Fonte A (Análise) | Não | Não (só ano/mês) | Histórico (recebido/anunciado por mês) | `income_monthly_summaries` |
| Fonte B (Por Ativo) | Sim | Não (só ano/mês) | Histórico — **não implementada** | (nenhuma ainda) |
| Fonte C (Próximos Dividendos) | Sim | Sim (dia) | Futuro/anunciado | `income_events` |

Misturar essas fontes na mesma tabela forçaria uma delas a inventar um
campo que não tem (ticker para A, data exata para A/B, ou tratar um evento
futuro como já recebido para C) — por isso a separação é definitiva, não
uma escolha de conveniência.
