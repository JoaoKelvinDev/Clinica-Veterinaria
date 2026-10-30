# Verificação da Etapa 1

Data: 2026-10-30, America/Sao_Paulo.

## Entrega

Supabase Auth e PostgreSQL locais, clínicas e usuários com quatro papéis, conexão runtime restrita, repositories com contexto de clínica, RLS obrigatório, migrações Alembic, login/logout e administração básica da equipe na interface. Provisionamento inicial por comando local explícito.

Nenhum projeto hospedado, recurso pago, convite por e-mail, deploy, commit ou push foi realizado. Os projetos hospedados existentes não foram alterados. As duas clínicas de demonstração e todas as contas usadas na verificação são fictícias.

## Arquivos e responsabilidades

- `backend/app/core/`: configuração, conexão restrita, contexto transacional e erros de domínio.
- `backend/app/modules/clinics/`: modelos, schemas, repositories, services e rotas de clínica/usuários.
- `backend/app/providers/auth.py`: contrato de autenticação e verificação com o servidor Supabase Auth.
- `backend/app/bootstrap.py` e `configure_local.py`: provisionamento e configuração exclusivamente locais.
- `backend/migrations/` e `alembic.ini`: criação do schema privado e políticas RLS, incluindo otimização dos valores de contexto.
- `backend/tests/`: regras de negócio, rotas, erros, isolamento no repository/banco e migrações reversíveis.
- `frontend/src/`: login, sessão, integração HTTP, administração, estilos e testes.
- `supabase/config.toml`: serviços locais necessários e cadastro público bloqueado.
- `scripts/`, `package.json` e lockfile: inicialização, configuração segura de portas e verificações locais.
- Dockerfiles, Compose, exemplos de ambiente, README, seção 11 do AGENTS.md e ADR 0003: execução e documentação.

## Resultados executados

| Verificação | Resultado |
|---|---|
| pytest, Windows e container Linux | 44 testes passaram em cada ambiente |
| Ruff lint e formatação | Passaram |
| mypy estrito, incluindo migrações | Passou, 28 arquivos Python |
| Vitest + Testing Library, Windows e container Linux | 11 testes passaram em cada ambiente |
| ESLint, TypeScript, Prettier e build Vite | Passaram |
| `npm run dev` | Iniciou Supabase local, aplicou migrações e iniciou os aplicativos |
| `/health` e proxy do frontend | HTTP 200 |
| Supabase advisors local, segurança e desempenho | Sem avisos ou erros ao final |
| Bind das portas 54321 e 54322 | Docker e Windows confirmaram escuta em 127.0.0.1 |
| Arquivos locais de configuração e acesso | Ignorados pelo Git |

O pytest mantém um `StarletteDeprecationWarning` sobre HTTPX/TestClient, já observado na Etapa 0. O aviso não foi ocultado e não impede a execução.

## Isolamento e permissões verificados

- Usuário de A não lê nem altera usuário de B, com resposta 404.
- O repository não retorna dados de outra clínica ou cadastros excluídos logicamente.
- Uma consulta proposital sem filtro de clínica continua isolada pelo próprio RLS.
- A conexão runtime não pode transferir um usuário de clínica.
- O contexto não permanece na conexão quando ela volta ao pool.
- A conexão administrativa é recusada para uso runtime.
- Usuários inativos, excluídos ou sem vínculo são bloqueados.
- Cabeçalho de clínica enviado pelo cliente não muda o tenant efetivo.
- Recepção, auxiliar e veterinário não administram usuários ou configurações.
- Mudanças de papel e desativação valem para as próximas requisições sem exigir novo login.
- Veterinário exige CRMV/UF e o último administrador ativo não pode ser removido.
- Upgrade/downgrade/upgrade das duas migrações funciona em banco temporário isolado.

## Verificação com os serviços locais reais

Separadamente dos testes automatizados, foram usados dois administradores fictícios para verificar por HTTP:

1. Login por e-mail/senha no Supabase Auth local.
2. Leitura do perfil e da lista de usuários pelo proxy `/api` da aplicação em container.
3. Bloqueio de leitura e alteração entre duas clínicas.
4. Recusa de cadastro público e ausência de tabela de negócio na Data API pública.
5. Logout com revogação da renovação da sessão.
6. Preservação dos dados e do acesso após restringir as portas dos serviços locais.

As credenciais de demonstração estão somente em `.cache/acesso-local.txt`, ignorado pelo Git; não foram incluídas no código, imagens da aplicação ou documentação.

## Ajustes e limitações

- Foi necessária uma adaptação específica à CLI 2.122.0/Docker Desktop: a rede criada com bind local não restringiu as portas como esperado. O inicializador ajusta apenas os containers deste projeto por meio da API local do Docker, com volumes e configurações preservados. Nenhuma configuração global ou regra de firewall foi alterada.
- Os diagnósticos apontaram inicialmente avaliação repetida do contexto nas políticas. A segunda migração corrigiu isso; o diagnóstico final não apresentou problemas.
- A ferramenta de inspeção retornou nenhuma aplicação ou navegador disponível. Componentes e interações foram testados com jsdom, mas não houve inspeção visual, captura de tela ou teste em navegador real.
- Ambiente exclusivo de desenvolvimento. Não há projeto hospedado, recuperação de senha, convites, cadastro público, alteração de credenciais pela interface ou múltiplas clínicas por usuário.
- Tokens já emitidos podem valer até sua expiração, limitada a 15 minutos; logout impede sua renovação. Desativação no perfil bloqueia as próximas chamadas à API.
- A Etapa 2 não foi iniciada. Não há tutores, animais ou dados clínicos.
