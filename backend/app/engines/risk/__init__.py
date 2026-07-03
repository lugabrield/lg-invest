"""Risk Engine v1 (Sprint 16 / Fase 2).

Classificação de risco de balanço/mercado por indicadores estáticos
(dívida/EBITDA, beta) — heurística própria e deliberadamente simples,
sem VaR, Monte Carlo ou qualquer otimização quantitativa (fora do
escopo do MVP, ver instruções do projeto). Não acessa banco, yfinance
nem Streamlit — ver `backend/tests/unit/test_engine_purity.py`.
"""
