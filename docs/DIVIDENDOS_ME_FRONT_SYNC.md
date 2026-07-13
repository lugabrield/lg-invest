# Sincronização Dividendos.me — Nova UX (v1.1)

> Regras de segurança gerais em `docs/SECURITY_NOTES.md` — este
> documento é o fluxo de produto/UX e a mecânica técnica específica.
> Endpoints em `docs/API_CONTRACT.md`. Planejado para a Fase 6 do
> `docs/V1_1_MIGRATION_PLAN.md`.

## Por que mudar

Hoje (v1.0.0) as credenciais do Dividendos.me só podem vir de
`.env`/`st.secrets` — o usuário nunca as digita na interface. Isso é
seguro, mas pouco prático: exige editar um arquivo de config toda vez
que a senha muda, e não dá para usar o app "pronto para qualquer
pessoa" sem mexer em texto. A v1.1 move isso para um modal, mantendo o
mesmo nível de segurança (ou melhor, ver abaixo).

## Descoberta importante da auditoria (Fase 0)

`DividendosMeClient(email, password, headless=True)` **já recebe as
credenciais no construtor** — ele nunca leu de `.env`/secrets
internamente. Quem faz essa leitura hoje é a camada acima (CLI e
Streamlit), via `secrets.get_dividendos_me_credentials()`. Isso
significa que a nova API **não precisa mudar nada no client nem no
service de sync** — só precisa parar de chamar
`get_dividendos_me_credentials()` nesse fluxo e usar diretamente o que
veio no body da requisição HTTP. Risco técnico bem menor do que
inicialmente parecia.

## Fluxo desejado (confirmado como viável)

```
1. Usuário clica "Sincronizar Dividendos.me" → abre modal
2. Digita email + senha (nunca fica em localStorage/cookie do navegador)
3. Frontend chama POST /api/dividendos-me/test-login { email, password }
   → backend cria DividendosMeClient(email, password), tenta login,
     descarta o client, responde só { "success": true|false }
4. Se ok, botão "Buscar carteira" habilita
5. Frontend chama POST /api/dividendos-me/dry-run { email, password, portfolio_id }
   → backend roda o mesmo fluxo de dry_run() já existente em
     DividendosMeSyncService, com um client construído com as
     credenciais desta requisição
6. Preview mostrado: ativos encontrados, seções encontradas, diff
   (novo/atualizado/removido), alertas, status (success/partial/failed),
   BTC sempre em USD, Tesouro sempre em BRL — mesmo formato que já
   existe hoje em SyncPreview, sem mudança de schema
7a. Update → POST /api/dividendos-me/sync-update { email, password,
    portfolio_id, confirm: true } — confirmação simples (um clique)
7b. Replace → POST /api/dividendos-me/sync-replace { email, password,
    portfolio_id, confirmation_phrase } — exige frase digitada
    (mesma trava que já existe em service.py::replace hoje)
8. Backend aplica e a função retorna — credenciais em memória saem de
   escopo e são coletadas pelo garbage collector Python normalmente,
   como qualquer variável local
```

## Decisão sobre "manter sessão entre etapas"

O brief perguntava se, tecnicamente, não for possível manter
credenciais entre etapas sem salvar, usar reenvio a cada etapa ou cache
temporário. **Decisão: reenviar a cada etapa (opção mais simples e mais
segura), não usar cache temporário.** Motivos:

- Não há necessidade real de estado entre chamadas — cada etapa
  (test-login, dry-run, update/replace) já é uma operação HTTP
  completa e independente no design atual do `DividendosMeSyncService`.
- Um cache temporário (Redis, memória do processo com TTL) é uma
  superfície de ataque a mais — se o processo do backend for
  comprometido ou tiver um bug de vazamento de memória/log, uma senha
  "esquecida" em cache por alguns minutos é pior do que uma senha que
  nunca é guardada em lugar nenhum.
- O custo (usuário digita a senha de novo entre teste de login e
  dry-run, ou entre dry-run e confirmação) é pequeno — essa é uma ação
  esporádica (sincronizar a carteira), não algo que acontece a cada
  clique do dia a dia. O modal pode manter o campo preenchido em
  memória do componente React **enquanto o modal está aberto** (não
  persistido em nenhum storage do navegador) para não obrigar
  redigitar dentro da mesma sessão de modal — só reseta ao fechar.

## Alternativas mais seguras avaliadas (para o futuro, não agora)

O brief pediu para avaliar: sync local helper, browser extension,
upload manual exportado do Dividendos.me. Avaliação:

- **Upload manual exportado** é objetivamente mais seguro (nunca
  transmite senha nenhuma) mas depende do Dividendos.me oferecer
  exportação de dados — não confirmado que exista; precisa de
  investigação separada antes de virar plano. Se existir, é a opção
  preferível a médio prazo e reduziria a dependência de Playwright por
  completo (eliminaria o problema de "onde roda o Playwright").
- **Sync local helper** (um pequeno programa que o usuário roda na
  própria máquina, fora do deploy web) resolve o problema de
  "Playwright não roda na Vercel", mas frigmenta a experiência (dois
  apps para manter) — só faz sentido se o backend hospedado for
  inviável por algum motivo ainda não identificado.
- **Browser extension** é a opção de maior esforço de desenvolvimento
  e manutenção (código separado, processo de review de extensão) para
  o ganho de segurança que já é atingido de forma mais simples com o
  fluxo backend-only descrito acima.

**Conclusão desta rodada:** seguir com o fluxo via backend seguro
(modal → API → Playwright no backend), que já atinge todas as garantias
de segurança pedidas sem a complexidade adicional das alternativas.
Reavaliar "upload manual" como melhoria futura se/quando confirmarmos
que o Dividendos.me oferece exportação.

## O que NÃO fazer (explicitamente proibido pelo brief, e correto)

- Nunca rodar o scraping direto do navegador do usuário — Playwright é
  Python server-side, não existe equivalente confiável rodando dentro
  do Chrome do usuário sem instalar algo adicional, e tentar around
  isso com fetch direto ao Dividendos.me do navegador do usuário
  esbarraria em CORS (o Dividendos.me não expõe API pública) e
  exporia ainda mais a senha (indo direto do browser para um domínio
  de terceiro sem controle nosso).

## Preview mais rico (Fase 7, mas desenhado aqui para não retrabalhar o schema)

Além do que já existe em `SyncPreview` hoje, adicionar ao payload
exibido no modal (sem mudar a extração, só a apresentação):

- Contagem por classe de ativo e por moeda antes/depois.
- Lista explícita de tickers novos, removidos, atualizados (o diff já
  é calculado internamente em `_compute_diff` — só precisa ser
  exposto por completo na resposta em vez de só usado para status).
- Warnings agrupados por severidade (mesma ideia de `strong_alert_sections`
  já existente).

## Mensagens de erro específicas (Fase 7)

Mapear cada causa conhecida para uma mensagem amigável e um código
identificável (para o frontend decidir o ícone/cor, nunca o texto
literal vindo hardcoded em dois lugares):

| Causa | Código sugerido | Mensagem ao usuário |
|---|---|---|
| Login inválido | `invalid_credentials` | "E-mail ou senha incorretos." |
| Playwright indisponível no servidor | `playwright_unavailable` | "Sincronização temporariamente indisponível — tente novamente mais tarde." |
| Estrutura da página mudou | `extraction_broken` | "O Dividendos.me mudou algo na página e a sincronização foi bloqueada por segurança." |
| Seção Brasil vazia inesperadamente | `section_gap_br` | "Não encontramos a seção de ativos do Brasil — sincronização bloqueada." |
| Seção EUA vazia inesperadamente | `section_gap_us` | "Não encontramos a seção de ativos dos EUA — sincronização bloqueada." |
| Timeout | `timeout` | "O Dividendos.me demorou demais para responder — tente novamente." |
| Captcha/2FA detectado | `captcha_or_2fa` | "Sua conta parece exigir verificação adicional — a sincronização automática não consegue continuar." |
| Dados parciais bloqueados | `partial_data_blocked` | "Os dados encontrados estavam incompletos — nada foi alterado." |

Esses códigos viram parte do contrato de erro da API (`{"detail":
"...", "error_code": "invalid_credentials"}`) para o frontend poder
tratar cada caso com um componente de erro apropriado sem parsear
texto.
