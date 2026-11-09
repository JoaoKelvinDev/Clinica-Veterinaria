# Verificação da Etapa 7

Data: 2026-11-09, `America/Sao_Paulo`. Ambiente: Windows, Python 3.12, Docker Desktop e Supabase exclusivamente local. Plano detalhado aprovado antes da implementação. Dados dos testes e do fluxo real são fictícios. Decisões na [ADR 0010](decisions/0010-etapa-7-orcamentos.md).

## Entregas e arquivos

- `backend/app/modules/quotes/`: models, schemas, repositories, service e API. Cálculo exato, rascunho, apresentação manual, decisão, expiração derivada, revisão, busca e paginação.
- `backend/app/main.py`: rotas e versão 0.9.0.
- `backend/migrations/env.py` e `versions/9182a5b73863_add_quotes_and_protected_presentation.py`: tabelas, referências, índices, RLS, permissões, coluna gerada dos itens e proteção de conteúdo apresentado.
- `backend/tests/test_quotes.py`, `test_quotes_isolation.py`, `test_quotes_services.py`: regras, API, cálculos, erros, histórico, papéis, isolamento e concorrência. Ajustes nos fixtures e no teste de migração.
- `frontend/src/Quotes.tsx`, `quotes-api.ts`, `Quotes.test.tsx`: seleção de paciente/tutor/atendimento, itens, prévia exata, edição, apresentação, decisão e revisão; integração em `App.tsx`.
- README, seção 11 e nota da Etapa 7 no AGENTS.md, ADR 0010 e este relatório.

Sem dependências novas, mudanças de infraestrutura ou integração de pagamento/envio.

## Verificações executadas

| Verificação | Resultado real |
|---|---|
| pytest completo, banco isolado `vetsys_test` | 242 passaram; um aviso de depreciação HTTPX/TestClient existente |
| Ruff lint e formatação | passaram; 105 arquivos |
| mypy | passou; 105 arquivos |
| Vitest | 55 passaram, em nove arquivos |
| ESLint, Prettier, TypeScript | passaram |
| Build frontend | passou; bundle JS de 532,49 kB mantém aviso informativo acima de 500 kB |
| Migração upgrade/downgrade/upgrade em banco temporário | passou dentro do pytest; 17 tabelas de negócio com RLS e 44 políticas |
| `npm.cmd run dev` | aplicou migração e iniciou API, frontend e worker locais |
| Supabase advisors local, todos os tipos, nível warn | nenhum problema encontrado |
| Fluxo por API com Auth real local | 17/17 verificações passaram |

Os 30 novos casos do backend incluem quantidades fracionadas, meio centavo para cima, arredondamento por item antes da soma, desconto integral e limites; rejeição de floats, negativos, quantidade inválida, desconto excessivo, total fornecido pelo cliente, tutor sem vínculo, atendimento de outro paciente e validade passada; permissões; snapshot dos nomes; revisão; expiração; isolamento na API e por RLS; preservação contra UPDATE/DELETE administrativos; versões antigas; decisões simultâneas e corrida entre editar e apresentar.

Os oito novos testes do frontend cobrem cadastro com quantidade e preço informados em pt-BR, centavos no payload, apresentação sem envio de mensagens, origem da decisão, orçamento expirado, auxiliar somente consultando, conflito sem mensagem falsa de sucesso, navegação e cálculo exato no navegador.

## Fluxo real

Executado por `node .cache/smoke-etapa-7.mjs`, com contas locais já provisionadas, pelo proxy `http://127.0.0.1:5173/api`. O teste criou paciente, tutor vinculado e atendimento fictícios; cadastrou orçamento com quantidade 1,5 e outro item de meio centavo; confirmou subtotal 1.876 e total 1.776 centavos; recusou total enviado pelo cliente e leitura por outra clínica; apresentou manualmente; recusou edição antiga; renomeou cadastros e verificou os nomes originais preservados; aprovou com origem telefone; recusou edição do aprovado; criou revisão e preservou o original; disputou aprovação/recusa simultâneas; buscou os dois orçamentos e confirmou ausência de mensagens ao tutor.

Antes da atualização, o banco da aplicação estava na revisão `90a37f9a5549`, sem as duas tabelas novas. A migração foi aplicada pelo fluxo normal de inicialização. Nenhuma remarcação de revisão ou limpeza do banco da aplicação foi necessária.

Resultados em `.cache/smoke-etapa-7-resultados.json`, ignorado pelo Git. O script depende das contas deste computador e não é versionado; a suíte automatizada é a reprodução portátil. Permanecem no banco local os cadastros e atendimento fictícios, orçamento aprovado e revisão finalizada pelo fluxo.

## Como executar e verificar

Na raiz:

```powershell
npm.cmd run dev
```

Em `http://localhost:5173`, abra **Orçamentos → Novo orçamento** com administrador, veterinário ou recepção. Busque um paciente com tutor vinculado, informe itens e salve. Depois de conferir a estimativa com o tutor, marque como apresentado e registre a decisão e sua origem. O original não deve oferecer edição; **Criar revisão** deve produzir outro rascunho.

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

Nesta rodada, uv usou `--offline` e cache em `.cache/uv`; mypy usou `.cache/mypy-verificacao-etapa-7`. Dados dos testes ficam no banco isolado, não no banco da aplicação.

## Limitações

- A ferramenta de navegação retornou listas vazias de navegadores/apps. Não foi possível fazer revisão visual manual; a interface foi verificada por Testing Library, tipos, lint e build. A revisão visual permanece pendente.
- Itens manuais, sem catálogo, estoque, pagamento, emissão fiscal, envio automático ou exportação PDF. Aprovação é a decisão do tutor informada e registrada pela equipe.
- O rascunho não mantém um histórico de cada edição. Nomes e conteúdo são congelados na apresentação. Revisões não invalidam automaticamente os orçamentos anteriores.
- Vencimento é derivado na leitura e nos filtros, sem worker e sem gravar `expired` no banco. A decisão depois do vencimento é bloqueada também no servidor.
- Não foi executada nova auditoria de vulnerabilidades de dependências. Permanecem os avisos informativos de HTTPX/TestClient e de tamanho do bundle.
- Sem diferenças funcionais em relação ao plano aprovado. Nenhum commit, push, deploy, recurso pago ou avanço para a Etapa 8 foi realizado.
