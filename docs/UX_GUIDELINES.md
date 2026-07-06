# UX Guidelines — Tema e Componentes (Sprint 11; correção de contraste Sprint 21)

## O bug corrigido

Antes do Sprint 21, `.streamlit/config.toml` não existia — o Streamlit
escolhia o tema (claro/escuro) com base na preferência do navegador do
usuário, enquanto o CSS customizado (`custom_css.py`) tinha cores de
texto hardcoded assumindo um tema claro. Em navegadores com preferência
de tema escuro, isso produzia cards com fundo escuro (herdado do tema
Streamlit) e texto claro sobre fundo claro — ou o inverso — resultando
em texto praticamente invisível em várias telas.

**Correção**: fixar o tema em modo escuro de ponta a ponta —
`.streamlit/config.toml` (`base = "dark"`) e todas as cores de texto
em `custom_css.py` e `theme.py` definidas explicitamente, nunca
herdadas do tema do navegador.

## Paleta (`frontend/streamlit_app/styles/theme.py`)

**Fundos**: `APP_BACKGROUND = #0B0F17`, `APP_BACKGROUND_SECONDARY =
#11151F`, `CARD_BACKGROUND = #151A24`, `CARD_BACKGROUND_HOVER =
#1A2130`.

**Bordas**: `BORDER = #2A3242`, `BORDER_SOFT = #1F2733`.

**Texto**: `TEXT_PRIMARY = #E9EDF4` (texto principal, sempre claro
sobre fundo escuro), `TEXT_MUTED = #9AA6B8` (texto secundário),
`TEXT_FAINT = #6B7688` (texto terciário/legendas).

**Cor de marca**: `PRIMARY = #3B82F6`, `PRIMARY_DARK = #1D4ED8`.

**Semânticas**: `POSITIVE = #3DD68C` (verde), `NEGATIVE = #F0554A`
(vermelho), `ATTENTION = #F5A623` (âmbar), `ALERT = #F0554A`, `INFO =
#3B82F6`, `NEUTRAL = #8B96A8`.

## Cores de classificação (Decision Engine / Conviction Score)

| Classificação | Cor | Label em português |
|---|---|---|
| `strong_buy` | `POSITIVE` (#3DD68C) | Aportar |
| `buy` | `#7DD69A` | Candidato |
| `hold` | `INFO` (#3B82F6) | Manter |
| `watch` | `ATTENTION` (#F5A623) | Monitorar |
| `avoid` | `NEGATIVE` (#F0554A) | Evitar |
| `insufficient_data` | `NEUTRAL` (#8B96A8) | Dados insuficientes |

Helpers: `classification_color(classification)` e
`classification_label_pt(classification)` (`theme.py`) — usados por
`components/badges.py` para renderizar badges HTML consistentes em
todas as telas.

## Cores por grupo/moeda (gráficos)

`GROUP_COLORS`: Ações BR `#3B82F6`, FIIs `#A78BFA`, Ações EUA `#2DD4BF`,
ETFs `#F5A623`, REITs `#F0554A`, Cripto `#FACC15`, Renda Fixa `#8B96A8`.
`CURRENCY_COLORS`: BRL `#3B82F6`, USD `#2DD4BF`. Labels fora dessas
tabelas caem em `FALLBACK_PALETTE` via hash determinístico
(`color_for()`), garantindo cor estável entre execuções.

## Componentes reutilizáveis

- **`components/sections.py`** — `section(titulo, ícone, caption=None)`:
  cabeçalho padronizado usado em todas as telas.
- **`components/cards.py`** — `KpiCard`, `render_kpi_grid()` (grade de
  métricas no topo de cada tela), `render_insight_list()` (lista de
  insights do Portfolio Diagnostics).
- **`components/tables.py`** — `render_positions_table()`,
  `render_grouped_positions()`.
- **`components/badges.py`** — `classification_badge_html()`,
  `confidence_badge_html()`, `data_quality_badge_html()`: badges HTML
  coloridos, fundo derivado da cor semântica com alpha (~15%),
  aplicados via variáveis CSS (`--lg-badge-bg`, `--lg-badge-border`).

## Classes CSS principais (`custom_css.py`)

- `.lg-section-header` / `.lg-section-subtitle` — cabeçalhos de seção.
- `.lg-insight-card` — cards de insight (Diagnóstico, Dashboard,
  Inteligência), cor da borda esquerda controlada por
  `--lg-insight-color`.
- `.lg-asset-card` — cards de ativo (Inteligência, Ativos).
- `.lg-badge` — badges de classificação/status.
- `.lg-highlight-box` — caixa de destaque ("Por que esse ativo?",
  resumo do Aporte), fundo `{PRIMARY}` com alpha baixo.
- `.lg-muted` / `.lg-faint` — utilitários de texto secundário.

Também restiliza elementos nativos do Streamlit (`stMetric`,
`stDataFrame`, `stExpander`) para manter a aparência consistente com o
resto da plataforma.

## Gráficos (Plotly)

`frontend/streamlit_app/charts/_theme.py::apply_dark_layout(fig)` —
aplicado a **todo** gráfico Plotly da plataforma: força
`template="plotly_dark"`, fundo de papel/plot transparente/escuro e
cor de texto consistente com a paleta acima. Isso evita o mesmo bug de
contraste em gráficos (eixos/legendas ilegíveis sobre fundo escuro).

## Regras gerais

- Nenhum texto deve depender da cor herdada do tema do navegador —
  sempre definir `color` explicitamente.
- Nenhum número deve aparecer sem formatação (`formatting.py`:
  `format_brl`, `format_usd`, `format_pct`, `format_number`,
  `format_quantity`).
- Toda tela nova deve reutilizar `section()`, `KpiCard`/
  `render_kpi_grid()` e os badges — não criar HTML solto por tela.
