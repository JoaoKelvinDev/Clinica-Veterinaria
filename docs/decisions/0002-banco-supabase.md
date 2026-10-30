# PostgreSQL gerenciado pelo Supabase

Data: 2026-10-30

## Contexto

O plano inicial previa PostgreSQL local no Docker Compose. O responsável escolheu Supabase, autorizando criar a estrutura gradualmente conforme a necessidade. Depois de selecionar a organização jkelvindev, optou por **não criar o projeto agora**, ao receber a confirmação de custo exigida pelo conector.

## Decisão

Usar PostgreSQL do Supabase como banco da aplicação, com criação do projeto remoto adiada. Nesta entrega, não criar projeto, tabelas, credenciais, migrações ou conexões remotas.

## Consequências

O Compose da Etapa 0 contém somente backend e frontend. Esta é uma alteração autorizada em relação à proposta de PostgreSQL local do AGENTS.md. O health check valida apenas a API e não deve ser apresentado como verificação do banco.

Esquemas e migrações serão definidos e versionados nas etapas aprovadas que precisarem de persistência. O uso de Supabase Auth, Storage ou outros serviços não foi decidido por esta escolha de banco. Os requisitos de isolamento entre clínicas permanecem obrigatórios.

Ao retomar a criação do projeto, consultar novamente o custo e respeitar a confirmação exigida pelo conector. O valor anteriormente cotado não é garantia de custo futuro.
