# Fundação do repositório

Data: 2026-10-30

## Contexto

O responsável autorizou iniciar o desenvolvimento e depois solicitou retomar a Etapa 0, após a apresentação do plano de fundação. O repositório continha somente o AGENTS.md, sem código ou histórico Git.

## Decisão

Implementar a base com Python 3.12, FastAPI, Pydantic v2 e Uvicorn; React, TypeScript estrito e Vite; pytest e HTTPX; Vitest, Testing Library e jsdom; Ruff, mypy, ESLint e Prettier. Usar uv para ambiente Python e lockfile, e npm com package-lock.json para frontend. O uv organiza as dependências e permite usar o Python gerenciado já disponível na máquina.

Aplicar a estrutura mínima compatível com o monólito modular proposto, sem criar antecipadamente módulos de domínio. Usar inglês em identificadores e português do Brasil na interface e documentação.

## Consequências

Não há autenticação, entidades de domínio, services, repositories, integrações ou persistência nesta etapa. Não há motivo para adicionar SQLAlchemy e Alembic antes da primeira etapa com banco. O Compose atende exclusivamente ao desenvolvimento local. CI/CD e deploy continuam fora do escopo.

Os AGENTS.md específicos de backend e frontend dependem de autorização própria e não foram criados. O AGENTS.md raiz continua sendo a referência principal; seus status de decisões serão atualizados pelo responsável, conforme a seção 15.
