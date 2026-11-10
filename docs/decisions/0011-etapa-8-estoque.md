# Etapa 8: estoque

Data: 2026-11-09.

## Contexto

Após os commits e o push da Etapa 7, o responsável aprovou o plano detalhado da Etapa 8: catálogo, lotes, entradas, saídas FEFO, ajustes imutáveis e alertas. Sem integração automática com orçamentos, vacinas ou prontuário; sem controlados, compras, custos financeiros ou fiscal.

## Decisão

- Criar o módulo `inventory`, nas camadas de API, schemas, services, repositories e models já utilizadas. Não adicionar dependências, provedores, serviços ou worker.
- Usar `Product`, `Lot` e `StockMovement` no schema privado `vetsys`, com UUID, clínica e timestamps. Toda leitura aplica o contexto centralizado do repository; FORCE RLS e referências compostas reforçam o isolamento.
- Produto possui nome, unidade de controle, estoque mínimo, exigência de validade e versão. Unidade e política de validade podem mudar antes da primeira movimentação; depois ficam preservadas, inclusive se o saldo voltar a zero. Nome e mínimo continuam editáveis. Ativar validade exige que todos os lotes existentes tenham data.
- Quantidades e mínimo usam `Decimal`/`numeric(9,3)`, até 999.999,999 por lançamento ou mínimo. Aceitar até três casas decimais; rejeitar floats, valores não finitos e precisão excedente na API. Quantidades trafegam como texto; o navegador valida com `BigInt`, sem arredondamento em ponto flutuante. Cada produto tem uma única unidade, sem conversões.
- Código do lote é normalizado para maiúsculas e único por clínica/produto. Validade é obrigatória quando configurada no produto e opcional nos demais. Lote nasce com saldo zero; entradas posteriores reutilizam o mesmo lote. Código, produto e validade são imutáveis. Não há edição ou remoção de lotes.
- Saldo é a soma dos lançamentos, sem coluna mutável de saldo. Expor físico, disponível e vencido. Validade segue `America/Fortaleza`, incluindo o dia informado. Vencido permanece no saldo físico até descarte por ajuste, mas nunca fica disponível.
- Entrada normal exige quantidade positiva e lote não vencido. Saída normal consome FEFO: validade mais próxima primeiro, lotes sem validade por último, desempate por registro e UUID. Uma saída pode produzir vários lançamentos com o mesmo `operation_id`, todos negativos e na mesma transação.
- Calcular todas as alocações antes de inserir. Saldo insuficiente rejeita a operação inteira. Falha durante a gravação reverte toda a transação. Bloquear o produto com `FOR UPDATE` antes de ler os saldos; exigir `expected_version` e incrementá-la em edição, cadastro de lote, arquivamento e operação de estoque. Pedidos concorrentes com a mesma versão resultam em um sucesso e um conflito 409.
- Ajustes positivos ou negativos exigem motivo e administrador. Permitem contagem de estoque vencido e seu descarte. Quantidade zero e saldo negativo são proibidos. Correção pode apontar para um lançamento anterior do mesmo produto/lote/clínica; acrescenta um ajuste e preserva o original, sem estorno automático.
- Todos os lançamentos guardam motivo, autor identificado, nome do autor, horário, nome do produto e unidade naquele momento. Movimentações não recebem UPDATE/DELETE, nem por conexão administrativa; gatilhos protegem também os lotes e a identidade dos produtos. O runtime recebe somente SELECT/INSERT no histórico. O gatilho de inserção bloqueia o produto, verifica lote/validade e impede saldo negativo no banco.
- Administrador cadastra/edita/arquiva produtos e faz ajustes. Administrador, veterinário e auxiliar cadastram lotes, registram entradas e saídas. Recepção apenas consulta. Estoque não exige aprovação clínica ou CRMV; permanecem as regras gerais do cadastro de usuários.
- Arquivar exige saldo físico zero em todos os lotes, preserva o histórico e impede novas operações. Não há exclusão física ou restauração de produtos pela interface.
- Alertas são derivados na leitura: disponível estritamente abaixo do mínimo; lote com saldo positivo que vence entre hoje e os próximos 30 dias; lote vencido com saldo positivo. Consultar/atualizar a tela recalcula os alertas; não há notificações, jobs ou mensagens de estoque.
- Disponibilizar navegação **Estoque**, busca por nome, filtros ativo/arquivado, paginação de produtos e de movimentações, saldo por lote e correção a partir do histórico. A tela informa conflitos e preserva o formulário quando uma operação falha.
- Migração Alembic `9986a520b54b`, após `9182a5b73863`; API 0.10.0. A reversão de migração só é verificada em banco temporário, sem apagar dados da aplicação.

## Consequências

O histórico explica cada variação do saldo e permite tratar vencidos sem usá-los em saídas normais. O limite se aplica a cada lançamento; o saldo agregado pode ultrapassá-lo por entradas sucessivas. Em uma correção, o operador informa a diferença desejada, não o saldo final.

Não há reserva, múltiplos depósitos, custo médio, compras, classificação regulatória de medicamentos, baixa automática por orçamento/vacina, notificações externas ou operação fiscal. Essas funções exigem planejamento próprio. A listagem de produtos e o histórico têm paginação; os lotes de um produto são carregados juntos para mostrar seus saldos e permitir FEFO.

## Referências técnicas

- [PostgreSQL: números exatos](https://www.postgresql.org/docs/17/datatype-numeric.html).
- [PostgreSQL: bloqueio de linhas](https://www.postgresql.org/docs/17/explicit-locking.html#LOCKING-ROWS).
- [Supabase: Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security).
