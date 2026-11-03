# Etapa 4b: documentos e laudos do paciente

Data: 2026-11-03.

## Contexto

O art. 9º, X, da Resolução CFMV nº 1321/2020, na redação da nº 1653/2025, exige no prontuário uma cópia impressa ou digitalizada de cada laudo de exame complementar. O responsável pediu também que o tutor ou a equipe possa registrar documentos de outros veterinários, anexando o arquivo ou escrevendo um resumo. A condição foi custo zero.

## Decisão

- Criar `patient_documents` no módulo `records`. Cada documento tem tipo (laudo de exame, histórico de outro veterinário ou clínica, receita, outro), origem (nome e CRMV opcional), data, atendimento opcional, resumo opcional e arquivo opcional. É obrigatório ter resumo ou arquivo.
- Seguir as regras do prontuário (ADR 0006):
  - somente inclusão, com gatilho que recusa `UPDATE` e `DELETE`;
  - correção por nova versão, com motivo e só pelo autor;
  - auditoria de inclusão, correção, leitura do histórico e abertura do arquivo;
  - RLS: veterinários e auxiliares incluem; administradores, veterinários e auxiliares leem; a recepção não vê o conteúdo.
- Guardar os arquivos no **Supabase Storage local**, num bucket privado `vetsys-documents`, criado pelo `setup-local.mjs`. Gratuito, sem serviço hospedado. O acesso fica atrás da interface `FileStorage`, com `SupabaseFileStorage` e `MemoryFileStorage` (simulada nos testes). O navegador nunca fala com o Storage: o backend usa a chave secreta, que fica só no servidor, e confere permissões antes de servir o arquivo.
- Aceitar PDF, JPG e PNG de até 10 MB. O tipo é identificado pelos primeiros bytes do conteúdo, não pela extensão nem pelo tipo declarado. O nome do arquivo é limpo de caminhos e caracteres de controle.
- Integridade:
  - guardar o SHA-256 e conferi-lo a cada abertura; um arquivo divergente não é servido;
  - cada envio recebe uma chave única (clínica, paciente e documento), enviada com `x-upsert: false`, para nunca sobrescrever;
  - não existe caminho no código para apagar arquivos;
  - uma correção pode manter o arquivo anterior ou anexar outro.
- Servir o arquivo com `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: sandbox` e `Cache-Control: no-store`.
- Desligar o protocolo S3 do Storage local, que não é usado.
- Nova dependência: `python-multipart==0.0.32` (junho de 2026), para receber arquivos no FastAPI. A 0.0.33 tinha 3 dias e não foi adotada. `pip-audit`: sem vulnerabilidades conhecidas.

## Consequências

- O Supabase local sobe um serviço a mais (`storage-api`). A primeira inicialização baixa a imagem.
- O arquivo é gravado antes do registro no banco. Se o registro falhar, sobra um objeto sem referência no Storage, mas nunca um registro apontando para arquivo inexistente.
- O envio aceita até cerca de 11 MB no corpo da requisição; o limite efetivo de 10 MB é conferido no backend e no bucket.
- A leitura ou pesquisa dos documentos com IA fica para depois das etapas do roadmap, conforme pedido do responsável.
