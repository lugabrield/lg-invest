# Frontend — LG Terminal

Interface do MVP em Streamlit. Apenas apresentação: nenhum cálculo
financeiro é feito aqui — tudo vem dos serviços/engines do backend
(Volume 20, prompt 11).

Rodar:
    streamlit run frontend/streamlit_app/app.py

Estrutura:
- `app.py` — navegação e seletor de carteira.
- `db.py` — sessão de banco de curta duração por interação.
- `pages_impl/` — uma tela por módulo: dashboard, carteira, ativos, aporte, journal, configuracoes.

Telas: Dashboard (PortfolioService), Carteira (importação CSV/Excel),
Ativos (LG Score explicável), Aporte (DecisionService), Journal
(JournalService), Configurações (ambiente + atualização de preços).
