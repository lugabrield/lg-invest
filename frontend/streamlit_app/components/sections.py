"""Blocos de seção padronizados (Sprint 11).

Só estrutura visual — dá aos blocos do Dashboard (Visão Geral,
Composição, Riscos, Destaques, Diagnóstico...) o mesmo cabeçalho, para
o app parecer um produto único em vez de telas soltas.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import streamlit as st


def section_header(title: str, icon: str = "", caption: str | None = None) -> None:
    st.markdown(
        f'<div class="lg-section-header"><h3>{icon} {title}</h3></div>',
        unsafe_allow_html=True,
    )
    if caption:
        st.caption(caption)


@contextmanager
def section(title: str, icon: str = "", caption: str | None = None) -> Generator[None, None, None]:
    """Context manager: título padronizado + o conteúdo indentado logicamente abaixo."""
    section_header(title, icon, caption)
    yield
