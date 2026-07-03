"""Target Allocation Engine (Sprint 17 / Fase 2).

Compara a alocação atual da carteira (já calculada pelo Portfolio
Engine) com a alocação-alvo configurada pelo usuário, por classe de
ativo. Não sugere QUAL ativo comprar — isso é papel do Decision Engine
(Sprint 18); aqui só se identifica ONDE a carteira está desviada da
meta. Não acessa banco, yfinance nem Streamlit — ver
`backend/tests/unit/test_engine_purity.py`.
"""
