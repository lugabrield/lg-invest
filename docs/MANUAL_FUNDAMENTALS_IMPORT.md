# Importação Manual de Fundamentos (Sprint 28)

## Objetivo

Fallback explícito para quando o Yahoo Finance não cobre um campo
fundamentalista de um ativo (comum em ações brasileiras de segunda
linha — ver `docs/FUNDAMENTAL_DATA_PROVIDERS.md`): o usuário baixa um
modelo CSV, preenche com dados de outra fonte confiável (RI da
empresa, CVM, Status Invest, Fundamentus etc.) e importa pela tela
Ativos. Nenhum ativo novo é criado por essa via — o import só
complementa dados de ativos já cadastrados.

## Onde fica

Tela **Ativos** → seção "Análise Fundamentalista" → bloco
**"Importar fundamentos manualmente (CSV/Excel)"**
(`frontend/streamlit_app/pages_impl/ativos.py`).

## Formato do arquivo

Aceita `.csv`, `.xlsx` e `.xls` (mesmo leitor já usado pela importação
de posições, `etl/importers/file_reader.py::read_rows` — nenhum
parser novo foi criado).

Colunas obrigatórias (`FUNDAMENTALS_IMPORT_REQUIRED_COLUMNS`):

| Coluna | Formato |
|---|---|
| `ticker` | precisa já estar cadastrado em Ativos/Carteira |
| `period_end` | `AAAA-MM-DD` ou `DD/MM/AAAA` |

Colunas opcionais — todas as demais colunas de
`FundamentalSnapshot` (`FUNDAMENTALS_IMPORT_OPTIONAL_COLUMNS`):
`source` (metadado informativo, ver abaixo), `revenue`, `net_income`,
`ebitda`, `ebit`, `free_cash_flow`, `net_debt`, `total_debt`,
`total_cash`, `total_equity`, `roe`, `roic`, `net_margin`,
`operating_margin`, `pe_ratio`, `pb_ratio`, `ev_ebitda`,
`dividend_yield`, `payout_ratio`, `market_cap`. Nenhuma delas é
obrigatória — uma linha pode preencher só `free_cash_flow`, por
exemplo, e deixar o resto vazio.

O botão "Baixar modelo CSV" na própria tela gera um arquivo com todas
essas colunas já no cabeçalho, na ordem certa.

Números aceitam tanto `.` quanto `,` como separador decimal (`"12.5"`
e `"12,5"` são equivalentes).

## A coluna `source`

É só um metadado de auditoria — registra, na mensagem de resultado da
linha, de onde o dado realmente veio (ex.: `"Status Invest"`, `"RI da
empresa"`). **Nunca vira o valor gravado no banco**: todo snapshot
salvo por esta via recebe `source="manual_import"`, para que qualquer
engine/relatório saiba distinguir "veio do Yahoo automaticamente" de
"foi importado manualmente" — sem depender de lembrar o texto livre
que o usuário digitou na coluna `source`.

## Validação linha a linha

Cada linha é validada de forma independente
(`etl/validators/fundamentals_import_validators.py`) — um erro em uma
linha nunca aborta o arquivo inteiro (mesmo padrão já usado pela
importação de posições desde o Sprint 3):

- `ticker` ausente/vazio → erro na linha.
- `period_end` ausente ou em formato não reconhecido → erro na linha.
- Qualquer coluna numérica com valor não conversível para número
  (ex.: `"não é um número"`) → erro na linha, apontando exatamente o
  campo (`field="free_cash_flow"` etc.).
- Linha com `ticker`/`period_end` válidos mas nenhum campo numérico
  preenchido → erro ("nenhum campo fundamentalista preenchido nesta
  linha") — não faz sentido gravar um snapshot vazio.
- Ticker válido no formato mas não cadastrado no banco → erro
  explícito: *"Ticker '...' não está cadastrado. A importação manual
  de fundamentos não cria ativos novos — cadastre-o primeiro em Ativos
  ou Carteira."*

## Regra central: nunca sobrescreve sem confirmação

Se `(ticker, period_end)` já tem um `FundamentalSnapshot` salvo:

- **Sem marcar a caixa "Sobrescrever snapshots existentes"** (padrão):
  a linha fica com status `conflict_pending_confirmation` e
  **não é aplicada** ao banco — a UI mostra quantas linhas ficaram
  pendentes.
- **Marcando a caixa e reimportando o mesmo arquivo**
  (`confirm_overwrite=True`): a linha é aplicada.

Isso é deliberado: a segunda submissão exige que o usuário tenha visto
o resultado da primeira tentativa e decidido conscientemente
sobrescrever — nunca uma sobrescrita silenciosa de um dado que possa
ser mais recente ou mais confiável do que o que está sendo importado.

Linhas para um `(ticker, period_end)` **novo** (sem snapshot existente)
são sempre aplicadas, com ou sem a confirmação marcada.

Ao sobrescrever, apenas as colunas efetivamente preenchidas no arquivo
são alteradas — um campo já existente no banco que não aparece na
linha importada (ou aparece vazio) permanece intocado, nunca é zerado
(`FundamentalsRepository.upsert_fields`, testado em
`test_import_existing_snapshot_with_confirmation_overwrites`).

## Depois de importar: recomputação automática

Para cada ticker efetivamente alterado (`tickers_recomputed`), o
serviço reaproveita a mesma rotina de recomputação da Central de Dados
(`DataRefreshService._recompute_analysis`, nunca duplicada): tenta
recalcular Trap Detection, Valuation Engine 2.0 (só ações) ou Análise
de Renda Imobiliária (só FII/REIT), e os scores. O resultado da
importação mostra quantos tickers foram recomputados e quantas dessas
recomputações efetivamente rodaram (`valuation_recalculated`,
`traps_recalculated`, `scores_recalculated`).

## Garantias (Volume 18 §8)

- **Nunca cria `Asset` novo** — só complementa fundamentos de ativos
  já cadastrados.
- **Nunca cria `Position`** — importar fundamentos não afeta carteira,
  patrimônio ou posições.
- **Nunca inventa valor** — uma coluna vazia numa linha simplesmente
  não altera aquele campo; nunca é preenchida com `0` ou uma média.
- **Nunca recomenda compra/venda** — a importação só persiste dado,
  as análises que consomem esse dado é que decidem o que dizer sobre
  ele (e continuam sem recomendar transação, como sempre).

## Como validar localmente

1. Tela Ativos → seção "Análise Fundamentalista" → "Importar
   fundamentos manualmente (CSV/Excel)" → "Baixar modelo CSV".
2. Preencha uma linha com um ticker já cadastrado na carteira e um
   `period_end` válido, e ao menos um campo numérico (ex.:
   `free_cash_flow`).
3. Envie o arquivo sem marcar "Sobrescrever" e clique "Importar
   fundamentos" — confira o resumo (linhas, aplicadas, pendentes,
   erros).
4. Reenvie o mesmo arquivo (mesmo ticker/período) sem marcar
   "Sobrescrever" — a linha deve aparecer como pendente de
   confirmação, e o valor no banco não muda.
5. Marque "Sobrescrever" e reenvie — agora a linha é aplicada.
6. Confira, na seção "Dados usados e dados ausentes" do próprio
   ticker, que o campo importado agora aparece disponível, com
   `fonte manual_import`.
7. Testes automatizados:
   `PYTHONPATH=... python -m pytest backend/tests/unit/test_fundamentals_import_service.py -v`.

## O que ficou fora desta sprint

- Importação em lote de múltiplos arquivos de uma vez, ou agendamento
  de importação recorrente — cada import é um upload manual único.
- Edição de um campo já importado diretamente pela UI (sem reimportar
  o arquivo inteiro) — hoje a única forma de corrigir um valor
  importado é reimportar a linha com o valor certo (com confirmação).
- Suporte a formatos além de CSV/Excel (ex.: colar texto direto na
  tela).
