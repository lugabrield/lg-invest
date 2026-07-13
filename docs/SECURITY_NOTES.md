# Notas de Segurança — LG INVEST v1.1

> Regras que valem para toda a API nova (`backend/app/api/`) e para o
> frontend Next.js. Para o fluxo específico de credenciais do
> Dividendos.me, ver `docs/DIVIDENDOS_ME_FRONT_SYNC.md` (este documento
> cobre as regras gerais que esse fluxo tem que respeitar).

## Regra de ouro

Nenhum segredo (senha, `DATABASE_URL`, chave de API) chega ao
navegador do usuário, aparece em log, é persistido em banco fora do
necessário, ou é ecoado numa mensagem de erro. Isso já era verdade na
v1.0.0 (`backend/app/integrations/dividendos_me/secrets.py` já segue
essa regra) — a v1.1 estende a mesma regra para credenciais que agora
também podem vir de uma requisição HTTP, não só de `.env`.

## Credenciais do Dividendos.me

1. **Nunca persistidas.** Nem em `ExternalSyncRun`, nem em nenhuma
   outra tabela, nem em arquivo, nem em cache em disco.
2. **Nunca logadas.** Nenhum `print`/`logger` recebe o valor de
   `password` ou `email` completo — email pode ser mascarado
   parcialmente em log (`lu***@outlook.com`) se precisar aparecer para
   diagnóstico; senha nunca aparece, nem mascarada.
3. **Nunca retornadas na resposta.** A API recebe email/senha no body
   da requisição e nunca os inclui na resposta (nem em erro, nem em
   sucesso).
4. **Vivem só em memória, pelo tempo da requisição.** O
   `DividendosMeClient(email, password)` já é construído assim hoje
   (recebe as credenciais no `__init__`, não busca sozinho de env/
   secrets) — a API só precisa não guardar essas variáveis em nenhum
   lugar além do escopo da função que processa a requisição.
5. **Cada etapa reenvia as credenciais.** Login de teste, dry-run,
   update e replace são chamadas HTTP independentes, cada uma com
   email/senha no body — não existe um "token de sessão Dividendos.me"
   guardado entre chamadas (nem em Redis, nem em cache do FastAPI). É
   mais simples e mais seguro do que tentar manter estado; o custo é o
   usuário digitar a senha de novo se repetir uma etapa, o que é
   aceitável para uma ação pouco frequente.
6. **Sanitização de erro.** Toda exceção capturada no fluxo do
   Dividendos.me passa por `sanitize_message()` (já existe em
   `secrets.py`) antes de virar resposta HTTP — proteção extra caso o
   Playwright ou alguma lib de terceiro ecoe a senha por engano (ex.:
   numa URL com querystring de erro).
7. **HTTPS obrigatório em produção.** Sem TLS, credenciais em trânsito
   ficam expostas independente de qualquer cuidado no código — a Vercel
   já força HTTPS por padrão; o backend (Render/Fly/Railway) precisa
   disso configurado também (os três oferecem TLS gerenciado).

## CORS

A API só aceita requisições do domínio da Vercel (produção) e
`localhost` (dev). Nunca `allow_origins=["*"]` com `allow_credentials=True`
— isso permitiria qualquer site na internet chamar a API em nome do
usuário se ele estiver com o app aberto. Lista de origens permitidas
vem de variável de ambiente (`CORS_ALLOWED_ORIGINS`), não hardcoded, para
poder trocar o domínio sem redeploy de código.

## Rate limiting

Endpoints do Dividendos.me (login/dry-run/sync) e de recomendação
(`/api/recommendations/aporte`, que pode ficar pesado) recebem um rate
limit básico por IP (ex.: 10 requisições/minuto) — evita abuso
acidental (um double-click no botão) e uso malicioso se a API ficar
exposta sem autenticação (ver seção "Sem autenticação na v1.1" abaixo).
Implementação sugerida: `slowapi` (wrapper de `limits` para FastAPI) —
biblioteca pequena, sem infraestrutura extra necessária para o volume
esperado (uso pessoal).

## Sem autenticação na v1.1 — o que isso implica

A v1.1 continua single-user, sem login. Isso significa que **a
segurança da API depende inteiramente de ela não ser publicamente
descoberta/exposta**:

- CORS restrito ao domínio da Vercel reduz o risco de uso via
  navegador de terceiros, mas **não impede** uma chamada direta à API
  (curl, Postman) por quem descobrir a URL — CORS protege browsers, não
  é autenticação.
- Mitigação mínima recomendada para v1.1: a URL da API não deve ser
  divulgada, e o provedor de deploy (Render/Fly/Railway) deve ter os
  logs de acesso monitoráveis para notar uso anômalo.
- Autenticação de verdade (ex.: um token fixo em header via variável de
  ambiente do lado do frontend, ou Supabase Auth completo) fica para
  v1.2, conforme decisão explícita do usuário de não atrasar a v1.1 por
  isso. **Documentar isso claramente no README da v1.1** para não virar
  uma falsa sensação de segurança.

## Variáveis de ambiente — onde cada uma vive

Ver tabela completa em `docs/WEB_APP_ARCHITECTURE.md`, seção "Variáveis
de ambiente e segredos". Resumo da regra: só variáveis prefixadas
`NEXT_PUBLIC_` no Vercel são enviadas ao navegador — qualquer coisa
sensível (`DATABASE_URL`, futuras chaves de API de dados de mercado)
fica exclusivamente no backend.

## Logs

- Nunca logar o body completo de requisições que contenham `password`.
- Nunca logar `DATABASE_URL` completa (ela contém a senha do banco).
- Erros 500 devolvem mensagem genérica ao cliente; o detalhe técnico
  vai para o log do servidor (nunca para a resposta HTTP) — mesma regra
  já usada no Streamlit (`except Exception: # noqa: BLE001 - nunca
  vazar detalhe de exceção não prevista`).

## Testes de segurança a criar (Fase 6/7)

- Teste que confirma que uma senha enviada para `/api/dividendos-me/*`
  nunca aparece na resposta (sucesso ou erro).
- Teste que confirma que `sanitize_message()` remove a senha de uma
  mensagem de exceção simulada.
- Teste que confirma que `ExternalSyncRun` (ou qualquer tabela) nunca
  recebe uma coluna com a senha, mesmo indiretamente.
- Teste de CORS: requisição de uma origem fora da allowlist é rejeitada.
