# Checklist Final do MVP — LG INVEST

Verificação dos critérios de aceite do MVP (Volume 17) ao final do Sprint 10.

## Critérios de aceite do MVP

- [x] **Usuário cadastra uma carteira completa** — cadastro de ativos + importação de posições via CSV/Excel (Sprint 3).
- [x] **Sistema atualiza preços de ações BR e ETFs US** — ETL via yfinance, provider substituível, coleta incremental (Sprint 4).
- [x] **Dashboard mostra valor total e pesos corretamente** — Portfolio Engine + tela Dashboard (Sprints 5 e 8).
- [x] **LG Score calculado para todos os ativos** — LG Score v1 com 5 pilares, explicação e confiança (Sprint 6).
- [x] **Usuário informa aporte e recebe sugestão explicada** — Decision Engine v1 com justificativa por ativo (Sprint 7).
- [x] **Usuário registra uma decisão no Journal** — Investment Journal com teses, revisões e diário (Sprints 2 e 9).
- [x] **Cálculos principais cobertos por testes** — 153 testes, engines 98%, cobertura total 86% (Sprint 10).
- [x] **Projeto roda localmente em poucos minutos** — instruções no README, setup em < 10 min.
- [x] **Nenhuma chave de API no código** — tudo via `.env`; `.env.example` documentado.

## Checklist de entrega de sprint (Volume 18 §15)

- [x] Todos os testes passam.
- [x] Código formatado com black.
- [x] Lint (ruff) sem erros.
- [x] Sem chaves de API no repositório.
- [x] README atualizado.
- [x] Premissas financeiras documentadas (docstrings + docs).
- [x] Módulos novos possuem testes.
- [x] Recomendações são explicáveis.
- [x] Dados ausentes tratados corretamente.
- [x] Resultados principais validados manualmente (end-to-end e regressão).

## Engines financeiras (Volume 20)

- [x] Portfolio Engine v1 — puro, recebe dados tratados, testes com valores conhecidos.
- [x] LG Score v1 — 5 pilares 0–100, score final 0–100, notas parciais, explicação, neutralidade quando falta dado.
- [x] Decision Engine v1 — distribuição do aporte, soma ≤ aporte, não sugere bloqueado, penaliza concentração, prioriza subalocado, auditoria.

## Interface (LG Terminal)

- [x] 6 telas: Dashboard, Carteira, Ativos, Aporte, Journal, Configurações.
- [x] Interface consome os engines; não duplica cálculo.
- [x] Renderização validada com streamlit AppTest.

## Estado

**MVP completo.** Os 10 sprints do plano foram entregues. Evoluções pós-MVP (valuation DCF/DDM, risco agregado, simulação Monte Carlo, IA, multiusuário, integração com corretoras) estão documentadas como próximos passos.
