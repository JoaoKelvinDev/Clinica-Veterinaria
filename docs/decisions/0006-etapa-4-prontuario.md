# Etapa 4: prontuário

Data: 2026-11-03.

## Contexto

A Etapa 4 cria o registro clínico versionado e auditável. O `AGENTS.md` (seção 2.2) exige confirmar os campos no texto oficial do CFMV antes de modelar. Foram lidas a Resolução CFMV nº 1321/2020 e a Resolução nº 1653/2025, que alterou o art. 9º e foi publicada no DOU em 02/07/2025, entrando em vigor na mesma data. A Resolução nº 1671/2025 revoga outras 63 normas, mas nenhuma das duas.

Exigências usadas no modelo:

- Art. 2º, VIII: o prontuário é documento escrito e datado, sem rasuras ou emendas, assinado pelo médico-veterinário, com garantia de autenticidade e integridade.
- Art. 3º, §2º: documentos eletrônicos exigem segurança, autenticidade, confidencialidade e integridade.
- Art. 9º, para cada atendimento: I data, horário e local; II veterinário atendente; III relatos do responsável; IV estado geral e parâmetros; V achados; VI diagnóstico presuntivo; VII diagnóstico conclusivo, quando houver; VIII procedimentos, com data, hora e profissionais identificados (nome e CRMV); IX imunizações; X cópia de cada laudo de exame complementar.
- Art. 9º, §3º: guarda mínima de 5 anos após o último atendimento, mesmo em caso de óbito.
- Art. 6º, carteira de vacinação: nome, partida, fabricante, dose, fabricação, validade e revacinação prevista.

## Decisão

- Criar o módulo `records`, com `record_entries`, `weight_records`, `vaccine_records` e `audit_logs`.
- Cada registro clínico pertence a um atendimento (`Encounter`) e grava data e hora, local (a clínica, por padrão), autor, nome e CRMV no momento do registro. Relato do responsável, estado geral e diagnóstico presuntivo são obrigatórios. Achados, diagnóstico conclusivo, procedimentos, prescrição e retorno são opcionais.
- Corrigir cria uma nova versão (`supersedes_id`, `root_id`, `version`) com motivo obrigatório. A anterior é preservada e consultável. Somente o autor corrige o próprio registro, sempre a versão mais recente e no mesmo atendimento. Registros posteriores à conclusão do atendimento são aceitos e ficam datados, servindo de evolução.
- Somente inclusão, garantida no banco: o papel da aplicação tem só `SELECT` e `INSERT` nas quatro tabelas, e um gatilho rejeita `UPDATE` e `DELETE` inclusive para papéis administrativos. Outro gatilho valida a sequência de versões. Restrições únicas impedem duas correções da mesma versão, e chaves compostas mantêm paciente, atendimento e clínica coerentes.
- Permissões, também reforçadas por RLS: veterinários registram e corrigem; auxiliares registram peso; administradores, veterinários e auxiliares leem; a recepção vê somente as datas dos atendimentos, sem conteúdo clínico. Somente administradores leem a auditoria.
- `AuditLog` registra leitura do prontuário, leitura do histórico de versões, inclusão e correção, com autor, ação, entidade e paciente. Não guarda conteúdo clínico.
- Vacinas exigem todos os campos do art. 6º. O lote passa a ser obrigatório, corrigindo a seção 7 do `AGENTS.md`. Uma vacina vencida na data de aplicação, ou com revacinação até essa data, é recusada. Somente veterinários registram vacinas.
- Peso em gramas inteiros, entre 1 g e 5.000 kg.
- CPF e endereço do responsável (art. 3º, VII) continuam opcionais no cadastro. A tela do prontuário avisa quando faltam no responsável principal. A exigência fica para a emissão de documentos.

## Consequências

- O art. 9º, X (cópia dos laudos) depende de anexar arquivos. Fica para a etapa curta seguinte, **4b: anexos de laudos**, aprovada em 2026-11-03. A pesquisa com IA sobre os anexos fica para depois das etapas do roadmap.
- A autoria vem do login, com nome e CRMV gravados em cada registro. Isso funciona como assinatura eletrônica simples. A suficiência jurídica não foi avaliada; a assinatura com certificado ICP-Brasil fica pendente para a exportação em PDF.
- Exportação e cópia ao responsável (art. 9º, §1º), extravio (art. 9º, §2º), internação e termos de consentimento (art. 10 e 11) ficam fora desta etapa.
- Não há exclusão física: pacientes arquivados mantêm o prontuário, o que atende à guarda mínima de 5 anos.
