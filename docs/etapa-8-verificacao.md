# Verificação da Etapa 8

Data: 2026-11-09, `America/Sao_Paulo`. Ambiente: Windows, Python 3.12, Docker Desktop e Supabase exclusivamente local. Plano detalhado aprovado antes da implementação. Dados fictícios em todas as verificações. Decisões na [ADR 0011](decisions/0011-etapa-8-estoque.md).

## Entregas e arquivos

- `backend/app/modules/inventory/`: modelos, schemas, repositories, service e API para produtos, lotes, saldos, entradas, saídas FEFO, ajustes, histórico e arquivamento.
- `backend/app/main.py`: registro das rotas de estoque e versão 0.10.0.
- `backend/migrations/env.py` e `versions/9986a520b54b_add_inventory_ledger_and_fefo_guards.py`: três tabelas, referências compostas, índices, RLS, permissões e gatilhos de preservação e saldo não negativo.
- `backend/tests/test_inventory.py` e `test_inventory_services.py`: regras, fluxos, erros, isolamento, papéis, concorrência e atomicidade. `conftest.py` inclui as tabelas na limpeza exclusiva do banco de testes; `test_migrations.py` verifica as novas tabelas e políticas.
- `frontend/src/Inventory.tsx`, `inventory-api.ts`, `Inventory.test.tsx`: produtos, busca, filtros, lotes, entradas, saída FEFO, ajustes/correções e histórico paginado. `App.tsx` adiciona Estoque à navegação; `styles.css` adapta tabelas, detalhes e alertas.
- README, seção 11 e nota da Etapa 8 no AGENTS.md, ADR 0011 e este relatório.

Nenhuma dependência, variável de ambiente, integração externa ou serviço novo.

## Verificações executadas

| Verificação | Resultado real |
|---|---|
| pytest completo, banco isolado `vetsys_test` | 268 passaram; um aviso de depreciação HTTPX/TestClient existente |
| Ruff lint e formatação | passaram; 114 arquivos |
| mypy | passou; 114 arquivos |
| Vitest | 70 passaram, em dez arquivos |
| ESLint, Prettier e TypeScript | passaram |
| Build frontend | passou; JS de 548,06 kB, com aviso informativo acima de 500 kB |
| Migração upgrade/downgrade/upgrade em banco temporário | passou dentro do pytest; 20 tabelas de negócio com RLS e 51 políticas |
| `npm.cmd run dev` | aplicou a migração e iniciou API, frontend e worker existentes |
| Atualização dos containers backend/worker após revisão final | passaram os healthchecks |
| Supabase advisors local, todos os tipos, nível warn | nenhum problema encontrado |
| Fluxo por API e proxy frontend, com Auth real local | 16/16 verificações passaram na execução final |

Os 26 casos novos do backend cobrem FEFO em vários lotes, quantidades fracionadas exatas, entradas repetidas, vencido separado do disponível, validade inclusiva, limite dos alertas de 30 dias, lotes sem validade por último e desempates. Incluem saldo insuficiente sem baixa parcial, falha simulada na segunda alocação com rollback da primeira, duas operações simultâneas com a mesma versão, ajustes positivos/negativos, correção vinculada, snapshot dos nomes, unidade preservada, arquivamento somente com físico zero, papéis, isolamento na API/repository/RLS, referências inválidas e proteção contra UPDATE/DELETE administrativos.

A revisão final incluiu o caso extremo de uma validade em `9999-12-31`, que também deve preceder lote sem validade, e código cujo tamanho aumenta na normalização para maiúsculas. Os testes de permissão distinguem bloqueio por exceção de uma atualização que afeta zero linhas por RLS; ambos preservam os dados.

Os 15 casos novos do frontend cobrem saldos e alertas, payload decimal e versão, entrada em lote, bloqueio de lote vencido, correção vinculada, restrições por papel, conflito preservando formulário, falha de leitura após gravação bem-sucedida, cadastro de produto/lote, consulta de arquivado, busca/paginação, navegação e validação exata de quantidades/respostas.

## Fluxo real local

Executado por `node .cache/smoke-etapa-8.mjs`, usando as contas fictícias já provisionadas e o proxy `http://127.0.0.1:5173/api`. O fluxo criou produto e lotes, registrou entradas de 3,125 e 1,125 mL, recusou uma saída sem saldo e consumiu 2,125 mL por FEFO em dois lançamentos da mesma operação. Verificou autoria e isolamento de outra clínica; recusou mudança de unidade após movimentação; registrou contagem e descarte de lote vencido sem disponibilizá-lo para consumo.

Duas saídas simultâneas de 1 mL com a mesma versão produziram um 201 e um 409, mantendo 1,125 mL. Um ajuste de −0,125 mL apontou para a entrada original sem alterá-la. O produto com saldo não pôde ser arquivado; após a saída final de 1 mL, o arquivamento preservou os nove lançamentos e a busca de arquivados encontrou o produto.

Na primeira execução, uma asserção do script esperava dez lançamentos, mas o fluxo produz nove (a saída dividida conta dois). A expectativa foi corrigida, o fluxo completo foi repetido e passou. As execuções usam nomes distintos e preservaram os produtos fictícios arquivados e seus históricos no banco local.

Resultados da execução final em `.cache/smoke-etapa-8-resultados.json`, ignorado pelo Git. O script depende das contas deste computador e não é versionado; a suíte automatizada é a reprodução portátil. Nenhuma limpeza ou remarcação de revisão foi feita no banco da aplicação.

## Como executar e verificar

Na raiz:

```powershell
npm.cmd run dev
```

Em `http://localhost:5173`, abra **Estoque → Novo produto** com administrador. Cadastre a unidade, mínimo e controle de validade; abra o produto, cadastre dois lotes com validades diferentes e registre entradas. Uma saída menor que o saldo total, mas maior que o lote que vence primeiro, deve consumir os dois lotes e mostrar os dois lançamentos no histórico.

Para verificar vencidos, cadastre um lote com data passada e registre sua contagem por **Ajustar inventário**, como administrador. O físico deve aumentar, mas o disponível deve continuar igual. Use ajuste negativo para registrar o descarte. **Corrigir lançamento** deve acrescentar ajuste, preservando o original; arquivar só deve funcionar com físico zero. Recepção deve conseguir consultar, sem ações de escrita.

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

Nesta rodada, uv usou `--offline` e cache em `.cache/uv`; mypy usou `.cache/mypy-verificacao-etapa-8`. Testes de integração usam banco isolado; o teste de migração cria e remove somente seu banco temporário.

## Limitações e diferenças

- A ferramenta de navegação retornou listas vazias de navegadores/apps. A revisão visual manual permanece pendente; a interface foi verificada por Testing Library, tipos, lint e build.
- Alertas são calculados ao carregar/atualizar a tela; não existem notificações ou atualização em tempo real. Lotes de um produto são carregados juntos; produtos e movimentações são paginados.
- Não há restauração de arquivados, edição de lotes, conversão de unidades, reservas ou integração automática com orçamentos/vacinas. Controlados, compras, múltiplos depósitos, custos financeiros e fiscal permanecem fora do escopo.
- Não foi executada nova auditoria de vulnerabilidades das dependências. Permanecem os avisos informativos de HTTPX/TestClient e tamanho do bundle. A CLI informou nova versão disponível; não foi atualizada.
- Sem diferenças funcionais em relação ao plano aprovado. Nenhum commit, push, deploy, recurso pago ou início de nova etapa foi realizado.
