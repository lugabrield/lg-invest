"""Valuation Engine v1 (Sprint 15 / Fase 2).

Classificação de valuation por múltiplos estáticos (P/L, P/VP,
EV/EBITDA, Dividend Yield) — heurística própria e simples, não uma
réplica de metodologia de nenhum autor ou fundo específico. Não faz
DCF/DDM nem qualquer projeção de fluxo de caixa (fora do escopo desta
sprint, ver `docs/FUNDAMENTALS_ENGINE_PLAN.md` e o plano macro da
Fase 2). Não acessa banco, yfinance nem Streamlit — ver
`backend/tests/unit/test_engine_purity.py`.
"""
