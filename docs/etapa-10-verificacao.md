# Verificação da Etapa 10

Data: 2026-11-10, `America/Sao_Paulo`. Windows, Python 3.12, Docker Desktop e Supabase exclusivamente local. Implementação após aprovação do plano. Dados fictícios em todas as verificações. Decisões na [ADR 0013](decisions/0013-etapa-10-financeiro.md).

## Entregas e arquivos

- `backend/app/modules/billing/`: modelos, contratos, persistência, regras e rotas dos lançamentos e estornos manuais.
- `backend/app/main.py`: integração do router e versão 0.12.0.
- `backend/migrations/env.py` e `versions/e4b9de0589fe_add_manual_financial_ledger.py`: tabela imutável, referências por clínica, índices, restrições, RLS, proteção contra alterações e validação de estornos.
- `backend/tests/test_billing.py`, `conftest.py` e `test_migrations.py`: regras, permissões, isolamento, concorrência, snapshot de leitura e reversibilidade.
- `frontend/src/Financial.tsx`, `financial-api.ts` e `Financial.test.tsx`: filtros, totais, cadastro, busca opcional de tutor/paciente, histórico e estorno com motivo, conversão monetária exata e testes.
- `frontend/src/App.tsx`: navegação financeira para administradores e recepção.
- README, AGENTS.md, ADR 0013 e este relatório.

Nenhuma dependência, variável de ambiente ou serviço novo foi adicionado. Não houve mudança nos fluxos de orçamentos, estoque, prontuário ou integrações externas.

## Verificações executadas

| Verificação | Resultado real |
|---|---|
| pytest completo, banco isolado `vetsys_test` | 348 passaram; um aviso existente de depreciação HTTPX/TestClient |
| Ruff lint e formatação | passaram; 130 arquivos |
| mypy | passou; 130 arquivos |
| Vitest | 102 passaram, em doze arquivos |
| ESLint, Prettier e TypeScript | passaram |
| Build frontend | passou; JS de 571,30 kB, com aviso informativo acima de 500 kB |
| Migração upgrade/downgrade/upgrade | passou no pytest em banco temporário; 22 tabelas de negócio com RLS e 55 políticas |
| Inicialização local | migração aplicada e containers da aplicação reconstruídos; API, frontend e worker saudáveis |
| Advisors Supabase local, todos os tipos, nível warn | nenhum problema encontrado |
| Fluxo via proxy frontend com Supabase Auth real local | 19/19 verificações passaram |
| Conferência visual manual no navegador | pendente: a ferramenta de interface retornou inventário vazio de navegadores e aplicativos |

Os 48 casos novos do backend cobrem centavos exatos, limites, valores fracionários/booleanos/textuais inválidos, data futura, motivo obrigatório, filtros, paginação, totais vazios/negativos, categorias, vínculos, nomes históricos, papéis e usuários inativos, isolamento na API/repository/RLS e imutabilidade mesmo por SQL administrativo. Também verificam estorno divergente/duplicado no banco e transporte de somas acima do limite seguro do JavaScript.

O teste de estornos simultâneos sincroniza duas requisições antes da trava transacional: exatamente uma retorna 201 e a outra 409. Outro teste pausa a consulta depois de calcular lista e totais, estorna o lançamento em uma segunda transação e confirma que a primeira consulta ainda mostra situação e totais do mesmo snapshot. A próxima consulta enxerga o estorno.

Os 20 casos novos do frontend cobrem navegação por papel, recepção sem despesas/diferença/estorno, cadastro de recebimento e despesa, vínculos opcionais por busca, valores exatos, rejeição de contratos inválidos, filtros/paginação, ausência de resultados, estorno/cancelamento, preservação do formulário em conflito e falha de leitura. Uma gravação confirmada não perde sua mensagem de sucesso caso apenas a atualização da lista falhe; os totais antigos não são apresentados como atuais.

O fluxo real local verificou recebimento de 12.345 centavos e despesa de 2.500, total de 9.845 com paginação de um item, filtro por forma, bloqueio do veterinário, isolamento de outra clínica, estorno na data original, conflito na repetição, nova correção, estornos simultâneos, preservação dos estornados, rejeição de zero/data futura e ausência de rotas de edição/exclusão. Evidência local ignorada pelo Git: `.cache/smoke-etapa-10-resultados.json`. Nenhuma credencial foi impressa ou adicionada ao repositório.

## Executar e conferir

Na raiz, com Docker Desktop iniciado:

```powershell
npm run dev
```

Abra `http://localhost:5173`, entre como administrador e escolha **Financeiro**. A tela começa no mês atual. Para conferir um lançamento antigo, ajuste **De** e **Até** e aplique os filtros.

1. Registre um recebimento de `123,45` por Pix, com descrição/categoria e data atual ou passada. Tutor e animal são opcionais; se informar ambos, devem estar vinculados no cadastro.
2. Registre uma despesa já paga de `25,00`. Confira os totais vigentes: recebimentos `R$ 123,45`, despesas `R$ 25,00`, diferença `R$ 98,45`, considerando somente esses registros no filtro.
3. Escolha **Estornar** no recebimento, confira os dados e informe o motivo. O original permanece na lista com autoria e motivo; os totais do seu período original passam a excluir esse valor.
4. Para corrigir, registre o novo valor como outro lançamento. Uma devolução efetiva de dinheiro deve ser registrada como despesa; o estorno administrativo não a executa.
5. Entre como recepção: apenas recebimentos e seus totais ficam disponíveis. Veterinários e auxiliares não têm a área financeira nesta etapa.

As verificações automatizadas continuam nos comandos habituais:

```powershell
# Em backend/
uv run --env-file ../.env --frozen pytest --tb=short
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy

# Em frontend/
npm test
npm run lint
npm run format:check
npm run typecheck
npm run build
```

## Limitações e diferenças do plano

- Conferência visual manual pendente no ambiente desta sessão; os fluxos de interface foram exercitados pelo Testing Library.
- Recepção e auxiliar foram validados com autenticação simulada nos testes da API e consultas RLS diretas; o smoke com Auth real usou os administradores e veterinário já existentes, sem provisionar novas contas.
- Busca opcional de cadastros mostra até 20 resultados; refine o nome se necessário.
- Limite individual de R$ 10 bilhões; totais são inteiros decimais como texto no transporte e BigInt na exibição, sem arredondamento monetário.
- Estornos alteram os totais da data original. Não há período fechado, saldo inicial ou abertura/fechamento de caixa.
- Sem contas futuras, parcelas, pagamentos, devoluções automáticas, conciliação, fiscal ou geração financeira automática por orçamento/estoque.
- Os avisos existentes de HTTPX/TestClient e tamanho do bundle permanecem. A CLI informa atualização disponível; as dependências fixadas não foram alteradas.
- Os testes reais acrescentaram registros fictícios ao ambiente local, preservando o histórico. As suítes automatizadas usam banco isolado.

Não houve ampliação funcional do plano aprovado. A navegação manual no navegador permanece como verificação não executada. Não foram realizados commit, push, publicação ou deploy.
