"""Testes do script de backup do banco (Sprint 31 — RC v1.0, Parte 9).

`scripts/backup_database.py` é deliberadamente simples: copiar o arquivo
SQLite para `data/backups/`. Estes testes usam `tmp_path` e monkeypatch de
`settings` para nunca tocar no banco real do projeto (`data/lg_invest.db`).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from scripts import backup_database as bd


class _FakeSettings:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url


@pytest.fixture
def fake_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Simula a raiz do projeto: cria `data/lg_invest.db` sob `tmp_path` e
    faz `_resolve_sqlite_path` resolver relativo a ela, em vez de à raiz
    real do repositório (`Path(__file__).resolve().parents[1]`)."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "lg_invest.db"
    db_path.write_bytes(b"fake sqlite content")

    monkeypatch.setattr(bd, "settings", _FakeSettings("sqlite:///./data/lg_invest.db"))

    def _fake_resolve(database_url: str) -> Path | None:
        if not database_url.startswith(bd._SQLITE_PREFIX):
            return None
        relative = database_url[len(bd._SQLITE_PREFIX) :]
        return (tmp_path / relative).resolve()

    monkeypatch.setattr(bd, "_resolve_sqlite_path", _fake_resolve)
    return tmp_path


def test_backup_database_copies_file_to_backups_dir(fake_project: Path) -> None:
    backup_path = bd.backup_database()

    assert backup_path.exists()
    assert backup_path.parent == fake_project / "data" / "backups"
    assert backup_path.read_bytes() == b"fake sqlite content"
    assert backup_path.name.startswith("lg_invest_")
    assert backup_path.suffix == ".db"


def test_backup_database_never_removes_backups_without_keep_last(fake_project: Path) -> None:
    bd.backup_database()
    time.sleep(1.1)  # timestamp tem granularidade de segundo
    bd.backup_database()

    backups = sorted((fake_project / "data" / "backups").glob("*.db"))
    assert len(backups) == 2


def test_backup_database_keep_last_prunes_oldest(fake_project: Path) -> None:
    bd.backup_database()
    time.sleep(1.1)
    bd.backup_database()
    time.sleep(1.1)
    newest = bd.backup_database(keep_last=1)

    backups = sorted((fake_project / "data" / "backups").glob("*.db"))
    assert backups == [newest]


def test_backup_database_raises_when_db_missing(fake_project: Path) -> None:
    (fake_project / "data" / "lg_invest.db").unlink()

    with pytest.raises(FileNotFoundError, match="alembic upgrade head"):
        bd.backup_database()


def test_backup_database_raises_for_non_sqlite_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bd, "settings", _FakeSettings("postgresql://user:pass@host/db"))

    with pytest.raises(RuntimeError, match="não é SQLite"):
        bd.backup_database()


def test_resolve_sqlite_path_returns_none_for_non_sqlite_url() -> None:
    assert bd._resolve_sqlite_path("postgresql://user:pass@host/db") is None


def test_main_prints_backup_path_on_success(
    fake_project: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `main()` faz `argparse.parse_args()` sobre `sys.argv` — sem isolar,
    # ele tentaria interpretar os argumentos do próprio pytest.
    monkeypatch.setattr("sys.argv", ["backup_database.py"])

    bd.main()

    captured = capsys.readouterr()
    assert "Backup criado:" in captured.out


def test_main_exits_with_error_when_db_missing(
    fake_project: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["backup_database.py"])
    (fake_project / "data" / "lg_invest.db").unlink()

    with pytest.raises(SystemExit) as exc_info:
        bd.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Backup não realizado" in captured.err
