# Guia de Uso — LG INVEST v1.0

Este guia explica como usar a LG INVEST no dia a dia: o fluxo principal recomendado, o que cada tela faz, e como interpretar os principais indicadores.

Para instalar o app, ver `docs/INSTALLATION.md`. Para comandos do dia a dia (abrir o app, atualizar dados, fazer backup), ver `docs/LOCAL_RUNBOOK.md`.

## Aviso importante

A LG INVEST organiza dados e aplica regras explícitas e transparentes para sugerir onde aportar — **ela nunca decide por você, nunca executa ordens e nunca recomenda vender uma posição existente.** Toda sugestão vem acompanhada do motivo e do nível de confiança, para que a decisão final seja sempre sua.

## Fluxo de uso principal (recomendado)

Este é o caminho pensado para o uso recorrente do app — não é obrigatório seguir esta ordem exata todas as vezes, mas é o fluxo que a interface foi organizada para guiar:

### 1. Sincronizar Dividendos.me (opcional) ou importar a carteira manualmente

Se você usa o [Dividendos.me](https://dividendos.me) para acompanhar sua carteira, configure as credenciais em `.env` (ver `docs/INSTALLATION.md`) e use a tela **Sincronizar Dividendos.me** para importar posições e proventos automaticamente. Sempre rode primeiro em modo **dry-run** (só mostra o preview, não altera nada) antes de confirmar um `replace` (substitui toda a carteira) ou `update` (atualiza incrementalmente).

Sem Dividendos.me, importe sua carteira manualmente via CSV/Excel na tela **Carteira**.

### 2. Atualizar dados

Na tela **Dashboard**, abra o painel **"Atualizar dados e análises"** (Central de Dados) e rode a atualização de preços, fundamentos e/ou watchlist. Essas rotinas buscam dados externos (Yahoo Finance) e podem demorar — não rodam sozinhas, só quando você clica.

### 3. Configurar política e alocação-alvo

Na tela **Configurações**, defina (se ainda não definiu):
- **Alocação-alvo simples** por classe de ativo, ou
- **Regras detalhadas** por classe/moeda/país/ativo específico (têm precedência sobre a política geral), e/ou
- **Política de investimento geral** (perfil, limites máximos, exposição internacional-alvo) — funciona como um limite padrão (fallback) para dimensões sem regra detalhada própria.

Sem nenhuma meta configurada, a LG INVEST nunca inventa uma alocação "recomendada" — as recomendações de aporte usam só LG Score/Conviction Score e concentração.

### 4. Revisar o Dashboard

Visão geral: patrimônio total, variação, exposição internacional, Portfolio Health Score, risco da carteira, alertas ativos (dados desatualizados, preços manuais/estimados, dados insuficientes) e a "Decisão do mês" (melhor oportunidade pelo LG Conviction Score v2).

### 5. Explorar a Inteligência

Ranking completo dos ativos da carteira por LG Conviction Score v2, organizado em blocos interpretativos (oportunidades, riscos, dados insuficientes).

### 6. Simular um aporte

Na tela **Aporte**, informe o valor e gere a recomendação (Decision Engine v1/v2/v3 — use v3, o mais completo, por padrão). O resultado mostra, por ativo: valor sugerido, motivo principal, badges de score/confiança, e um expander "Ver detalhes técnicos" com o breakdown completo. Mostra também os ativos evitados (com motivo do bloqueio) e, quando relevante, os limites pós-aporte atingidos e o saldo não alocado.

### 7. Avaliar candidatos novos no Radar/Watchlist

Ativos que você está considerando mas ainda não tem posição ficam na **Radar**. Cadastre um candidato, colete os dados dele, e acompanhe a classificação (`new_candidate`, `blocked`, etc.) antes de decidir se e quando iniciar uma posição pequena.

### 8. Estudar fundamentos de um ativo específico

Na tela **Ativos**, selecione um ativo para ver o LG Score explicado por fator, o LG Conviction Score v2, e a Análise Fundamentalista completa (Valuation Engine 2.0 para ações, análise de renda para FIIs/REITs, adequação de política para ETF/cripto/Tesouro, e possíveis armadilhas de valuation detectadas).

### 9. Rodar cenários de longo prazo

Na tela **Simulação**, rode uma projeção Monte Carlo de patrimônio futuro com aportes recorrentes — sempre apresentada como uma faixa de probabilidade, nunca uma previsão exata.

### 10. Decidir manualmente, fora do app

A LG INVEST organiza a informação e explica o raciocínio; **a decisão final e a execução (comprar, vender, transferir) são sempre feitas por você, na sua corretora**, fora do app.

## Telas em detalhe

### Dashboard

Ponto de entrada. Mostra: patrimônio total (convertido e por moeda), variação, exposição internacional, Portfolio Health Score (score agregado de 5 sinais — nunca uma recomendação de compra/venda), risco da carteira, alocação por classe/moeda/Brasil-exterior, destaques (top posições, melhor/pior retorno), diagnóstico da carteira (regras simples e transparentes, sem IA generativa), e a tabela completa de posições. A **Central de Dados** (dentro de um expander) é onde você dispara a atualização manual de preços/fundamentos/watchlist — a última atualização aparece no próprio título do painel, sem precisar abrir.

### Carteira

Lista de posições, com filtros e composição. É aqui que você importa uma carteira via CSV/Excel (modelo em `database/seeds/positions_template.csv`) quando não usa o Dividendos.me.

### Aporte

Coração do app: recomenda como distribuir um valor de aporte entre os ativos da carteira (e, opcionalmente, candidatos da Watchlist). Três motores disponíveis (v1 é o mais simples/antigo, v3 é o mais completo — usa fundamentos, alocação-alvo multi-dimensão, concentração e internacionalização, escalado pela confiança do dado). A recomendação nunca soma mais que o valor informado, nunca sugere venda, e sempre explica por que cada ativo foi priorizado ou evitado. Quando o aporte é grande o suficiente para ultrapassar um limite máximo configurado (classe/moeda/país/ativo/exposição internacional) *depois* de aplicado, a seção "Limites pós-aporte atingidos" mostra exatamente qual dimensão foi cortada e por quê — o valor excedente fica como saldo não alocado, nunca forçado em outro lugar.

### Inteligência

Ranking de todos os ativos com posição na carteira, por LG Conviction Score v2 (Qualidade, Valuation, Crescimento, Risco, Reinvestimento de Capital, com pesos por classe de ativo). Organiza em blocos: oportunidades, riscos, dados insuficientes.

### Ativos

Cadastro mestre de todos os ativos: status do preço (automático/manual/sem preço), fundamentos coletados, LG Score, LG Conviction Score v2, e a **Análise Fundamentalista** completa por ativo — a seção mais profunda do app. Para ações: Valuation Engine 2.0 (faixa de valor justo por DCF, múltiplos e Graham). Para FIIs/REITs: análise de renda imobiliária (P/VP + Dividend Yield + estabilidade). Para ETF/cripto/Tesouro (sem valuation tradicional): adequação à política de alocação. Em todos os casos, o Trap Detection Engine sinaliza possíveis armadilhas de valuation, e a seção "Dados usados e dados ausentes" mostra exatamente quais campos faltam e o impacto disso na confiança do resultado.

É também aqui que você marca um ativo como "manual" (sem cotação automática, ex.: Tesouro Direto), cadastra o preço manual dele, atualiza preços/fundamentos individualmente, e importa fundamentos manualmente via CSV/Excel quando o Yahoo Finance não cobre o ativo.

### Radar

Watchlist de candidatos que ainda não são posição na carteira. Cadastre um ticker, colete os dados dele, e acompanhe o status (observando, candidato, bloqueado, descartado, comprado). Candidatos classificados como `new_candidate` podem entrar na recomendação do Aporte v3 (opção "Permitir ativos novos da watchlist"), sempre com um teto reduzido do aporte e nunca criando a posição sozinho.

### Simulação

Projeção Monte Carlo de patrimônio futuro, dado um valor inicial, aporte mensal e horizonte. Usa premissas de retorno/volatilidade por classe (configuráveis em Configurações → aba Simulação), não dados de mercado real coletados — é uma ferramenta didática de planejamento, apresentada sempre como faixa de probabilidade.

### Journal

Memória de investimento: registre teses de investimento por ativo, decisões tomadas e revisões periódicas. Não afeta nenhum cálculo de outra tela — é só um diário estruturado.

### Sincronizar Dividendos.me

Integração opcional com o [Dividendos.me](https://dividendos.me) via Playwright (scraping da sua própria conta). Sempre mostra um preview antes de qualquer alteração:
- **dry-run** — só mostra o que seria importado, não altera nada.
- **update** — atualiza posições incrementalmente.
- **replace** — substitui toda a carteira; exige digitar a palavra de confirmação exata antes do botão ficar habilitado.

Bitcoin é sempre tratado em USD (nunca convertido silenciosamente); Tesouro Direto é sempre tratado em BRL. Se uma seção esperada do Dividendos.me não for encontrada durante o scraping, a sincronização bloqueia por segurança em vez de prosseguir com dados parciais.

### Configurações

Ambiente, câmbio USD/BRL (automático via BCB PTAX com fallback Yahoo Finance, ou manual), atualização de preços em lote, e as **três camadas de alocação-alvo**, organizadas em abas:
- **Alocação simples** — um número por classe de ativo (ex.: FIIs = 20%).
- **Regras detalhadas** — mínimo/alvo/máximo por classe, moeda, país ou ativo específico, com prioridade manual. Têm precedência sobre a política geral para a mesma dimensão.
- **Política de investimento geral** — perfil, limites amplos (peso máximo por ativo, peso máximo em cripto/FIIs, exposição internacional-alvo). Funciona como fallback só para dimensões sem regra detalhada própria.
- **Visão geral** — mostra exatamente qual camada está valendo hoje para cada dimensão (regra detalhada > política geral > nenhum limite) e qualquer conflito entre elas.
- **Simulação** — premissas de retorno/volatilidade por classe usadas no Monte Carlo.
- **Sistema** — ambiente, banco de dados (credenciais sempre mascaradas na tela), contagem de ativos cadastrados.

Nenhuma regra aqui gera venda automática — sempre um aviso fixo lembra disso em toda seção relacionada a alocação.

## Como interpretar os principais indicadores

- **LG Score (0–100):** nota simples por ativo (Qualidade, Valuation, Crescimento, Risco, Alocação), com Confidence Score refletindo a qualidade do dado disponível.
- **LG Conviction Score v2 (0–100):** metodologia mais completa (Qualidade, Valuation, Crescimento, Risco, Reinvestimento de Capital), com pesos por classe de ativo — usada pela Inteligência e pelo Aporte v3.
- **Portfolio Health Score:** score agregado de 5 sinais diferentes (diversificação, qualidade média, risco, alinhamento com a política, dados disponíveis) em um único número — é um relatório informativo, nunca uma recomendação de compra/venda.
- **Confiança do dado:** sempre que um score ou análise depende de dados incompletos, isso aparece explicitamente — nunca é escondido nem preenchido com um valor inventado.

## Perguntas frequentes

**Preciso usar o Dividendos.me?** Não — é opcional. Sem ele, importe a carteira manualmente via CSV/Excel na tela Carteira.

**A LG INVEST executa compras/vendas?** Nunca. Ela só organiza dados e sugere uma distribuição de aporte; a execução é sempre manual, na sua corretora.

**Por que um ativo aparece com "dados insuficientes"?** Geralmente porque o Yahoo Finance não tem cobertura completa para aquele ticker (comum em ações brasileiras menores e FIIs). Use a importação manual de fundamentos (tela Ativos) como fallback.

**Como faço backup antes de uma operação arriscada?** `python -m scripts.backup_database` — ver `docs/LOCAL_RUNBOOK.md`.
