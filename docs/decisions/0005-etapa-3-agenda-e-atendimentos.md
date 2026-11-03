# Etapa 3: agenda e atendimentos

Data: 2026-11-03. Registro das escolhas implementadas no commit `87979f4`.

## Contexto

Com tutores e pacientes cadastrados, a Etapa 3 do roadmap pede agendar e acompanhar consultas: `Appointment`, `Encounter`, situações e conflito de horário. Lembretes automáticos e prontuário detalhado ficam fora desta etapa.

## Decisão

- Criar o módulo `scheduling` com API, services, repositories e models, como nos módulos anteriores. Pacientes e veterinários são consultados pelos services desses módulos.
- Situações do agendamento: agendado, confirmado, em atendimento, concluído, cancelado e faltou. Somente agendado e confirmado podem ser alterados. Reagendar volta a situação para agendado, porque o novo horário precisa de outra confirmação.
- Administradores e recepção agendam, reagendam, confirmam, cancelam e marcam falta. Somente o veterinário responsável, ativo, inicia e conclui o atendimento. Auxiliares consultam.
- Impedir conflito de horário do mesmo veterinário no service e, como garantia contra pedidos simultâneos, por uma restrição de exclusão `btree_gist` no banco. Cancelados e faltas liberam o horário e são preservados.
- Iniciar um agendamento cria um `Encounter` vinculado. O veterinário também pode abrir um atendimento avulso, sem agendamento, que começa no horário atual. Iniciar e concluir são idempotentes.
- Gravar datas em UTC. O dia da agenda e a exibição usam `America/Fortaleza`; uma consulta que atravessa a meia-noite aparece nos dois dias que ocupa. Atendimentos são listados pelo dia em que começaram.
- Isolamento por RLS obrigatório nas duas tabelas. Chaves estrangeiras compostas com `clinic_id` impedem referências entre clínicas, e o atendimento não pode trocar paciente ou veterinário do agendamento de origem.
- Sem exclusão física: agendamentos e atendimentos seguem a exclusão lógica dos cadastros. Pacientes arquivados mantêm o histórico.

## Consequências

Não há lembretes, mensagens, prontuário, peso ou vacinas nesta etapa. O `Encounter` é a base em que o prontuário da Etapa 4 será registrado. O fuso fixo `America/Fortaleza` continua até haver decisão sobre fuso por clínica (`AGENTS.md`, seção 7).
