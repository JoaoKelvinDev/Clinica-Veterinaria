# ADR 0013 — Financeiro básico manual

Data: 2026-11-10. Status: aprovado pelo responsável antes da implementação.

## Contexto

A clínica precisa acompanhar valores que já recebeu e despesas que já pagou. O escopo aprovado é um registro financeiro manual, separado dos orçamentos e sem movimentar dinheiro. Caixa completo e emissão fiscal continuam fora do escopo.

## Decisão

- Criar o módulo `billing`, seguindo API → service → repository → model, sem novas dependências, provedores ou serviços.
- Registrar recebimentos e despesas em reais, com descrição, categoria livre, valor positivo em centavos inteiros, data financeira, forma de pagamento, autor e horário de registro. Valores individuais limitados a 1.000.000.000.000 centavos. Datas futuras são recusadas; a referência diária é `America/Fortaleza`.
- Formas aceitas: dinheiro, Pix, cartão de débito, cartão de crédito, transferência bancária e outro. São classificações manuais, sem integração bancária ou de pagamentos.
- Tutor e paciente são opcionais e validados pelos services dos respectivos módulos. Se ambos forem informados, devem estar vinculados. Preservar seus nomes na data do lançamento; renomear ou arquivar cadastros não altera o histórico.
- Usar uma tabela append-only `financial_entries`, com `clinic_id`, UUIDs, referências compostas por clínica e RLS obrigatório. Não expor pela Data API. A conexão da aplicação recebe somente SELECT/INSERT; um trigger também rejeita UPDATE/DELETE administrativos.
- O estorno é uma nova linha vinculada ao original, com motivo, autor e horário próprios. Copia exatamente a natureza, o valor, a data e as classificações do original. A restrição única impede dois estornos; o trigger recusa divergências e estorno de outro estorno. Uma trava transacional por clínica/lançamento serializa tentativas concorrentes sem conceder UPDATE no histórico.
- O estorno corrige os totais na **data financeira original**. Não é tratado como despesa/recebimento de natureza oposta, não infla os totais e não movimenta ou devolve dinheiro. Para uma devolução real, registrar manualmente uma despesa. Para corrigir digitação, estornar e criar outro lançamento.
- Listar originais, incluindo os estornados e seus detalhes de correção, com busca literal na descrição e filtros de período inclusivo, categoria exata sem diferenciar maiúsculas, forma de pagamento, tipo e situação. Paginação de até 100 resultados; a interface usa 20.
- Calcular os totais de todos os resultados filtrados, independentemente da página. Somente lançamentos vigentes contribuem. Ao filtrar apenas estornados, os totais efetivos são zero. Lista, contagem, situação e totais usam a mesma transação com snapshot consistente.
- Transportar cada valor individual como inteiro JSON e os totais como texto de inteiro decimal em centavos, evitando perda de precisão em somas acima do limite seguro do JavaScript. O frontend usa BigInt para conversão e exibição, sem ponto flutuante monetário.

| Papel | Acesso aprovado |
|---|---|
| `admin` | Consultar e registrar recebimentos e despesas, ver totais completos e estornar com motivo |
| `reception` | Consultar e registrar recebimentos; consultar seus estornos; sem despesas, diferença geral ou permissão de estornar |
| `veterinarian`, `assistant` | Sem acesso ao financeiro nesta etapa |

API, service e banco aplicam essas restrições. Para a recepção, os campos de despesas e diferença retornam `null`, sem revelar contagens ou valores de despesas. Orçamentos não geram lançamentos financeiros.

## Consequências e limites

O histórico de autoria faz parte dos próprios registros financeiros. Não há edição, exclusão ou fechamento de período. Um estorno posterior pode alterar o total consultado de um período antigo, preservando sua data real de registro para conferência.

A diferença apresentada não é lucro contábil nem saldo bancário. Não há contas futuras a pagar/receber, parcelamento, cobrança, pagamento online, conciliação, controle de taxas, saldo inicial, abertura/fechamento de caixa, vínculo automático com estoque/orçamentos ou emissão fiscal. São decisões para outras etapas.

Referências técnicas consultadas em 2026-11-10: [RLS do Supabase](https://supabase.com/docs/guides/database/postgres/row-level-security), [travas transacionais do PostgreSQL](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS) e [changelog do Supabase](https://supabase.com/changelog.md). A mudança de CLI v3 não exige atualização da CLI 2.122.0 fixada no projeto. As migrações continuam exclusivamente no Alembic, conforme as decisões anteriores do repositório.
