# Verificação da Etapa 12

Data: 2026-11-11, `America/Sao_Paulo`. Plano aprovado antes da implementação. Decisões na [ADR 0015](decisions/0015-etapa-12-visao-geral.md).

## Entrega e arquivos

- `backend/app/modules/dashboard/`: schema, service agregador e rota autenticada de leitura consistente da Visão geral.
- `backend/app/main.py`: inclusão da rota e versão `0.13.0` da API.
- `backend/app/modules/scheduling/{repositories,schemas,services}.py`: agendamentos por situação e total de atendimentos em aberto.
- `backend/app/modules/messaging/{repositories,schemas,services}.py`: contagem completa de mensagens ainda aguardando atenção e indicação do provedor simulado.
- `backend/app/modules/inventory/{repositories,schemas,services}.py`: alertas agregados de mínimo e validade, considerando todos os produtos ativos.
- `backend/app/modules/billing/{repositories,services}.py`: reutilização dos totais existentes sem carregar uma página; resumo mensal conforme o papel.
- `backend/tests/test_dashboard.py`: 25 testes novos de regras, API, RLS, erros e concorrência.
- `frontend/src/Dashboard.tsx` e `dashboard-api.ts`: cartões, atalhos, atualização manual, estados de carregamento/erro e validação do contrato conforme o papel.
- `frontend/src/App.tsx` e `styles.css`: nova tela inicial e item do menu; cartões com os estilos compartilhados e grade responsiva.
- `frontend/src/Dashboard.test.tsx`, `test/dashboard-fixture.ts` e `Authentication.test.tsx`: 12 casos novos e adaptação da tela inicial no fluxo de login.
- README, AGENTS.md, ADR 0015 e este relatório.

Nenhuma dependência, migração, tabela, variável de ambiente ou provedor foi adicionada. A consulta não altera registros nem dispara o worker.

## Verificações executadas

| Verificação | Resultado |
|---|---|
| pytest completo, banco local isolado | 373 testes passaram; um aviso de depreciação HTTPX/TestClient já existente |
| Ruff check | passou |
| Ruff format --check | 135 arquivos formatados |
| mypy | passou, 135 arquivos |
| Vitest completo com `--maxWorkers=2` | 128 testes passaram, em 14 arquivos |
| ESLint | passou, sem avisos |
| Prettier | passou |
| TypeScript | passou, também executado no build |
| Build Vite | passou; JS de 585,14 kB, acima do limite informativo de 500 kB |
| Inicialização local | `npm run dev` reconstruiu a aplicação; backend, frontend e worker saudáveis |
| API local com Supabase Auth real | 11/11 verificações passaram pelo proxy do frontend |
| Supabase db advisors local | nenhum problema em nível warn/error |
| Navegador real / screenshots | não executado: inventário da ferramenta retornou `apps: []`, `browsers: []` |

Os testes backend incluem clínica vazia nos quatro papéis, autenticação ausente/inválida e usuário sem acesso, 125 agendamentos distribuídos nas seis situações, atendimentos antigos em aberto, 73 mensagens antes de resolver duas, mais de 20 produtos, limites de validade (ontem/hoje/30/31 dias), lotes zerados e produtos arquivados. O financeiro cobre valores exatos, paginação, outro mês, estornos, recepção e ausência da consulta para veterinário/auxiliar.

O isolamento foi exercitado com outra clínica contendo dados próprios e com contexto de repository divergente do contexto RLS. Leituras repetidas não adicionam movimentações, mensagens, rascunhos ou auditoria clínica. Uma falha simulada do banco retorna erro genérico sem dados parciais. Os limites de calendário incluem a diferença entre UTC e Fortaleza, fevereiro bissexto e a virada do ano. Uma gravação financeira concorrente só aparece na leitura seguinte, comprovando o snapshot consistente.

Os testes de interface cobrem a tela inicial, cartões dos quatro papéis, navegação pelos atalhos, clínica vazia, falha e nova tentativa de atualização, resposta atrasada após troca de sessão, centavos acima do inteiro seguro de JavaScript e rejeição de dados incompatíveis com o perfil. As suítes anteriores continuam passando.

A verificação HTTP usou os acessos fictícios locais já existentes: administradores de duas clínicas e veterinário. Conferiu saúde, autenticação obrigatória, ausência de cache, resumo financeiro omitido para veterinário, fuso/período, concordância com a agenda e com os totais mensais de cada clínica, indicação MOCK e ausência de dados pessoais/conteúdo clínico. Não houve criação de lançamentos ou cadastros nesta conferência. Evidência local ignorada pelo Git: `.cache/smoke-etapa-12-resultados.json`, sem credenciais.

## Executar e conferir

Na raiz, com Docker Desktop iniciado:

```powershell
npm run dev
```

Abra `http://localhost:5173` e entre com um usuário provisionado localmente:

1. Confira **Visão geral** como tela inicial, com dia/atualização em Fortaleza.
2. Confira agenda, pendências de mensagens e alertas de estoque. Atendimentos em aberto incluem dias anteriores.
3. Com administrador, confira recebimentos, despesas e diferença do mês; com recepção, somente recebimentos; com veterinário/auxiliar, ausência do cartão financeiro.
4. Use os atalhos dos cartões e volte pelo menu **Visão geral**. As áreas existentes mantêm suas telas próprias e o botão Voltar nas ações.
5. Após uma alteração em outra área, abra a Visão geral novamente ou use **Atualizar visão geral** para obter os dados atuais.
6. Confira a apresentação em desktop e celular, incluindo os quatro cartões, legibilidade de valores longos e acesso aos botões.

Verificações automatizadas, em `backend/`:

```powershell
uv run --env-file ../.env --frozen pytest --tb=short
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy
```

Em `frontend/`:

```powershell
npm test -- --maxWorkers=2
npm run lint
npm run format:check
npm run typecheck
npm run build
```

## Limitações e pendências

- Inspeção visual em navegador real, desktop e celular, permanece pendente por indisponibilidade do navegador na ferramenta. Os testes jsdom não comprovam a aparência nem o layout responsivo.
- Atualização acontece ao abrir ou solicitar manualmente; não há polling, Realtime ou notificações automáticas nesta etapa.
- Atalhos abrem as áreas existentes, sem aplicar novos filtros. Não foram adicionados relatórios exportáveis, gráficos históricos ou URLs próprias.
- O aviso de tamanho do bundle e o aviso HTTPX/TestClient permanecem visíveis; não foram adicionadas dependências para suprimi-los.
- Nenhum commit, push, deploy ou serviço hospedado foi realizado. Não houve ampliação em relação ao plano aprovado; a pendência visual está explicitamente registrada.
