"""Helper de sessão de banco para o Streamlit.

O Streamlit reexecuta o script a cada interação; abrir uma sessão de
curta duração por operação é simples e seguro para o MVP.
"""

from __future__ import annotations

from contextlib import contextmanager

from backend.app.infrastructure.database.session import SessionLocal


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
