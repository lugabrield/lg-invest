"""Resultado estruturado de uma importação de carteira (Volume 4, seção 14).

Permite reportar de forma auditável quantas linhas entraram, quantas
foram atualizadas, quantas foram ignoradas e os erros por linha, sem
abortar o processamento das linhas válidas.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ImportError:
    """Erro associado a uma linha específica do arquivo."""

    line: int
    field: str | None
    message: str

    def as_dict(self) -> dict:
        return {"line": self.line, "field": self.field, "message": self.message}


@dataclass
class ImportResult:
    """Resumo do processamento de um arquivo de importação."""

    total_rows: int = 0
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[ImportError] = field(default_factory=list)

    def add_error(self, line: int, message: str, field_name: str | None = None) -> None:
        self.errors.append(ImportError(line=line, field=field_name, message=message))
        self.skipped += 1

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def as_dict(self) -> dict:
        return {
            "total_rows": self.total_rows,
            "imported": self.imported,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": [e.as_dict() for e in self.errors],
        }
