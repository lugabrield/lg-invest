# UI — Análise Fundamentalista (Sprint 26, Fase 7)

## Objetivo

Expor, por ativo, os quatro engines construídos nesta sprint —
Valuation Engine 2.0, Trap Detection Engine, Análise de Renda
Imobiliária e Adequação de Carteira — numa única seção nova da tela
Ativos ("Análise Fundamentalista"), sem duplicar a seção "Fundamentos"
já existente (que mostra os campos brutos coletados e o Valuation
Engine v1 legado, mantidos intactos). Camada de apresentação pura:
nenhum cálculo novo vive aqui (Volume 20, prompt 11) — só leitura,
formatação e roteamento por classe de ativo.

## Localização

`frontend/streamlit_app/pages_impl/ativos.py`, seção "🔬 Análise
Fundamentalista", logo após "📚 Fundamentos" e antes de "🏷️ Marcar
ativo como manual".

## Roteamento por classe de ativo

A seção sempre pede um ticker (`st.selectbox`) e então roteia para
exatamente UM bloco de análise, conforme `asset_class` — nunca mais de
um, nunca decidido de novo aqui (as constantes de classe espelham as já
impostas pelos próprios engines):

| Classe | Bloco exibido | Serviço consultado |
|---|---|---|
| `stock` | Valuation Engine 2.0 | `ValuationServiceV2` |
| `fii`, `reit` | Análise de Renda Imobiliária | `IncomeRealEstateService` |
| `etf`, `crypto`, `bond` | Adequação à Política de Alocação | `PortfolioAdequacyService` (precisa de `portfolio_id`) |
| qualquer classe (`stock`, `fii`, `reit`) | Flags do Trap Detection Engine (bloco adicional, sempre abaixo do principal) | `TrapDetectionService` |

`ativos.render()` passou a receber `portfolio_id: int` (antes não
recebia nenhum argumento) — necessário para a Adequação de Carteira,
que avalia peso atual/alvo dentro de UM portfólio específico. `app.py`
já repassa o `portfolio_id` selecionado na sidebar.

## Bloco: Valuation Engine 2.0 (ações)

Badge de status (subvalorizado/valor justo/sobrevalorizado/
indeterminado) + badge de confiança. Quando há faixa calculável: faixa
mínima/base/máxima (3 métricas lado a lado), preço atual, margem de
segurança obtida vs. exigida, expectativa implícita de mercado (reverse
DCF), Graham Number como checagem de sanidade (nunca destacado como
método primário), cenários individuais num `st.expander` (um por
método: DCF pessimista/base/otimista, múltiplos), avisos e lista de
métodos efetivamente usados. Quando indeterminado, mostra só o `reason`
literal (nunca inventa uma faixa).

## Bloco: Análise de Renda Imobiliária (FII/REIT)

Badge de status (atrativo/neutro/pouco atrativo/indeterminado) + badge
de confiança. P/VP, Dividend Yield, DY médio do histórico próprio (3
métricas lado a lado), estabilidade do DY com o motivo quando
indeterminada, avisos (inclui sempre a limitação de FFO/AFFO para
REITs) e métodos usados.

## Bloco: Adequação à Política de Alocação (ETF/cripto/Tesouro)

`st.info()` fixo com `valuation_note` (a mensagem que explica por que
esta classe não tem valuation tradicional), badge de status de
adequação (abaixo do alvo/no alvo/acima do alvo/bloqueado/
indeterminado), peso atual/alvo/gap (3 métricas lado a lado), peso da
classe inteira na carteira (com alvo, quando disponível), `st.warning()`
com o `alert_message` do Target Allocation Engine v2 quando existe, e
`st.error()` de concentração extrema quando `extreme_overweight=True`
— sempre reforçando "nunca uma sugestão de venda" no próprio texto.

## Bloco: flags do Trap Detection Engine

Exibido sempre que aplicável (ações, FIIs, REITs), independente de qual
dos três blocos acima foi mostrado. Um cartão por flag ativo: badge de
severidade + label, explicação, "como interpretar" (nunca "vender"/
"comprar"). Sem flags ativos mas dentro do escopo, nada extra é
mostrado; fora do escopo (ETF/cripto/Tesouro), mostra o `reason` da
varredura quando presente.

## Badges novos (`components/badges.py`)

Quatro funções novas, seguindo o mesmo padrão dos badges existentes
(`_badge_html` + mapa cor/rótulo por status):

- `valuation_status_badge_html` — status do Valuation Engine 2.0.
- `income_real_estate_status_badge_html` — status da Análise de Renda
  Imobiliária.
- `adequacy_status_badge_html` — status de Adequação de Carteira.
- `trap_severity_badge_html` — severidade de uma flag do Trap
  Detection Engine.

Cores reaproveitam a paleta semântica já existente
(`styles/theme.py::POSITIVE/INFO/ATTENTION/ALERT/NEUTRAL`) — nenhuma
cor nova foi introduzida.

## Nunca uma recomendação de compra/venda

Todos os quatro blocos + o bloco de flags seguem a mesma disciplina do
resto da plataforma: análise, faixa, confiança e avisos — nunca um
veredito de "compre"/"venda". A caption da seção reforça isso
explicitamente para o usuário.

## Testes

A UI Streamlit deste projeto não tem testes unitários de renderização
(convenção já estabelecida — ver `backend/tests/unit/
test_streamlit_smoke.py`, que só verifica que cada módulo de página
importa sem erro e expõe `render()`). A lógica de dados por trás de
cada bloco já está coberta pelos testes dos respectivos serviços/
engines (ver os 4 docs de engine desta sprint).

## Bloco: "Dados usados e dados ausentes" (Sprint 28)

Novo bloco, exibido sempre logo após o bloco de flags do Trap
Detection, alimentado pelo Data Coverage Report
(`docs/DATA_COVERAGE_REPORT.md`) do ticker selecionado:

- Frase-resumo (`coverage.summary`).
- 5 métricas lado a lado — Quality/Valuation/Trap Detection/Análise de
  Renda/Decision Engine — cada uma com o score (0-100%) e a
  classificação (suficiente/parcial/insuficiente/não aplicável).
- `st.expander("Dados disponíveis (N)")` — cada campo disponível, com
  valor formatado, fonte (`"yahoo"` ou `"manual_import"`) e data de
  atualização.
- `st.expander("Dados ausentes (N)", expanded=True quando houver algo
  ausente)` — cada campo ausente listado, mais uma legenda de impacto
  quando a lacuna afeta o valuation ("sem esses dados, a confiança do
  valuation permanece baixa").

Este bloco nunca decide nada por conta própria — é leitura pura do
`DataCoverageResult` já calculado pelo `DataCoverageService`, mesma
disciplina dos demais blocos desta tela.

## Bloco: "Importar fundamentos manualmente (CSV/Excel)" (Sprint 28)

Novo bloco, logo abaixo de "Cadastrar preço atual manual": botão para
baixar o modelo CSV, upload de `.csv`/`.xlsx`/`.xls`, checkbox
"Sobrescrever snapshots existentes que colidirem" e botão "Importar
fundamentos". Depois de importar, mostra um resumo (linhas no arquivo,
aplicadas, pendentes de confirmação, tickers recomputados) e a lista
de erros/avisos por linha, quando houver. Ver
`docs/MANUAL_FUNDAMENTALS_IMPORT.md` para o detalhamento completo das
regras (nunca cria ativo novo, nunca sobrescreve sem confirmação
explícita).

## O que ainda não existe

- Nenhum gráfico (Plotly) para a faixa de valor justo ou para a série
  histórica de DY — só métricas e texto.
- Nenhuma comparação lado a lado entre ativos dentro desta seção (é
  sempre um ticker por vez, via `st.selectbox`).
