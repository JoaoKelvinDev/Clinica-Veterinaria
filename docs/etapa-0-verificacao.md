# Verificação da Etapa 0

Data: 2026-10-30 (America/Sao_Paulo).

## Resultado executado

| Verificação | Ambiente local Windows | Containers Linux |
|---|---|---|
| pytest | 3 testes passaram | 3 testes passaram |
| Ruff lint | Passou | Passou |
| Ruff formatação | Passou, 3 arquivos | Passou, 3 arquivos |
| mypy estrito | Passou, 3 arquivos | Passou, 3 arquivos |
| Vitest + Testing Library | 5 testes passaram | 5 testes passaram |
| ESLint, sem avisos permitidos | Passou | Passou |
| TypeScript estrito | Passou | Passou |
| Build Vite | Passou | Passou |
| Prettier | Passou | Passou |
| HTTP `/health` direto | 200, `{"status":"ok"}` | 200, `{"status":"ok"}` |
| HTTP `/api/health` pelo Vite | 200, `{"status":"ok"}` | 200, `{"status":"ok"}` |
| Página inicial via HTTP | 200, HTML em UTF-8 com título em português e entrada React | 200, HTML em UTF-8 com título em português |

Também foram executados:

- `docker compose config --quiet`: configuração válida.
- `docker compose up --build --detach --wait --wait-timeout 120`: imagens construídas e serviços iniciados com sucesso.
- `npm install`/`npm ci`: auditoria retornou zero vulnerabilidades conhecidas naquele momento.
- Inicialização do Git local, sem commit ou push.

O Docker Desktop estava parado no início da execução. Foi iniciado para viabilizar a construção e a verificação dos containers. Os servidores temporários usados na verificação sem Docker foram encerrados antes de iniciar os containers, evitando conflito nas portas 8000 e 5173.

## Aviso observado

O pytest passou com um `StarletteDeprecationWarning`: a versão instalada do TestClient mantém compatibilidade com HTTPX, mas recomenda futuramente HTTPX2. O aviso não foi ocultado nem tratado como falha. HTTPX foi mantido conforme o plano aprovado, sem acrescentar outra biblioteca de testes.

## Limitações e diferenças do plano inicial

- PostgreSQL local no Compose foi substituído pela escolha autorizada de Supabase. O projeto remoto continua adiado, por decisão do responsável; nenhuma conexão com banco foi testada.
- Não há ORM, migrações, tabelas, regras de negócio, autenticação ou testes de isolamento. Esses itens dependem das etapas futuras aprovadas.
- A renderização de componentes foi testada com jsdom. A inspeção visual em navegador não foi realizada: a ferramenta de navegador informou que não havia navegador disponível na sessão. Não há captura de tela ou validação visual alegada.
- O ambiente é exclusivamente de desenvolvimento. Não houve deploy, publicação, CI/CD ou avanço para a Etapa 1.
