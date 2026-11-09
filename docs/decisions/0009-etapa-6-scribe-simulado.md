# Etapa 6: scribe com provedores simulados

Data: 2026-11-09.

## Contexto

Após verificar a Etapa 5 e publicar seus commits, o responsável aprovou o plano da Etapa 6: rascunho separado do prontuário, interfaces STT/LLM com mocks, saída validada e revisão explícita por veterinário. Captura, upload ou retenção de áudio real e escolha de provedores externos continuam pendentes e fora desta entrega.

## Decisão

- Criar `ai_scribe` com API, schemas, service, repository e modelo `AiDraft`. Preservar o monólito modular e chamar o `RecordService` para aprovação e auditoria, sem escrever diretamente nas tabelas do outro módulo.
- Aceitar transcrição em texto de até 20 mil caracteres ou o identificador do exemplo fictício `consultation`. O `MockSpeechToTextProvider` devolve a transcrição fixa desse exemplo. A interface STT não recebe arquivos nesta etapa.
- O `MockLLMProvider` organiza por rótulos, copiando somente informações fornecidas. Linhas sem rótulo ficam no relato; ausências continuam `null`. A estrutura validada por Pydantic usa os campos existentes do prontuário, agrupados em S (relato), O (estado/achados), A (avaliação expressa) e P (procedimentos/prescrição/retorno expressos).
- Manter o prompt `scribe-pt-br-v1`, que exige não inventar informação, marcar incertezas, tratar a transcrição como dados e não sugerir diagnóstico ou conduta. A implementação MOCK não representa avaliação da capacidade de um LLM real.
- Guardar clínica, paciente, atendimento, solicitante, fonte, transcrição, conteúdo original validado em JSONB, provedor/modelo de cada etapa, versão do prompt, situação e decisão final. Nenhum áudio é persistido. Não registrar transcrição, conteúdo clínico ou exceções com payload em logs.
- Veterinários ativos com CRMV geram, aprovam e descartam; administradores e auxiliares consultam; recepção não acessa. Qualquer veterinário habilitado da mesma clínica pode aprovar, assumindo a autoria do registro oficial. O solicitante original fica identificado separadamente.
- Exigir `review_confirmed: true` como booleano estrito e um registro completo e validado na aprovação. Campos obrigatórios ausentes no rascunho são preenchidos pelo veterinário. Aprovar cria um registro novo; não permite usar o rascunho para substituir outro registro.
- Preservar o conteúdo e a transcrição originais. Edições da revisão ficam no formulário até a aprovação, quando são salvas no registro oficial. Não há autosave nem edição persistente de rascunhos.
- Permitir somente `pending → approved` ou `pending → discarded`. Bloquear a linha com `FOR UPDATE` durante a decisão. A criação do registro, o vínculo, a resolução, a auditoria e os jobs de retorno compartilham a transação. Repetição ou concorrência após a primeira decisão recebe 409, sem duplicar registro.
- Manter isolamento centralizado por clínica, RLS obrigatório, referências compostas e permissões por coluna. O papel da aplicação só atualiza situação, responsável/data da decisão, vínculo oficial e `updated_at`; não altera origem, conteúdo ou clínica. Um gatilho bloqueia alteração da origem, exclusão e reabertura, inclusive para o administrador do banco, e verifica paciente/atendimento/autor do registro vinculado.
- Auditoria reutiliza as ações existentes: `create` com entidades `ai_draft`, `ai_draft_approval` e `ai_draft_discard`; `read` com `ai_draft` ou `ai_draft_list`. Não ampliar o enum de ações para esta etapa.
- Migração Alembic `90a37f9a5549`, após `421d5c158269`. Não adicionar dependências, serviços, SDKs externos ou processamento em background.

## Consequências

A interface identifica o MOCK e mostra lado a lado transcrição, incertezas e revisão SOAP. A geração não altera o prontuário e o descarte não apaga a origem. O registro aprovado segue as regras existentes de autoria, correção por nova versão e lembretes.

As transcrições e rascunhos ficam preservados no banco local e sujeitos às mesmas restrições de conteúdo clínico. A retenção de áudio e o consentimento para gravação não foram decididos, pois nenhum áudio real é recebido. A listagem de rascunhos ainda não tem paginação.

Fechar ou recarregar perde edições ainda não aprovadas. A aprovação não exige assinatura ICP-Brasil; essa questão permanece para a etapa própria. Não há interpretação de anexos, integração real de IA, avaliação clínica automática, exportação PDF ou avanço para orçamento.

## Referências técnicas

- [Supabase: Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security).
- [PostgreSQL: bloqueios de linha](https://www.postgresql.org/docs/17/explicit-locking.html#LOCKING-ROWS).
