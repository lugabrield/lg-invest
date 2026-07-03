"""Leitor de arquivos de importação (CSV e Excel).

Converte um arquivo em uma lista de linhas, cada uma com seu número de
origem (para mensagens de erro precisas) e os valores como strings
(a tipagem/validação acontece nos schemas e validators).

CSV usa a biblioteca padrão; Excel usa openpyxl. Nenhuma regra de
negócio vive aqui — apenas leitura.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import NamedTuple


class RawRow(NamedTuple):
    """Uma linha bruta do arquivo: número de origem + valores por coluna."""

    line: int  # número da linha no arquivo (cabeçalho = 1; primeira linha de dados = 2)
    data: dict[str, str]


SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".xls"}


def read_rows(path: str | Path) -> list[RawRow]:
    """Lê um arquivo CSV/Excel e devolve as linhas de dados com numeração.

    Levanta ValueError se a extensão não for suportada ou o arquivo
    não tiver cabeçalho.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Extensão não suportada: {suffix}. Use {', '.join(sorted(SUPPORTED_SUFFIXES))}."
        )
    if suffix == ".csv":
        return _read_csv(p)
    return _read_excel(p)


def _read_csv(path: Path) -> list[RawRow]:
    rows: list[RawRow] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Arquivo CSV sem cabeçalho.")
        headers = [h.strip() for h in reader.fieldnames]
        for idx, raw in enumerate(reader, start=2):  # linha 1 é o cabeçalho
            data = {h: (raw.get(h) or "").strip() for h in headers}
            rows.append(RawRow(line=idx, data=data))
    return rows


def _read_excel(path: Path) -> list[RawRow]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - dependência declarada no projeto
        raise ImportError(
            "openpyxl é necessário para ler arquivos Excel. Instale com 'pip install openpyxl'."
        ) from exc

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header_values = next(rows_iter)
    except StopIteration as exc:
        raise ValueError("Arquivo Excel vazio.") from exc

    headers = [str(h).strip() if h is not None else "" for h in header_values]
    result: list[RawRow] = []
    for idx, values in enumerate(rows_iter, start=2):
        if values is None or all(v is None for v in values):
            continue  # ignora linhas totalmente vazias
        data = {
            headers[i]: ("" if values[i] is None else str(values[i]).strip())
            for i in range(len(headers))
            if headers[i]
        }
        result.append(RawRow(line=idx, data=data))
    wb.close()
    return result
