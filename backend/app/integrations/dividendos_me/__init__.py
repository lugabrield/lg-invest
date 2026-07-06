"""Integração com o Dividendos.me (Sprint 23).

Ver docs/DIVIDENDOS_ME_INTEGRATION.md para o diagnóstico técnico
completo (por que Playwright em vez de API, por que só local, riscos
conhecidos) e docs/DATA_QUALITY.md para como a origem da posição
(`Position.source`) se relaciona com o restante da plataforma.

Módulos:
- `secrets.py`: leitura seguem de credenciais (.env / st.secrets) e
  utilitários de mascaramento — nunca expõe o valor real.
- `parser.py`: normalização pura de números, percentuais e tickers
  (sem rede, sem banco) — testável isoladamente.
- `schemas.py`: DTOs Pydantic (posição extraída, preview, resultado).
- `auth.py`: login via Playwright — mensagens de erro sempre genéricas.
- `client.py`: orquestra login + navegação + extração das tabelas já
  renderizadas. Faz sessão nova a cada chamada, nunca persiste cookie.
- `service.py`: fronteira com o banco — dry-run/replace/update.
"""
