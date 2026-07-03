"""Garante que nenhum engine depende de banco, yfinance ou Streamlit.

Sprint 11 formaliza como teste automático o que já era uma regra do
projeto: `backend/app/engines/` deve ser puro (SQLAlchemy, yfinance e
Streamlit só vivem em `services/`, `infrastructure/` e
`frontend/streamlit_app/`). Varre a árvore de imports (AST) de cada
módulo em `engines/` — não depende de convenção nem de revisão manual.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ENGINES_ROOT = Path(__file__).resolve().parents[2] / "app" / "engines"
FORBIDDEN_MODULES = ("streamlit", "yfinance", "sqlalchemy")


def _engine_files() -> list[Path]:
    return sorted(ENGINES_ROOT.rglob("*.py"))


def _imported_module_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


@pytest.mark.parametrize(
    "path",
    _engine_files(),
    ids=lambda p: str(p.relative_to(ENGINES_ROOT)),
)
def test_engine_module_has_no_forbidden_imports(path: Path) -> None:
    modules = _imported_module_names(path)
    offending = [
        m
        for m in modules
        if any(m == forbidden or m.startswith(forbidden + ".") for forbidden in FORBIDDEN_MODULES)
    ]
    assert not offending, f"{path} importa módulo(s) proibido(s) para um engine: {offending}"


def test_at_least_one_engine_file_was_scanned() -> None:
    """Trava contra um erro de path que faria o teste acima passar vazio."""
    assert len(_engine_files()) >= 4  # portfolio, lg_score, decision, portfolio_diagnostics
