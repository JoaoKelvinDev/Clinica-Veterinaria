# Etapa 1: autenticação e isolamento entre clínicas

Data: 2026-10-30.

## Contexto

O responsável aprovou o plano da Etapa 1, escolheu Supabase Auth com e-mail/senha e determinou custo financeiro zero. Após constatar o limite de dois projetos ativos da organização Free, escolheu Supabase local pelo Docker. Esta decisão complementa a escolha de banco da ADR 0002; o projeto hospedado continua sem ser criado.

## Decisão

- Executar PostgreSQL e Supabase Auth localmente, sem serviços hospedados ou alterações em outros projetos.
- Provisionar clínica e usuários por comando local explícito, sem cadastro público ou convites por e-mail. A interface administra os usuários provisionados: nome, papel, CRMV/UF e situação ativa.
- Adotar os quatro papéis propostos: admin, veterinarian, assistant e reception. Um usuário pertence a uma clínica e tem um papel nesta etapa. Nenhum papel concede acesso a outras clínicas.
- Armazenar apenas nome da clínica e dados mínimos de identificação profissional dos usuários. Senhas e sessões ficam no Auth; o banco da aplicação guarda somente o identificador externo da identidade. E-mail não é duplicado no perfil de negócio.
- Usar SQLAlchemy 2.x, psycopg 3 e migrações Alembic como fonte de verdade do esquema da aplicação. Não manter uma segunda cadeia de migrações SQL do Supabase para as mesmas tabelas.
- Tabelas no schema privado `vetsys`, sem acesso direto pela Data API. Ambas têm UUID, clinic_id, timestamps com fuso e deleted_at. Na raiz Clinic, clinic_id é igual a id, garantido por CHECK.
- Centralizar o filtro de clinic_id e exclusão lógica no TenantRepository. Resolver a identidade autenticada antes do tenant com uma consulta restrita ao auth_id validado no servidor Auth.
- Reforçar o isolamento com RLS obrigatório e conexão runtime vetsys_app, sem privilégios administrativos, sem herança de papéis e sem bypass de RLS. A API recusa conexões administrativas. O contexto é definido na transação e não é reutilizado pelo pool.
- Consultar o papel e a situação ativa no banco em cada requisição; não autorizar por user_metadata, parâmetros ou cabeçalhos de clínica enviados pelo cliente.
- Impedir a remoção do último administrador ativo, com bloqueio da linha da clínica para serializar alterações concorrentes.

## Consequências

O ambiente é de desenvolvimento, com portas publicadas somente em 127.0.0.1. Chaves e senhas locais geradas ficam em arquivos ignorados pelo Git. O frontend recebe apenas URL e chave publicável.

Na combinação da CLI 2.122.0 com Docker Desktop verificada aqui, a opção de bind da rede não limitou as portas como esperado. O script de inicialização aplica bind explícito somente aos containers `supabase_db_vetsys` e `supabase_kong_vetsys`, por meio da API local do Docker. Preserva o volume de dados e os arquivos de configuração, verifica a saúde antes de concluir e não altera o daemon ou o firewall. Containers já restritos não são recriados. Esta adaptação é específica do ambiente local.

Uma segunda migração mantém as mesmas permissões de RLS e avalia os valores de contexto por instrução SQL, conforme a recomendação do diagnóstico de desempenho do Supabase.

O token de acesso expira em 15 minutos; logout limpa a sessão no cliente e revoga a renovação. Tokens já emitidos podem continuar válidos até a expiração, conforme o comportamento do Supabase. Desativar o usuário no banco da aplicação bloqueia imediatamente as próximas requisições da API.

Não há recuperação de senha, cadastro público, convites, múltiplas clínicas por usuário ou edição de e-mail/senha pela interface nesta etapa. Não há dados clínicos, deploy ou serviços pagos. A regra de aprovação clínica exclusiva por veterinário permanece para as etapas clínicas; admin não substitui esse papel.
