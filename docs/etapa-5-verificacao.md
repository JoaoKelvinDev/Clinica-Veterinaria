# Verificação da Etapa 5

Data: 2026-11-09, `America/Sao_Paulo`. Ambiente: Windows, Python 3.12, Docker Desktop e Supabase exclusivamente local. Dados fictícios, provedor MOCK e nenhum recurso hospedado criado.

## Entrega e correções aprovadas

A base da etapa está nos commits `f2170d8` (backend) e `3172ba1` (frontend), de 2026-11-03: planejamento de lembretes de consulta, vacina e retorno, worker, registro das mensagens, processamento de respostas curtas e tela **Mensagens**. API 0.7.0. As decisões e limitações estão na [ADR 0008](decisions/0008-etapa-5-lembretes-e-mensagens.md).

Na verificação de 2026-11-09, os 170 testes existentes do backend e os 40 do frontend passaram. Sondagens adicionais reproduziram três defeitos: lembrete atrasado enviado às 21h; erro 503 ao confirmar novamente uma consulta próxima; erro 503 em uma de duas entradas simultâneas com o mesmo identificador. O Ruff também recusou os imports do worker. O responsável aprovou corrigir esses casos e documentar os resultados.

Arquivos criados ou alterados nesta correção:

- `backend/app/modules/messaging/services.py`: confere a janela no despacho e reserva a entrada antes de efeitos de negócio.
- `backend/app/modules/messaging/repositories.py`: inclusão atômica com `ON CONFLICT DO NOTHING`, sem atualizar o conteúdo de uma entrada existente.
- `backend/app/worker.py`: ordenação dos imports, preservando o carregamento dos modelos necessários no processo independente.
- `backend/migrations/versions/421d5c158269_allow_reminder_rescheduling.py`: permite atualizar somente `due_at` dos jobs; downgrade revoga a concessão.
- `backend/tests/test_messaging.py`: sete novos casos de regressão, contando parametrizações.
- `backend/tests/test_migrations.py`: verifica concessão e revogação da permissão de `due_at` e ausência de permissão de alteração de `clinic_id`.
- `README.md`, seção 11 e nota histórica da Etapa 4b no `AGENTS.md`, ADR 0008 e este relatório: funcionamento, comandos, decisões e evidências.

Sem novas dependências e sem alterações na interface.

## Resultados executados após as correções

| Verificação | Resultado real |
|---|---|
| pytest completo, PostgreSQL isolado `vetsys_test` | 177 passaram; um aviso de depreciação HTTPX/TestClient já existente |
| Ruff lint | passou |
| Ruff format --check | 81 arquivos formatados |
| mypy | sem erros em 81 arquivos |
| Vitest | 40 passaram, em sete arquivos de teste |
| ESLint, Prettier, TypeScript | passaram |
| Build do frontend | passou; aviso existente de bundle JS de 507,33 kB, acima do limite informativo de 500 kB |
| Migração em banco temporário | upgrade; revogação no downgrade para `d4a81f6c9e27`; downgrade até base; upgrade novamente; passou dentro do pytest |
| Inicialização com `npm.cmd run dev` | aplicou migração, construiu imagens e iniciou API, frontend e worker locais |
| Supabase advisors local, todos os tipos, nível warn, falha em warn | nenhum problema encontrado |
| Fluxo real pela API, Auth local e worker no Docker | 14 de 14 verificações passaram |

Os novos testes de regressão verificam:

- lembrete vencido não enviado às 20h nem às 21h; continua pendente e não consome tentativa; permanece bloqueado às 7h59 e é enviado às 8h;
- confirmar novamente consulta dentro das duas horas anteriores não retorna 503, mantém o mesmo job e atualiza seu horário;
- duas entradas simultâneas, tanto uma resposta livre como `confirmo`, recebem 201 com o mesmo identificador interno, um único registro e, quando aplicável, uma única resposta e confirmação;
- identificador já ocupado em outra clínica retorna 409 genérico, sem revelar o registro;
- falha simulada antes de enviar a resposta desfaz a entrada e a confirmação da consulta; repetir a entrada depois da recuperação funciona.

Os seis casos iniciais de regressão falharam antes das correções e passaram depois delas. O teste de recuperação após falha foi acrescentado para verificar a atomicidade da nova reserva de entrada.

## Fluxo real com Auth local e worker

Executado por `node .cache/smoke-etapa-5.mjs`, pelo proxy `http://127.0.0.1:5173/api`, com contas locais já provisionadas e dados fictícios novos. O teste aguardou o ciclo automático do worker, sem usar o botão de disparo manual.

Confirmados: vínculo com tutor principal autorizado; agendamento e planejamento da confirmação; envio automático pelo MOCK; texto sem detalhes clínicos e com `SAIR`; resposta livre encaminhada à equipe; veterinário impedido de simular entrada; `CONFIRMO` alterando a agenda; repetição do identificador sem segunda resposta; planejamento do lembrete de proximidade; isolamento da outra clínica; `CANCELAR` alterando a agenda e cancelando jobs; `SAIR` revogando opt-in.

Resultado em `.cache/smoke-etapa-5-resultados.json`, ignorado pelo Git. Esse script depende das contas deste computador, não está versionado e cria dados fictícios a cada execução; para outro ambiente, a reprodução portátil é a suíte automatizada acima. Permanecem na base local o tutor e paciente fictícios, a consulta cancelada e as mensagens de verificação.

## Como executar e repetir

Na raiz:

```powershell
npm.cmd run dev
```

Abra `http://localhost:5173`, entre com uma conta local já provisionada e abra **Mensagens**. Somente administradores e recepção podem simular entradas ou disparar os lembretes vencidos. O aviso de MOCK deve permanecer visível.

Para repetir a suíte e as verificações do backend, em `backend/`:

```powershell
uv run --env-file ../.env --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy
```

Para executar somente os testes da etapa e do processo independente:

```powershell
uv run --env-file ../.env --frozen pytest tests/test_messaging.py tests/test_worker_process.py tests/test_migrations.py
```

No frontend:

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run format:check
npm.cmd run typecheck
npm.cmd run build
```

Os comandos desta rodada usaram `UV_CACHE_DIR` dentro de `.cache/uv` e `uv --offline`; mypy usou `.cache/mypy-verificacao-etapa-5`. Os programas executados são os fixados no lockfile. `npm.cmd` evita a restrição do PowerShell a `npm.ps1`, sem mudar a política do sistema.

## Limites da verificação

- Não foi feita nova revisão visual manual da interface nesta rodada. Os 40 testes do frontend passaram; o código visual não foi alterado.
- As garantias verificadas são as do provedor MOCK. Não há WhatsApp real, webhook público, template aprovado, análise de política/preço de provedor real nem garantia externa de entrega exatamente uma vez.
- O worker não cria lembretes retroativos de registros anteriores à implantação. Regras de envio são fixas e a tela limita as listas de próximos/recentes, sem paginação.
- Não foi executada uma nova auditoria de vulnerabilidades das dependências nesta rodada; o diagnóstico executado foi o advisors do banco local.
- Nenhum commit, push, deploy ou avanço para a Etapa 6 foi realizado.
