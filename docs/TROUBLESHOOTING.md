# Solução de Problemas — LG INVEST v1.0

Problemas comuns e como resolver. Se o seu problema não estiver aqui, veja "Como reportar um problema" no final.

## Instalação

### `ModuleNotFoundError` ao rodar qualquer comando

Faltou instalar as dependências ou ativar o ambiente virtual.

```bash
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### Erro de versão do Python

A LG INVEST exige **Python 3.11 ou superior**. Confira com `python --version`. Se seu sistema tem várias versões, use `python3.11 -m venv .venv` explicitamente ao criar o ambiente.

### `playwright install` falha ou trava

Isso só afeta a sincronização com o Dividendos.me — o resto do app funciona normalmente sem o Playwright instalado. Se quiser usar essa integração depois, rode `playwright install chromium` novamente com mais espaço em disco/rede disponível.

## Banco de dados e migrations

### Erro "no such table" ou "no such column" ao abrir o app

O banco está desatualizado em relação ao código. Rode:

```bash
python -m alembic upgrade head
```

Sempre rode este comando depois de atualizar o código (`git pull`).

### Quero recomeçar do zero (apagar todos os dados)

**Faça backup primeiro se houver qualquer dado que você queira manter:**

```bash
python -m scripts.backup_database
```

Depois, apague `data/lg_invest.db` e rode `python -m alembic upgrade head` de novo para recriar o banco vazio.

### `alembic upgrade head` falha com erro de migration

Confirme que está rodando o comando na raiz do projeto (onde está `alembic.ini`). Se o erro persistir, restaure o último backup (`data/backups/`) e reporte o erro — não é esperado em uso normal.

## Preços e fundamentos

### Preços não atualizam / "Não foi possível atualizar o preço agora"

Geralmente é falta de internet ou o Yahoo Finance está temporariamente indisponível/limitando requisições. Tente novamente em alguns minutos. Se o ativo está marcado como manual (`is_manual`), a atualização automática é pulada de propósito — cadastre o preço manualmente na tela Ativos.

### Um ativo aparece sempre com "dados insuficientes" ou fundamentos ausentes

Comum em ações brasileiras menores e FIIs — a cobertura do Yahoo Finance varia por ticker. Use a importação manual de fundamentos (tela Ativos → "Importar fundamentos manualmente") com dados de outra fonte (RI da empresa, CVM, etc.). A LG INVEST nunca inventa um valor ausente.

### Câmbio USD/BRL não atualiza automaticamente

O BCB PTAX é a fonte primária; se estiver indisponível, o app tenta o Yahoo Finance como fallback. Se ambos falharem, defina o câmbio manualmente em Configurações → Câmbio USD/BRL → "Sobrescrever câmbio manualmente".

## Sincronização com o Dividendos.me

### Botões de sincronização aparecem desabilitados

O Playwright não está instalado, ou as credenciais (`DIVIDENDOS_ME_EMAIL`/`DIVIDENDOS_ME_PASSWORD`) não estão configuradas no `.env`. A tela mostra qual dos dois está faltando.

### Sincronização falha com erro de login

Confirme as credenciais no `.env`. Se o Dividendos.me tiver um captcha ou verificação adicional, o login automático pode não conseguir passar — nesse caso, a sincronização não é possível até o site mudar ou você usar a importação manual via CSV/Excel.

### "Seção esperada não encontrada" / sincronização bloqueada

O Dividendos.me mudou a estrutura de alguma página que o scraper espera. Isso é uma proteção intencional: a LG INVEST prefere bloquear a sincronização a importar dados parciais/incorretos silenciosamente. Reporte o problema (pode indicar que o parser precisa de ajuste); enquanto isso, importe manualmente via CSV/Excel.

### Bitcoin aparece com valor errado depois de sincronizar

Bitcoin é sempre tratado em USD pela LG INVEST (nunca convertido silenciosamente durante a sincronização). Se o valor parece errado, confira se o câmbio USD/BRL configurado em Configurações está correto — a conversão para exibição acontece só no Dashboard.

## Interface (Streamlit)

### A tela trava ou fica em "Running..." por muito tempo

Normal durante atualização de preços/fundamentos em lote (pode levar minutos dependendo do tamanho da carteira e da resposta do Yahoo Finance). Se travar por mais de alguns minutos sem progresso, feche o terminal e reabra o app — nenhuma operação parcial corrompe o banco (as escritas são transacionais).

### Erro genérico na tela ("Falha inesperada... Tente novamente")

A LG INVEST nunca mostra o texto técnico bruto de uma exceção ao usuário — mensagens assim indicam uma falha de rede/fonte externa que não foi possível completar. Tente de novo; se persistir, rode o mesmo fluxo por linha de comando (`docs/LOCAL_RUNBOOK.md`) para ver o erro técnico completo no terminal.

### A porta 8501 já está em uso

Outra instância do Streamlit já está rodando. Feche-a, ou abra em outra porta: `streamlit run frontend/streamlit_app/app.py --server.port 8502`.

## Testes e qualidade de código

### `pytest` falha depois de um `git pull`

Rode `pip install -r requirements-dev.txt` de novo (dependências podem ter mudado) e `python -m alembic upgrade head`.

### `ruff check` ou `black --check` acusam problemas em arquivos que você não tocou

Verifique se está na branch/versão certa. Se persistir, rode `black .` para autoformatar antes de investigar mais.

## Como reportar um problema

1. Rode o comando equivalente por linha de comando (ver `docs/LOCAL_RUNBOOK.md`) para capturar o erro técnico completo — a interface esconde detalhes técnicos de propósito.
2. Anote: o que você estava tentando fazer, o comando/tela usado, e a mensagem de erro completa.
3. Confira se um `python -m alembic upgrade head` recente resolve (banco desatualizado é a causa mais comum de erros estranhos).
4. Se envolver dados sensíveis da sua carteira, remova-os do log antes de compartilhar.
