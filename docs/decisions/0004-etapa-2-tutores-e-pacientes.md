# Etapa 2: tutores e pacientes

Data: 2026-10-30.

## Contexto

O responsável autorizou continuar a etapa dos cadastros após a base de clínicas e autenticação. Solicitou deixar o financeiro empresarial para depois e entregar o projeto ao GitHub por etapas. Os commits e pushes serão feitos pelo responsável, com sugestões de nomes fornecidas pelo agente.

## Decisão

- Implementar somente tutores, pacientes, vínculos N:N e consentimento de WhatsApp, usando o Supabase local gratuito já escolhido. Nenhum serviço hospedado ou envio de mensagem é configurado.
- Manter API, services, repositories e models por módulo. Compartilhar autenticação e filtro de clínica em `core`. Pacientes consultam tutores pelo service desse módulo.
- Administradores e recepção escrevem; veterinários e auxiliares consultam cadastros. Reforçar permissões e isolamento nas políticas RLS, além do backend.
- Coletar apenas nome obrigatório do tutor; telefone, documento e endereço opcionais. Usar `phonenumbers` para validar e normalizar telefone para E.164, com região BR para números nacionais e rejeição de ramais.
- Registrar autorização explícita, data UTC e origem. Concessão exige telefone. Mudança de telefone e arquivamento revogam autorização. Preservar os dados da última concessão e revogação; esta etapa não cria um histórico completo de eventos de consentimento.
- Pacientes exigem nome e espécie. Nascimento e idade estimada em meses são alternativas; data futura é rejeitada. Microchip é normalizado em maiúsculas e único por clínica entre pacientes ativos.
- Primeiro tutor vinculado torna-se principal. Troca de principal é explícita e serializada por bloqueio do paciente, com índice único parcial como garantia adicional. Remover o principal não promove outro automaticamente.
- Preservar cadastros e vínculos por exclusão lógica. Um tutor arquivado continua visível nos vínculos anteriores. Reutilizar o vínculo removido ao associar novamente o mesmo par. Chaves estrangeiras compostas impedem vínculos entre clínicas também no banco.
- Usar paginação e busca literal sem interpretar os caracteres de busca como SQL ou curingas. Desativar access log do Uvicorn para evitar nomes e telefones das buscas nos logs de acesso.
- Manter Alembic como única fonte de migrações da aplicação, conforme ADR 0003.

## Consequências

Não há restauração pela interface, prontuário, agenda, mensagens, faturamento ou emissão fiscal. Cada novo módulo precisará de autorização e plano próprios. A parte financeira fica adiada conforme a orientação mais recente.

Os arquivos de uma etapa podem ser alterados na seguinte. Uma cópia local da Etapa 1 foi preservada antes de substituir as imagens Docker que a continham. A lista de arquivos distingue essa base das alterações da Etapa 2. Nenhum commit, push ou deploy foi executado pelo agente.
