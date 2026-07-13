# UX/UI Guide — Design System da LG INVEST (Sprint 30)

Este documento descreve o Design System interno criado na Sprint 30
("Product Design / UX Polish") e como ele foi aplicado nas nove telas
do app. Complementa `docs/UX_GUIDELINES.md` (tema, paleta de cores,
cores de classificação/grupo/moeda), que continua sendo a referência
para cores e para o tema escuro fixo. Este guia foca na camada acima
disso: os componentes de layout reutilizáveis e o padrão de estrutura
de cada tela.

## Por que este Design System existe

Antes da Sprint 30, cada tela montava sua própria versão de "card",
"aviso" ou "cabeçalho" com `st.markdown` + HTML solto, ou usava os
componentes nativos do Streamlit (`st.metric`, `st.warning`, `st.info`)
sem nenhuma padronização visual entre telas. O resultado tinha lógica
correta, mas aparência de protótipo: sem hierarquia visual clara, sem
uma leitura rápida de "isso está bom ou ruim", e com o app inteiro
parecendo uma coleção de telas desconectadas em vez de um produto
único.

O objetivo explícito do usuário para esta sprint (citação): "transformar
a LG INVEST em um app com aparência profissional, bem acabado,
organizado e com cara de produto financeiro premium (...) deixar de
parecer um protótipo Streamlit". Com uma restrição igualmente explícita:
"Não quero criar engine nova. Não quero criar funcionalidades complexas
novas." — ou seja, esta sprint é inteiramente de apresentação. Nenhuma
engine, service, cálculo ou regra de negócio foi tocada; a suíte de
1184 testes ficou inalterada do início ao fim (só passou a ser
executada mais vezes, para confirmar que nada quebrou).

## Onde vive o Design System

- `frontend/streamlit_app/components/patterns.py` — os seis componentes
  de layout (ver abaixo).
- `frontend/streamlit_app/components/badges.py` — badges HTML
  reutilizáveis, incluindo o `status_badge_html()` genérico e o
  `risk_badge_html()` da Sprint 30.
- `frontend/streamlit_app/styles/custom_css.py` — todo o CSS dos
  componentes acima. Nenhuma tela injeta `<style>` própria — isso
  garante que uma mudança visual (cor, espaçamento, borda) só precisa
  ser feita num lugar.
- `frontend/streamlit_app/styles/theme.py` — paleta de cores (já
  existia desde a Sprint 11/21, documentada em `UX_GUIDELINES.md`).

Regra geral: componentes em `patterns.py` e `badges.py` são só
renderização. Nenhum deles decide *quando* aparecer ou *com que dado*
— isso é sempre decisão da tela que os chama. Um componente nunca
consulta o banco, nunca chama uma engine, nunca formata um valor
monetário (isso é `formatting.py`).

## Os seis componentes

### 1. `page_header(title, description, icon="", status_badge=None)`

Cabeçalho padronizado de página: título grande + ícone opcional +
descrição curta de uma linha do que a tela faz. Substitui o antigo
padrão `st.title(...)` + `st.caption(...)` repetido (com formatação
levemente diferente) em cada tela.

Usado no topo de **todas as nove telas** do app (Dashboard, Carteira,
Aporte, Inteligência, Ativos, Radar, Simulação, Journal, Sincronizar
Dividendos.me, Configurações).

### 2. `metric_card_row(cards)` / `metric_card(...)`

Grade responsiva de "MetricCard premium" — como `st.metric`, mas com
uma faixa de cor lateral que comunica status (`positive` / `neutral` /
`attention` / `critical` / `muted`) sem depender só do texto. Cada
card é um dicionário `MetricCardSpec` (`label`, `value`, `icon`,
`delta` opcional, `status`, `help` opcional).

Usado na área "hero" do Dashboard (6 métricas principais), no resumo
da Carteira (patrimônio total, Brasil, exterior, maior posição — com
sinalização visual de concentração acima de 20%), no resumo da
Simulação (valor inicial, total aportado, mediana projetada,
probabilidade de perda — colorida por faixa de risco), no resumo do
Radar (contagem por estágio do funil da Watchlist) e no status da
integração com o Dividendos.me (credenciais, Playwright, última
sincronização).

Quando usar `status`: só quando o valor tem um julgamento de "bom ou
ruim" claro e calculado (ex.: perda ≥ 30% é `critical`). Métricas
neutras (contagens, totais informativos) usam `neutral`.

### 3. `alert_box(kind, title, message)` + atalhos

`success_box` / `info_box` / `warning_box` / `error_box` — alternativa
com título em destaque ao `st.success`/`st.info`/`st.warning`/`st.error`
nativos, que só aceitam um bloco de texto corrido. Usar quando o aviso
merece um título curto separado da explicação (ex.: "Nunca gera venda
automática" como título, com o texto completo da regra como corpo).
Para um aviso de uma linha só, o componente nativo do Streamlit
continua sendo suficiente e não foi substituído em todo lugar — a
troca foi seletiva, priorizando os avisos estruturais recorrentes
(como o disclaimer de "não vende automaticamente", repetido em três
seções de Configurações).

### 4. `recommendation_card(ticker, amount, weight, reason, name=None, badges_html="", tag_html="")`

Card de um ativo recomendado — usado no Aporte v3 no lugar da tabela
antiga. Mostra ticker, valor sugerido, % do aporte, motivo principal
em destaque, e badges (LG Score, Conviction Score, confiança do dado)
e uma tag ("Já tenho" / "Novo candidato"). O `badges_html`/`tag_html`
recebem HTML já pronto de `components/badges.py` — o card em si nunca
decide cor ou rótulo de badge.

### 5. `data_quality_box(title, available, missing, confidence_label=None, impact=None)`

Mostra de forma explícita o que uma análise usou e o que faltou —
usado em Ativos (Análise Fundamentalista) e nos candidatos do Aporte
v3 com dado frágil. Existia como componente desde a Sprint 30, Parte 1;
seu uso nas telas de Onda 2 permaneceu como estava (as seções que já
mostravam disponível/ausente antes da Sprint 30 continuaram com a
mesma estrutura de texto, priorizando não regredir nenhuma explicação
existente).

### 6. `empty_state(title, message, icon="📭", cta_label=None, cta_key=None)`

Tela ou seção sem dados ainda — substitui `st.info("Nenhum X ainda")`.
Devolve `True` quando o botão de ação opcional (`cta_label`) foi
clicado, deixando a tela decidir o que fazer.

Aplicado em: Ativos (sem ativos cadastrados), Radar (watchlist vazia,
radar de oportunidades vazio), Inteligência (carteira vazia), Carteira
(sem posições), Journal (sem ativos, sem entradas de diário, sem
teses, sem tese para revisar). Onde uma tela já tinha uma mensagem de
"vazio" explicativa e específica (ex.: o placeholder de "Dividendos
por Ativo — extração ainda não disponível" em Sincronizar
Dividendos.me, que documenta uma limitação técnica real, não um estado
vazio comum), o texto original foi mantido — `empty_state` é para
"você ainda não tem dados aqui", não para avisos técnicos.

## Badges

`components/badges.py` ganhou dois badges genéricos na Sprint 30:

- `status_badge_html(status, label=None)` — vocabulário de 9 status:
  `bom` / `atencao` / `critico` / `dados_insuficientes` / `atualizado`
  / `desatualizado` / `bloqueado` / `monitorando` / `candidato`.
- `risk_badge_html(classification)` — risco agregado da carteira:
  `baixo` / `moderado` / `moderado-alto` / `alto` / `indeterminado`.

Nem toda classificação de domínio foi migrada para o vocabulário
genérico de 9 status. O Portfolio Health Score, por exemplo, tem uma
escala própria de 5 valores (`excelente` / `boa` / `atenção` /
`crítica` / `indeterminado`) que não cabe dentro do vocabulário
genérico sem perder a distinção entre "excelente" e "boa" — por isso o
Dashboard mantém seu próprio dicionário de cor (`_HEALTH_COLOR`) para
esse caso específico, em vez de forçar tudo pelo `status_badge_html`.
A regra geral: usar o vocabulário genérico quando ele cobre o domínio
exatamente; manter um dicionário de cor dedicado quando o domínio tem
uma escala própria e mais rica.

## Layout global (sidebar e navegação)

`app.py` reorganiza a navegação em três grupos, usando `st.radio`
independentes sincronizados por um `session_state["nav_page"]`
compartilhado (o Streamlit não tem agrupamento nativo de rádio, então
cada rerun detecta qual grupo mudou e força os outros a `None`):

- **Principal**: Dashboard, Carteira, Aporte.
- **Análise**: Inteligência, Ativos, Radar, Simulação, Journal.
- **Operação**: Sincronizar Dividendos.me, Configurações.

O rodapé da sidebar mostra a versão do app ("LG INVEST v1.0 RC"), o
ambiente ("Local") e a data da última sincronização bem-sucedida com o
Dividendos.me — sempre dentro de um `try/except` para nunca derrubar o
app se essa consulta falhar.

## Como cada tela foi tratada

O tratamento não foi uniforme de propósito — a profundidade da
reformulação em cada tela dependeu de quanto ela já estava organizada
antes da Sprint 30 e do orçamento de esforço da "Onda 2" (aplicar o
Design System em seis telas na mesma sessão de trabalho).

**Reformulação estrutural** (Onda 1, telas priorizadas explicitamente
pelo usuário):
- **Dashboard**: hero com `metric_card_row` (6 métricas), nova seção
  "Decisão do mês", seção "Alertas" consolidada, Central de Dados
  dentro de um `st.expander` recolhido.
- **Aporte v3**: tabela de recomendações virou grade de
  `recommendation_card`, com breakdown técnico dentro de um expander
  por ativo.

**Adoção leve a moderada** (Onda 2 — preserva 100% da estrutura e
lógica existentes, adicionando `page_header`, `empty_state` e, onde
fazia sentido, `metric_card_row`/badges/`alert_box`):
- **Ativos**: `page_header` + `empty_state`. A estrutura rica já
  existente (LG Score, Conviction Score v2, Fundamentos, Análise
  Fundamentalista com Valuation Engine 2.0) não foi tocada.
- **Radar**: `page_header` + resumo da Watchlist migrado para
  `metric_card_row` (um card por estágio do funil) + `empty_state` nos
  dois pontos sem dados.
- **Inteligência**: `page_header` + `empty_state`. A tela já tinha uma
  organização interpretativa (Resumo Executivo, buckets de
  classificação, "Por que esse ativo?") alinhada ao espírito da
  Sprint 30, então não precisou de reestruturação.
- **Carteira**: `page_header` + hero `metric_card_row` (patrimônio
  total, Brasil, exterior, maior posição com sinalizador de
  concentração ≥ 20%) + `empty_state`.
- **Simulação**: `page_header` + `info_box` explicando que é uma
  projeção, não uma previsão + os 4 `st.metric` de resultado migrados
  para `metric_card_row` (com a probabilidade de perda colorida por
  faixa).
- **Configurações**: reorganizada em `st.tabs` (Visão geral, Alocação
  simples, Regras detalhadas, Política de investimento, Simulação,
  Sistema) no lugar de uma rolagem vertical única com sete seções
  separadas por `st.divider()`. Os disclaimers repetidos de "nunca gera
  venda automática" migraram para `warning_box`/`info_box`.
- **Journal**: `page_header` + `empty_state` nos quatro pontos sem
  dados (sem ativos, sem entradas, sem teses, sem tese para revisar).
- **Sincronizar Dividendos.me**: `page_header` + status da integração
  migrado de `st.metric` solto para `metric_card_row`, com os avisos de
  credenciais/Playwright ausentes usando `info_box`.

## O que não mudou (e por quê)

- **Nenhuma engine, service ou regra de negócio.** Esta sprint é
  inteiramente de apresentação — confirmado pela suíte de 1184 testes
  ficando inalterada do início ao fim.
- **Nenhuma tela perdeu funcionalidade.** Todo formulário, botão,
  fluxo de confirmação (ex.: a palavra de confirmação exata exigida
  para substituir a carteira no Dividendos.me) e explicação técnica
  existente antes da Sprint 30 continua exatamente igual — só a camada
  visual ao redor mudou.
- **Padronização de texto/jargão técnico → linguagem de produto** foi
  aplicada de forma pontual (ex.: os disclaimers convertidos para
  `warning_box`/`info_box`), não como uma varredura completa de todo
  texto do app. Uma varredura textual completa (padronizar todo termo
  técnico restante) fica como trabalho futuro, se o usuário quiser
  aprofundar depois da v1.0.

## Para quem for adicionar uma tela nova

1. Sempre começar com `page_header(title, description, icon=...)`.
2. Se a tela pode ficar sem dados (carteira vazia, watchlist vazia,
   etc.), usar `empty_state(...)` em vez de `st.info`.
3. Se a tela tem um resumo numérico no topo (3 a 6 números), considerar
   `metric_card_row` em vez de `st.metric` solto — só vale a pena
   quando pelo menos um dos números tem um status claro (bom/atenção/
   crítico).
4. Nunca injetar `<style>` numa tela — se falta uma classe CSS, ela
   deve ser adicionada em `styles/custom_css.py`, nunca inline.
5. Um componente novo em `patterns.py` só deve ser criado quando o
   padrão se repete em pelo menos duas telas — caso contrário, é
   provável que o padrão já exista e só precise ser reaproveitado.
