"""Configurações globais da aplicação LG INVEST.

Carrega variáveis a partir do arquivo .env. Nenhuma chave de API
deve ser escrita diretamente no código (Volume 14 / Volume 18).

Este módulo é apenas infraestrutura de setup: não contém regra
de negócio nem cálculo financeiro.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação lidas do ambiente (.env)."""

    environment: str = "development"
    database_url: str = "sqlite:///./data/lg_invest.db"
    log_level: str = "INFO"

    # Flags de provedores de dados
    yahoo_finance_enabled: bool = True
    # Câmbio automático (Sprint 12): BCB PTAX é a fonte primária, gratuita
    # e sem chave; desligar aqui pula direto para o fallback Yahoo/manual.
    bcb_fx_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Instância única reutilizável pela aplicação.
settings = Settings()
