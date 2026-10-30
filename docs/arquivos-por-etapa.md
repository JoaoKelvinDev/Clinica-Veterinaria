# Arquivos separados por etapa

Data: 2026-10-30. Repositório escolhido: [JoaoKelvinDev/Clinica-Veterinaria](https://github.com/JoaoKelvinDev/Clinica-Veterinaria).

Os commits e o envio ficam com o responsável. Nenhum commit ou push foi executado pelo agente.

## Atenção às versões

Ainda não havia commit inicial quando a Etapa 2 começou. Por isso, a primeira entrega inclui a fundação da Etapa 0 e a Etapa 1. Não há uma cópia independente da Etapa 0 para prometer três commits históricos exatos.

Alguns caminhos aparecem nas duas entregas porque a Etapa 2 os altera. Usar as versões atuais desses arquivos no primeiro commit misturaria as etapas. Foi preservada uma cópia da Etapa 1 antes da reconstrução das imagens Docker; a segunda entrega contém somente arquivos novos ou modificados em relação a essa cópia.

Neste computador, estão preparados os diretórios ignorados pelo Git:

- `.cache/entregas/etapa-1/`: 77 arquivos da fundação e Etapa 1.
- `.cache/entregas/etapa-2/`: 42 arquivos novos ou alterados pela Etapa 2.

Para envio manual, use o **conteúdo** de cada diretório, preservando os caminhos internos. Primeiro envie a Etapa 1; depois adicione/substitua os arquivos da Etapa 2. Não envie a pasta `.cache` nem as pastas de entrega como diretórios dentro do repositório. Os diretórios foram preparados somente nesta máquina; não são uma dependência para executar o projeto clonado.

## Primeiro commit — fundação e Etapa 1

Nome sugerido: `feat: criar fundação e autenticação multi-clínica`.

Arquivos da **versão preservada** da Etapa 1:

```text
.editorconfig
.env.example
.gitignore
AGENTS.md
README.md
backend/.dockerignore
backend/.python-version
backend/Dockerfile
backend/alembic.ini
backend/app/__init__.py
backend/app/bootstrap.py
backend/app/configure_local.py
backend/app/core/__init__.py
backend/app/core/config.py
backend/app/core/db.py
backend/app/core/errors.py
backend/app/main.py
backend/app/modules/__init__.py
backend/app/modules/clinics/__init__.py
backend/app/modules/clinics/api.py
backend/app/modules/clinics/models.py
backend/app/modules/clinics/repositories.py
backend/app/modules/clinics/schemas.py
backend/app/modules/clinics/services.py
backend/app/providers/__init__.py
backend/app/providers/auth.py
backend/migrations/README
backend/migrations/env.py
backend/migrations/script.py.mako
backend/migrations/versions/cbe8339a86dd_create_clinics_users_and_tenant_policies.py
backend/migrations/versions/e303b8c5a9a4_cache_tenant_context_in_row_policies.py
backend/pyproject.toml
backend/tests/__init__.py
backend/tests/conftest.py
backend/tests/test_auth_provider.py
backend/tests/test_clinics_api.py
backend/tests/test_health.py
backend/tests/test_migrations.py
backend/tests/test_services.py
backend/tests/test_tenant_isolation.py
backend/uv.lock
docker-compose.yml
docs/decisions/0001-fundacao.md
docs/decisions/0002-banco-supabase.md
docs/decisions/0003-etapa-1-auth-e-isolamento.md
docs/etapa-0-verificacao.md
docs/etapa-1-verificacao.md
frontend/.dockerignore
frontend/.env.example
frontend/.prettierignore
frontend/.prettierrc.json
frontend/Dockerfile
frontend/eslint.config.js
frontend/index.html
frontend/package-lock.json
frontend/package.json
frontend/src/App.test.tsx
frontend/src/App.tsx
frontend/src/Authentication.test.tsx
frontend/src/HealthStatus.tsx
frontend/src/UserAdministration.tsx
frontend/src/api.ts
frontend/src/auth.ts
frontend/src/main.tsx
frontend/src/styles.css
frontend/src/test/setup.ts
frontend/tsconfig.json
frontend/vite.config.ts
package-lock.json
package.json
scripts/check-backend.mjs
scripts/dev-local.mjs
scripts/restrict-local-ports.mjs
scripts/setup-local.mjs
scripts/start-local.mjs
supabase/.gitignore
supabase/config.toml
```

## Segundo commit — Etapa 2

Nome sugerido: `feat: adicionar cadastros de tutores e pacientes`.

### Arquivos novos (27)

```text
backend/app/core/dependencies.py
backend/app/core/permissions.py
backend/app/core/repositories.py
backend/app/modules/patients/__init__.py
backend/app/modules/patients/api.py
backend/app/modules/patients/models.py
backend/app/modules/patients/repositories.py
backend/app/modules/patients/schemas.py
backend/app/modules/patients/services.py
backend/app/modules/tutors/__init__.py
backend/app/modules/tutors/api.py
backend/app/modules/tutors/models.py
backend/app/modules/tutors/repositories.py
backend/app/modules/tutors/schemas.py
backend/app/modules/tutors/services.py
backend/migrations/versions/f62c813aa353_add_tutors_patients_and_tenant_links.py
backend/tests/test_registry_api.py
backend/tests/test_registry_isolation.py
backend/tests/test_registry_services.py
docs/arquivos-por-etapa.md
docs/decisions/0004-etapa-2-tutores-e-pacientes.md
docs/etapa-2-verificacao.md
frontend/src/PatientTutors.tsx
frontend/src/Patients.tsx
frontend/src/Registry.test.tsx
frontend/src/Tutors.tsx
frontend/src/registry-api.ts
```

### Arquivos existentes alterados (15)

Enviar novamente estes caminhos com as versões da Etapa 2:

```text
AGENTS.md
README.md
backend/Dockerfile
backend/app/main.py
backend/app/modules/clinics/api.py
backend/app/modules/clinics/repositories.py
backend/migrations/env.py
backend/pyproject.toml
backend/tests/conftest.py
backend/tests/test_migrations.py
backend/tests/test_tenant_isolation.py
backend/uv.lock
frontend/src/App.tsx
frontend/src/api.ts
frontend/src/styles.css
```

## Alternativa pelo Git local, sem copiar fontes

Execute os comandos abaixo **você mesmo**, na raiz, se optar por commits locais. O auxiliar da primeira entrega prepara apenas o índice do Git com as versões antigas; não troca os fontes atuais e não faz commit ou push. Ele recusa execução se já existir HEAD ou se o índice tiver arquivos. Se você já criou algum commit, não execute esse auxiliar.

```powershell
backend\.venv\Scripts\python.exe .cache/preparar-commit-etapa-1.py
git diff --cached --stat
git commit -m "feat: criar fundação e autenticação multi-clínica"
```

Depois de revisar/publicar o primeiro commit, prepare a segunda entrega:

```powershell
git status --short
git add -- .
git diff --cached --stat
git commit -m "feat: adicionar cadastros de tutores e pacientes"
```

Antes de `git add -- .`, confira se não há mudanças pessoais ou arquivos novos fora desta relação; adicione-os separadamente se houver. Revise também o diff completo antes de cada commit. A configuração do remoto e o push permanecem com você.

## Não enviar

`.env`, `frontend/.env.local`, senhas, chaves, `.cache/`, `.venv/`, `node_modules/`, `dist/`, caches de ferramentas e arquivos temporários do Supabase. Os arquivos `.env.example` da lista devem ser enviados: são modelos sem credenciais.
