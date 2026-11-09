# Etapa 5: lembretes e mensagens com provedor simulado

Data: 2026-11-09.

## Contexto

Os commits `f2170d8` e `3172ba1`, de 2026-11-03, acrescentaram o backend e a interface da Etapa 5. Em 2026-11-09, o responsável solicitou a verificação e aprovou corrigir as falhas reproduzidas, adicionar regressões automatizadas e atualizar a documentação. Este registro descreve o comportamento existente e as correções aprovadas, sem aprovar provedores reais.

## Decisão

- Manter `MessagingProvider` e `MockMessagingProvider`: não há conexão real com WhatsApp, recurso hospedado ou custo financeiro. A API de entrada é uma simulação autenticada, não um webhook público.
- Usar `reminder_jobs` e `messages`, com filtro centralizado de clínica, RLS obrigatório e referências compostas entre registros da mesma clínica. O planejamento é chamado pelos services de agenda e prontuário, na transação da alteração de origem.
- Manter as regras fixas já implementadas: confirmação de consulta 24h antes; lembrete de consulta confirmada 2h antes; vacina 7 dias antes; retorno 2 dias antes. Vacina e retorno usam 9h. O fuso é `America/Fortaleza`.
- Aplicar a janela de lembretes também no despacho: a partir de 8h e antes de 20h. Fora dela, o lembrete permanece pendente, sem consumir tentativa. Na próxima janela, o worker reavalia situação, data do evento, paciente e consentimento antes de enviar. As respostas automáticas a entradas simuladas são imediatas; esta janela controla os lembretes programados.
- Enviar somente ao tutor principal ativo, com telefone e opt-in atuais. Reagendar, cancelar ou iniciar uma consulta cancela lembretes pendentes; confirmar planeja o lembrete de proximidade. Corrigir vacina ou retorno cancela o lembrete da versão anterior.
- Executar um ciclo do worker a cada 60 segundos, em transações separadas por clínica, usando conexão restrita. A função privada `clinics_with_due_reminders` enumera somente identificadores e não concede execução a `PUBLIC`. A seleção com `FOR UPDATE SKIP LOCKED` evita que dois workers reservem simultaneamente o mesmo job.
- Administradores e recepção simulam entradas, disparam lembretes vencidos e resolvem pendências; usuários ativos dos demais papéis consultam. Respostas curtas confirmam/cancelam consultas; `SAIR` revoga opt-in dos tutores com o telefone na clínica. Entradas não reconhecidas ou sem vínculo identificável seguem para atenção humana, sem orientação clínica.
- Reservar cada entrada com `INSERT ... ON CONFLICT DO NOTHING`, pela restrição de unicidade de provedor/identificador, antes dos efeitos de negócio. A entrada, o efeito e o registro da resposta compartilham a transação. Uma entrega concorrente aguarda e retorna o registro existente. A releitura continua limitada à clínica; identificador ocupado em outra clínica recebe conflito genérico, sem expor o registro.
- Adicionar a migração Alembic `421d5c158269`, após `d4a81f6c9e27`, concedendo apenas `UPDATE (due_at)` em `reminder_jobs` a `vetsys_app`. O downgrade revoga apenas essa concessão. Não alterar a migração anterior nem ampliar permissões sobre identidade, clínica, origem ou conteúdo.
- Não adicionar dependências.

## Consequências

O modo MOCK fica explícito na interface e nos logs. As regras não são configuráveis pela interface e não há tabela de regras ou de conversas separada: jobs e mensagens atendem ao escopo atual. Consultas e registros anteriores à implantação não são reprocessados para criar lembretes retroativos.

Os textos automáticos evitam detalhes clínicos e incluem a saída dos lembretes; mensagens recebidas ficam registradas. A confirmação/cancelamento se associa à consulta futura válida encontrada nas últimas mensagens enviadas ao telefone, sem seleção interativa em caso de múltiplas consultas.

A restrição única protege as entradas no banco. Não há garantia de envio externo exatamente uma vez após falha entre envio e commit: isso depende de idempotência no futuro provedor real. Janela de atendimento, templates, autenticação de webhook e políticas oficiais do WhatsApp precisam de análise atual e aprovação na etapa de integração real.

Sem provedor real, campanhas, agente conversacional ou avanço para a Etapa 6. Resultados executados e limites da verificação estão em `../etapa-5-verificacao.md`.

## Referências técnicas

- [SQLAlchemy: INSERT ON CONFLICT](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert).
- [PostgreSQL: INSERT, conflitos e RETURNING](https://www.postgresql.org/docs/17/sql-insert.html).
