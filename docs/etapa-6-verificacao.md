# Verificação da Etapa 6

Data: 2026-11-09, `America/Sao_Paulo`. Ambiente: Windows, Python 3.12, Docker Desktop e Supabase local. Somente dados fictícios e provedores MOCK. Plano aprovado antes da implementação. Decisões na [ADR 0009](decisions/0009-etapa-6-scribe-simulado.md).

## Entregas e arquivos

- `backend/app/modules/ai_scribe/`: modelo, schemas, repository, service, API e prompt versionado. Geração separada, consulta, aprovação e descarte.
- `backend/app/providers/llm.py`, `speech_to_text.py`: interfaces e mocks explícitos, sem chamadas externas ou áudio real.
- `backend/app/main.py`: injeção de provedores, rotas e API 0.8.0.
- `backend/app/modules/records/services.py`: auditoria de eventos do scribe pelo service do prontuário. A criação oficial reutiliza `add_entry`.
- `backend/migrations/env.py` e `versions/90a37f9a5549_add_simulated_ai_scribe_drafts.py`: tabela, referências, índices, RLS, permissões por coluna e gatilho de preservação/transições.
- `backend/tests/test_ai_scribe*.py`: regras, provedores, API, isolamento, erros, autoria e concorrência; ajustes em `conftest.py` e `test_migrations.py` para incluir a nova tabela.
- `frontend/src/AiScribe.tsx`, `ai-scribe-api.ts`, `AiScribe.test.tsx`: texto ou exemplo fictício, transcrição, revisão SOAP, confirmação explícita e finalização.
- `frontend/src/Records.tsx`, `Records.test.tsx`, `styles.css`: integração ao prontuário, ocultação para recepção e disposição responsiva dos campos.
- README, seção 11 e nota da Etapa 6 no AGENTS.md, ADR 0009 e este relatório.

Nenhuma dependência nova.

## Resultados executados

| Verificação | Resultado real |
|---|---|
| pytest completo com banco isolado `vetsys_test` | 212 passaram; um aviso de depreciação HTTPX/TestClient |
| Ruff lint e formatação | passaram; 95 arquivos |
| mypy | passou; 95 arquivos |
| Vitest | 47 passaram, em oito arquivos |
| ESLint, Prettier e TypeScript | passaram |
| Build frontend | passou; aviso de bundle acima de 500 kB permanece |
| Migração upgrade/downgrade/upgrade em banco temporário | passou dentro do pytest |
| Inicialização `npm.cmd run dev` | imagens construídas; API, frontend e worker locais iniciados |
| Fluxo pela API com Auth real local | 17/17 verificações passaram |
| Supabase advisors, todos os tipos, nível warn | nenhum problema encontrado após criar a tabela local |

Os testes cobrem separação entre rascunho e registro oficial, fontes válidas, metadados, saída inválida sem persistência parcial, logs sem conteúdo, revisão explícita estrita, campos obrigatórios, papéis, isolamento por API e RLS, preservação no banco, transição única, aprovação concorrente e disputa entre aprovação/descarte. A criação oficial mantém autoria/CRMV, auditoria e lembrete de retorno. Casos adicionais verificam aprovação por outro veterinário da clínica e rollback do registro e dos lembretes se o vínculo final falhar.

## Fluxo real e ajuste do estado local

O primeiro fluxo real encontrou erro 503 na geração: `alembic_version` estava em `90a37f9a5549`, mas a tabela `ai_drafts` e sua função ainda não existiam. O problema não ocorreu nos bancos temporários nem no banco isolado dos testes.

Depois de confirmar a ausência dos dois objetos e a revisão exata, foi remarcada somente a revisão local para `421d5c158269` e reaplicada a migração aprovada. As quantidades de pacientes, registros oficiais e documentos antes/depois permaneceram iguais. Isso foi um reparo do estado de desenvolvimento, não uma alteração das migrações anteriores. A causa da marcação sem objetos não foi determinada; não se deve reproduzir esse reparo em um banco que já contenha a tabela.

Após o reparo, `node .cache/smoke-etapa-6.mjs` passou nas 17 verificações: geração com metadados e campos ausentes; ausência de registro automático; revisão obrigatória; administrador impedido de aprovar; outra clínica sem leitura; autoria/CRMV e conteúdo revisado; segunda aprovação recusada; original preservado; STT simulado; descarte sem registro; descarte irreversível; duas aprovações simultâneas com um sucesso e um conflito e somente um registro.

Resultado em `.cache/smoke-etapa-6-resultados.json`, ignorado pelo Git. O script depende das contas fictícias já provisionadas neste computador e não está versionado. Permanecem na base local pacientes e atendimentos fictícios de diagnóstico, além dos rascunhos e dois registros de aprovação do fluxo bem-sucedido. Nenhum dado anterior foi apagado.

## Como executar e verificar

Na raiz, com Docker Desktop disponível:

```powershell
npm.cmd run dev
```

Em `http://localhost:5173`, entre como veterinário com CRMV, abra o prontuário de um paciente com atendimento e selecione **Abrir rascunhos → Novo rascunho MOCK**. Gere com o exemplo fictício ou texto rotulado, confira o original, complete os campos obrigatórios, marque a confirmação da revisão e aprove. O registro deve aparecer no atendimento; um rascunho descartado não deve gerar registro.

Em `backend/`:

```powershell
uv run --env-file ../.env --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy
```

Em `frontend/`:

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run format:check
npm.cmd run typecheck
npm.cmd run build
```

Nesta rodada, uv usou `--offline` e cache em `.cache/uv`; mypy usou `.cache/mypy-verificacao-etapa-6`. Os bancos dos testes continuam separados do banco da aplicação.

## Limitações e diferenças

- A ferramenta de navegação respondeu que não há navegador disponível. Não foi executada revisão visual manual; a interface foi verificada por Testing Library/Vitest, lint, tipos e build. Isso permanece como limitação da verificação.
- O MOCK organiza texto por rótulos e não interpreta uma consulta como um LLM real. Não há gravação, upload de áudio, STT/LLM externos ou análise de anexos.
- As edições da revisão não têm autosave; o rascunho original é preservado. A listagem não tem paginação.
- Permanecem o aviso de depreciação HTTPX/TestClient e o aviso informativo de tamanho do bundle. Não houve nova auditoria de vulnerabilidades de dependências nesta rodada.
- Diferença operacional em relação ao plano: foi necessário reparar a revisão do banco local antes de validar o fluxo real; não houve expansão funcional do escopo.
- Nenhum commit, push, deploy, recurso pago ou avanço para a Etapa 7 foi realizado.
