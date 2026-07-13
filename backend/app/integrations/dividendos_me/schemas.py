"""DTOs da integração com o Dividendos.me (Sprint 23).

Estruturas serializáveis que descrevem: uma posição já normalizada
extraída do site, o preview de sincronização (com diff contra a LG
INVEST) e o resultado de uma execução (dry-run/replace/update). Nenhum
cálculo financeiro vive aqui — só composição de dados já extraídos e
normalizados por `parser.py`/`client.py`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

# Rótulos de origem usados em `Position.source` e no diff do preview —
# um por seção do Dividendos.me (Sprint 23: Brasil e EUA sob Renda
# Variável são as seções confirmadas; novas seções podem ser adicionadas
# em `client.py` sem mudar este schema).
ORIGIN_B3 = "dividendos_me:b3"
ORIGIN_INTERNATIONAL = "dividendos_me:international"
# Origem própria para Criptomoedas (Sprint 23.2 — correção): a tela
# correta é "Criptomoedas → Extrato" (nunca "Meu Resumo"), e os valores
# lá são exibidos em R$ (BRL), não em USD — por isso cripto tem sua
# própria origem em vez de reaproveitar ORIGIN_INTERNATIONAL.
ORIGIN_CRYPTO = "dividendos_me:crypto"

# Status do preview/execução (Sprint 23.1 — bug real de extração
# incompleta classificada como "success" motivou esta distinção):
# "success": extração parece confiável (ativos válidos suficientes,
#   nenhuma condição de risco disparada); "partial": alguma seção falhou
#   ou parte dos ativos não foi reconhecida, mas há dado suficiente para
#   olhar o preview (replace continua bloqueado se as regras de
#   segurança disparar); "failed": não há ativos válidos suficientes
#   para considerar a extração minimamente confiável.
PREVIEW_STATUSES = ("success", "partial", "failed")

# Número mínimo de posições válidas (ticker reconhecido, não
# `review_required`) para o preview poder ser "success". Abaixo disso,
# mesmo que um patrimônio total tenha sido encontrado, o preview vira
# "partial" (patrimônio mas nenhum/poucos ativos) ou "failed" (nada).
MIN_VALID_ASSETS_FOR_SUCCESS = 2

# Status do patrimônio total do preview (Sprint 23.3 — correção: um dry-run
# que só extraiu Brasil não pode apresentar `total_patrimonio` como se
# fosse o patrimônio consolidado da carteira inteira). "consolidated":
# todas as seções esperadas (derivadas da carteira atual — ver
# `service._expected_sections_from_current`) vieram nesta execução.
# "partial": pelo menos uma seção esperada não veio — o número existe,
# mas é só uma fração do patrimônio real, e a UI/CLI devem deixar isso
# explícito em vez de apresentar como total consolidado.
TOTAL_PATRIMONIO_STATUSES = ("consolidated", "partial")


class NormalizedTicker(BaseModel):
    """Resultado da normalização de um ticker bruto (`parser.normalize_position`)."""

    ticker: str
    asset_class: str
    country: str
    currency: str
    is_manual: bool = False
    review_required: bool = False
    review_reason: str | None = None


class ExtractedPosition(BaseModel):
    """Uma posição já normalizada, extraída de uma seção do Dividendos.me.

    Campos opcionais (`average_price`, `current_price`, etc.) ficam
    `None` quando a tabela de origem não trouxe o dado — nunca são
    inventados a partir de outro campo.
    """

    raw_ticker: str
    name: str | None = None

    ticker: str
    asset_class: str
    country: str
    currency: str
    is_manual: bool = False
    review_required: bool = False
    review_reason: str | None = None
    section: str | None = None
    """Seção de origem no Dividendos.me ("brasil"/"eua"/"criptomoedas"/
    "renda_fixa"), preservada mesmo quando `ticker` fica vazio — necessária
    para redes de segurança pós-extração (ex.: mapear uma criptomoeda sem
    ticker para BTC-USD em `service.py`) que não podem confiar só em
    `asset_class`/`origin`, pois um ticker vazio nunca chega a ser
    classificado (ver Sprint 23.2)."""

    quantity: Decimal
    average_price: Decimal | None = None
    current_price: Decimal | None = None
    current_value: Decimal | None = None
    return_pct: Decimal | None = None
    daily_change_pct: Decimal | None = None
    dividend_yield_pct: Decimal | None = None
    v_vp: Decimal | None = None

    origin: str  # ORIGIN_B3 | ORIGIN_INTERNATIONAL (ou outra seção futura)
    synced_at: datetime

    model_config = {"from_attributes": True}


class SyncDiff(BaseModel):
    """Comparação entre o que veio do Dividendos.me e o estado atual da LG INVEST."""

    kept: list[str] = []
    """Tickers com posição igual nas duas fontes (nada muda)."""
    updated: list[str] = []
    """Tickers já existentes na LG INVEST com quantidade/preço diferentes."""
    created: list[str] = []
    """Tickers novos, sem posição atual na LG INVEST."""
    missing_in_source: list[str] = []
    """Tickers que existem na LG INVEST mas não vieram do Dividendos.me —
    serão REMOVIDOS no modo replace. Sempre mostrado com destaque no preview."""

    @property
    def removed_in_replace(self) -> list[str]:
        """Alias explícito: no modo replace, `missing_in_source` é exatamente
        o que será removido — nome separado só para deixar a UI mais clara."""
        return self.missing_in_source


class SectionDiagnostics(BaseModel):
    """Diagnóstico de uma seção extraída — nunca inclui HTML bruto nem
    dado sensível, só contagens e motivos de rejeição já sanitizados
    (vindos de `NormalizedTicker.review_reason`)."""

    section: str
    selector_used: str
    raw_rows_detected: int = 0
    valid_rows: int = 0
    rejected_rows: int = 0
    rejection_reasons: list[str] = []
    navigation_detail: str | None = None
    """Sprint 23.3 — instrumentação de navegação: registra, sem dado
    sensível, o que aconteceu ao tentar chegar nesta seção (ex.: se o
    acordeão foi encontrado/clicado, a URL final após o clique, se uma
    nova tentativa de leitura foi necessária). Existe especificamente
    para diagnosticar seções que "navegam sem erro" mas voltam vazias
    (ver `client.py::_goto_section`) — nunca inclui HTML bruto."""

    # Diagnóstico reforçado do histórico mensal de proventos (ajuste
    # pós-Sprint 25, Parte 3): sinais binários/contagens sobre o estado
    # final da página — nunca HTML bruto, nunca dado sensível. Vazio
    # (`[]`/`0`/`False`/`None`) para seções que não chamam
    # `_diagnose_income_page` (ex.: carteira, calendário futuro).
    final_url: str | None = None
    """URL da página no momento em que o diagnóstico foi coletado — não é
    sensível (é a mesma URL que aparece na barra de endereço do usuário)."""
    tabs_found: list[str] = []
    """Quais rótulos de aba conhecidos ("Análise", "Próximos Dividendos")
    foram de fato encontrados na página no momento da coleta."""
    wallet_selectors_found: list[str] = []
    """Quais rótulos de carteira conhecidos ("Carteira (B3)", "Carteira
    Dolar") foram de fato encontrados na página no momento da coleta."""
    table_elements_found: int = 0
    """Quantidade de elementos `<table>` presentes no DOM no momento da
    coleta — 0 é um sinal forte de que o conteúdo não é uma tabela HTML
    (ex.: pode estar em canvas/svg, ver `canvas_or_svg_detected`)."""
    canvas_or_svg_detected: bool = False
    """True quando o DOM tem pelo menos um `<canvas>`/`<svg>` — indício de
    que o dado é renderizado como gráfico (ApexCharts/Highcharts/D3), não
    como tabela, e não pode ser extraído pelo seletor de tabela atual."""
    debug_snapshot_path: str | None = None
    """Caminho local do HTML sanitizado salvo em modo debug (nunca
    enviado a lugar nenhum) — `None` quando o modo debug não foi pedido."""
    debug_screenshot_path: str | None = None
    """Caminho local do screenshot salvo em modo debug — `None` quando o
    modo debug não foi pedido."""


class SyncPreview(BaseModel):
    """Preview de uma sincronização — nunca grava nada no banco."""

    portfolio_id: int
    total_patrimonio: Decimal
    total_patrimonio_status: str = "consolidated"
    """"consolidated" | "partial" — ver `TOTAL_PATRIMONIO_STATUSES` (Sprint
    23.3). "partial" sempre que `sections_expected` tiver alguma seção
    que não veio nesta execução (ver `sections_failed`) — a UI/CLI nunca
    devem apresentar `total_patrimonio` como consolidado nesse caso."""
    total_assets: int
    """Conta só posições válidas (ticker reconhecido, `review_required=False`).
    Nunca inclui posições vazias/rejeitadas — ver Sprint 23.1."""
    positions: list[ExtractedPosition]
    diff: SyncDiff
    status: str = "success"
    """"success" | "partial" | "failed" — ver `PREVIEW_STATUSES`. Calculado
    por `service.py` a partir de `total_assets`, `sections_failed` e
    `review_required_tickers`; nunca "success" com patrimônio > 0 e
    poucos/nenhum ativo válido reconhecido."""
    sections_expected: list[str] = []
    """Seções que a carteira ATUAL da LG INVEST indica que deveriam vir
    nesta extração (Sprint 23.3): derivadas da classe/país dos ativos já
    existentes (ex.: há um ativo `crypto` -> "criptomoedas" é esperada). Ver
    `service._expected_sections_from_current`. "brasil" sempre é esperada
    se a carteira atual tem qualquer ativo BR."""
    sections_failed: list[str] = []
    """Seções que não puderam ser extraídas nesta execução — inclui tanto
    seções que lançaram erro real (layout mudou, timeout) quanto seções
    esperadas (`sections_expected`) que navegaram sem erro mas voltaram
    com zero linhas/cards (Sprint 23.3 — corrige o preview reportar
    "success" quando EUA/Criptomoedas/Renda Fixa vêm vazios silenciosamente).
    Ativos dessas seções não aparecerão no preview nem serão preservados
    no modo replace."""
    review_required_tickers: list[str] = []
    diagnostics: list[SectionDiagnostics] = []
    generated_at: datetime

    model_config = {"from_attributes": True}


class SyncRunResult(BaseModel):
    """Resultado de uma execução de sincronização (dry-run/replace/update)."""

    run_id: int | None = None
    provider: str = "dividendos_me"
    mode: str
    status: str
    portfolio_id: int

    assets_found: int = 0
    positions_created: int = 0
    positions_updated: int = 0
    positions_removed: int = 0
    errors: list[str] = []

    started_at: datetime
    finished_at: datetime | None = None

    preview: SyncPreview | None = None

    model_config = {"from_attributes": True}


class IncomeEventPreviewItem(BaseModel):
    """Um evento de provento já normalizado, só para exibição no preview
    (amostra) — nunca é o que é gravado no banco (ver `IncomeEvent`)."""

    ticker: str | None
    event_type: str
    status: str
    payment_date: date | None = None
    amount_total: Decimal
    currency: str
    source: str


class IncomeSyncPreview(BaseModel):
    """Preview de proventos/dividendos — nunca grava nada no banco.

    Separado de `SyncPreview` (carteira) de propósito: proventos podem
    falhar/ficar parciais sem que isso bloqueie a sincronização da
    carteira (Prioridade explícita do usuário) — os dois preview têm
    ciclos de vida e regras de bloqueio independentes.
    """

    portfolio_id: int
    events_found: int = 0
    """Total de linhas brutas consideradas (antes da deduplicação dentro
    do próprio lote) — ver `diagnostics` para o detalhe por seção."""
    events_valid: int = 0
    events_rejected: int = 0
    period_start: date | None = None
    period_end: date | None = None
    total_by_currency: dict[str, Decimal] = {}
    sections_failed: list[str] = []
    """"income_calendar" — desde a Sprint 23.3, este preview cobre só o
    calendário futuro (aba "Próximos Dividendos"); o histórico mensal
    agregado tem preview próprio (`IncomeMonthlySyncPreview`). Uma falha
    aqui NUNCA bloqueia `replace`/`update` da carteira nem o histórico
    mensal."""
    diagnostics: list[SectionDiagnostics] = []
    sample: list[IncomeEventPreviewItem] = []
    generated_at: datetime

    model_config = {"from_attributes": True}


class IncomeSyncRunResult(BaseModel):
    """Resultado de uma execução de sincronização de proventos
    (dry-run/import). Não tem modo "replace" — proventos são sempre
    aditivos (dedup por chave), nunca substituem/apagam histórico.

    Desde a Sprint 23.3, este schema (e `IncomeSyncPreview`/
    `IncomeEventPreviewItem`) descreve exclusivamente o CALENDÁRIO futuro
    de proventos (aba "Próximos Dividendos", gravado em `income_events`).
    O histórico mensal agregado (aba "Análise") tem seus próprios schemas
    (`IncomeMonthlySyncPreview`/`IncomeMonthlySyncRunResult`, abaixo),
    gravado em `income_monthly_summaries` — nunca misturado aqui."""

    provider: str = "dividendos_me"
    status: str
    portfolio_id: int

    events_found: int = 0
    events_created: int = 0
    events_skipped_duplicate: int = 0
    errors: list[str] = []

    started_at: datetime
    finished_at: datetime | None = None

    preview: IncomeSyncPreview | None = None

    model_config = {"from_attributes": True}


class IncomeMonthlySummaryPreviewItem(BaseModel):
    """Uma linha de resumo mensal já normalizada, só para exibição no
    preview (amostra) — nunca é o que é gravado no banco (ver
    `IncomeMonthlySummary`). Nunca tem ticker/data exata — ver módulo
    docstring de `income_parser.py`."""

    wallet_name: str
    year: int
    month: int
    amount_total: Decimal
    currency: str
    status: str
    annual_total: Decimal | None = None
    annual_average: Decimal | None = None


class IncomeMonthlySyncPreview(BaseModel):
    """Preview do histórico mensal agregado de proventos (Sprint 23.3,
    aba "Central de Proventos" -> "Análise") — nunca grava nada no banco.

    Separado de `IncomeSyncPreview` (calendário futuro) de propósito:
    são fontes/tabelas diferentes (`income_monthly_summaries` vs
    `income_events`), com ciclos de vida e regras de dedup independentes.
    Uma falha aqui nunca bloqueia nem é bloqueada pela sincronização da
    carteira nem pelo calendário futuro.
    """

    portfolio_id: int
    summaries_found: int = 0
    summaries_valid: int = 0
    summaries_rejected: int = 0
    years_found: list[int] = []
    months_found: list[int] = []
    wallets_found: list[str] = []
    total_by_year: dict[str, Decimal] = {}
    """Chave é o ano como string (ex.: "2026") — soma de `amount_total`
    de todos os meses/carteiras daquele ano encontrados nesta execução
    (não é `annual_total`, que vem pronto da própria tabela por carteira)."""
    total_by_currency: dict[str, Decimal] = {}
    sections_failed: list[str] = []
    """"income_monthly" — mesma convenção de `IncomeSyncPreview.sections_failed`."""
    diagnostics: list[SectionDiagnostics] = []
    sample: list[IncomeMonthlySummaryPreviewItem] = []
    generated_at: datetime

    model_config = {"from_attributes": True}


class IncomeMonthlySyncRunResult(BaseModel):
    """Resultado de uma execução de sincronização do histórico mensal
    (dry-run/import). Sempre aditivo (dedup por
    `portfolio_id+wallet_name+year+month+currency+source`) — nunca
    substitui/apaga resumo mensal já salvo."""

    provider: str = "dividendos_me"
    status: str
    portfolio_id: int

    summaries_found: int = 0
    summaries_created: int = 0
    summaries_skipped_duplicate: int = 0
    errors: list[str] = []

    started_at: datetime
    finished_at: datetime | None = None

    preview: IncomeMonthlySyncPreview | None = None

    model_config = {"from_attributes": True}
