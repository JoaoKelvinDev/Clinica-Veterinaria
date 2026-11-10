# Etapa 9: exportação do prontuário em PDF

Data: 2026-11-10.

## Contexto

Após concluir o estoque, o responsável escolheu a exportação do prontuário e aprovou o plano: PDF gerado localmente, histórico preservado, anexos originais em ZIP opcional, acesso auditado e cópias sem assinatura digital incorporada. Assinatura, conferência do solicitante e entrega permanecem procedimentos manuais da clínica.

Foram consultados os textos oficiais da Resolução CFMV nº 1321/2020, consolidada com a nº 1653/2025. Os arts. 2º, VIII, e 3º tratam de autoria, assinatura, identificação e integridade. O art. 9º contempla o histórico e as cópias dos laudos. Seu §1º estabelece prazo ordinário de cinco dias úteis a partir do protocolo, regras específicas para prorrogação/exames externos, conferência da identidade do solicitante e comprovante de recebimento. Download não equivale a esses procedimentos. A exportação técnica não certifica conformidade jurídica integral do estabelecimento ou dos registros.

## Decisão

- Manter a funcionalidade no módulo `records`, com serviço de exportação, renderer PDF, schemas, repository e rotas próprios. Consultar clínica, paciente, responsáveis e atendimentos pelos services existentes.
- Somente veterinário ativo com CRMV/UF prepara uma nova cópia. Administradores, veterinários e auxiliares listam e baixam cópias existentes. Recepção não tem acesso. Reforçar permissões e isolamento com FORCE RLS e referências compostas no schema privado `vetsys`.
- Criar `record_exports`: paciente, responsável selecionado, autor, nomes e CRMV preservados, horários, chave privada do PDF, tamanho, SHA-256, contagem de documentos com/sem arquivo e manifesto dos anexos. Somente SELECT/INSERT pelo runtime; gatilho recusa UPDATE/DELETE inclusive administrativos. Não existe exclusão ou sobrescrita pela aplicação.
- Cada geração bem-sucedida produz um novo identificador. Guardar o PDF no bucket privado existente, pelo `FileStorage`, com chave exclusiva e sem upsert. Downloads posteriores devolvem os mesmos bytes do PDF. Correções clínicas ou cadastrais posteriores exigem outra emissão para aparecer na cópia.
- Usar uma transação `REPEATABLE READ` exclusivamente na criação, configurada antes da primeira consulta de autenticação. A coleta de cadastros, atendimentos e todas as versões usa o mesmo snapshot; a autenticação e os contextos RLS são compartilhados com o fluxo existente. As demais rotas mantêm o isolamento habitual; o pool restaura o nível após a requisição.
- O formulário de emissão informa endereço, telefone e e-mail profissionais. Identificação de pessoa jurídica é opcional; quando usada, exige razão social, CNPJ e registro no CRMV em conjunto. Nome e CRMV do emitente vêm do usuário autenticado, sem aceitar substituição no payload. Dados do formulário ficam no PDF preservado, sem ampliar o cadastro de clínica/usuários nesta etapa.
- Escolher um responsável atualmente vinculado ao paciente. CPF e endereço precisam estar preenchidos no cadastro; o backend confere o formato básico do CPF, não titularidade ou autenticidade. Aceitar consulta do prontuário de paciente arquivado, mantendo o acesso restrito. Não reconstruir relações de responsabilidade que já foram removidas do cadastro.
- PDF em A4, fonte TrueType incorporada, campos em português, horários em `America/Fortaleza`, numeração de páginas e identificador da exportação. Identificação cadastral reflete a emissão; não inventar dados ausentes ou idade histórica. Autoria dos registros clínicos mantém os nomes/CRMVs gravados na origem.
- Incluir atendimentos e registros vigentes em ordem cronológica, pesos, vacinas, prescrições, documentos externos e seus resumos. Em seção separada, preservar versões substituídas com identificadores e motivos das correções. Todas as versões dos documentos exportados participam do manifesto. Rascunhos de IA não aprovados nunca são consultados pelo serviço de exportação.
- Escapar o texto antes de passá-lo aos parágrafos do renderer. Tags, URLs e comandos do texto clínico não são interpretados. Caracteres sem glifo na fonte são representados por `[U+XXXX]`, com explicação no PDF. Falhas do renderer viram erro de domínio; logs registram somente a classe da exceção, sem traceback ou conteúdo clínico.
- Exibir aviso de ausência de assinatura digital incorporada e espaço para assinatura manual. Exigir ciência explícita antes de preparar a cópia. Nome/CRMV, login e hash não são apresentados como certificado ou assinatura digital do PDF. A preparação da cópia não muda a autoria dos registros originais.
- PDF descreve os anexos, sem abrir, converter ou mesclar seus arquivos. O ZIP opcional contém `prontuario.pdf`, os originais em caminhos únicos por documento e `manifesto.json`, com hashes, contagens e indicação de que download não comprova recebimento. Preservar os bytes dos originais e eventuais assinaturas já existentes neles. O ZIP é remontado a cada solicitação, portanto seus metadados e bytes totais podem variar.
- Documentos sem arquivo original são identificados na interface e no PDF. Não apresentar resumo como cópia de laudo ausente nem afirmar que a cópia contém originais não anexados.
- Conferir hashes e tamanhos dos anexos antes de registrar a emissão e novamente ao montar o ZIP; conferir hash/tamanho do PDF antes de servir. Arquivo ausente/divergente falha explicitamente. Downloads usam attachment, `no-store`, `nosniff` e CSP sandbox; o navegador nunca recebe chaves privadas do Storage.
- Limites operacionais: PDF até 10 MiB, compatível com o bucket existente; PDF mais anexos até 100 MiB, sem truncar o histórico. Excesso é recusado, sem registrar cópia parcial. Não há divisão automática de prontuários grandes nesta etapa.
- Auditar listagem, criação, leitura do PDF, ZIP e anexos, sem conteúdo clínico no log. A auditoria não registra entrega ao tutor.
- Adicionar ReportLab 5.1.0 para geração e pypdf 7.0.1 no grupo de desenvolvimento para inspeção/testes, com versões resolvidas no `uv.lock`. ReportLab traz Pillow e charset-normalizer. Usar Poppler apenas em container temporário para QA visual, sem incorporá-lo ao runtime.
- Migração Alembic `7373a052b884`, após `9986a520b54b`; API 0.11.0. Nenhuma integração externa, recurso hospedado ou custo novo.

## Consequências

Há uma cópia consultável de cada emissão bem-sucedida, mesmo depois de alterações no prontuário. O arquivo é guardado antes da transação de banco terminar: uma falha posterior pode deixar objeto órfão no Storage, mas não uma emissão visível apontando para arquivo inexistente. Não foi criada rotina de limpeza de arquivos clínicos.

Conferência da identidade/autorização do solicitante, protocolo e controle dos prazos, assinatura manual/externa e obtenção do comprovante de recebimento permanecem sob responsabilidade da clínica. Não há integração de certificado, validação de assinatura externa, recibo eletrônico, envio por WhatsApp/e-mail, portal do tutor ou automação de entrega. Essas funções exigem etapas próprias.

O armazenamento local e o hash permitem verificar consistência, sem substituir backup, assinatura digital, certificação ou revisão normativa/profissional. Esta etapa não revisa retrospectivamente a completude clínica dos registros nem transforma um documento externo sem arquivo em laudo original.

## Fontes consultadas

- [CFMV: Resolução nº 1321/2020 consolidada](https://manual.cfmv.gov.br/arquivos/resolucao/1321.pdf), arts. 2º, 3º e 9º.
- [CFMV: Resolução nº 1653/2025](https://manual.cfmv.gov.br/arquivos/resolucao/1653.pdf), art. 3º.
- [ReportLab: Platypus](https://docs.reportlab.com/reportlab/userguide/ch5_platypus/) e [fontes Unicode](https://docs.reportlab.com/reportlab/userguide/ch3_fonts/).
- [PostgreSQL: isolamento de transações](https://www.postgresql.org/docs/17/transaction-iso.html).
- [Supabase: Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security).
