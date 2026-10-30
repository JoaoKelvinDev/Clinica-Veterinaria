# Verificação da Etapa 2

Data: 2026-10-30. Ambiente: Windows, Python 3.12, Docker Desktop, Supabase local. Somente dados fictícios; custo de serviços hospedados: zero.

## Entregas e arquivos

CRUD com arquivamento lógico e busca paginada de tutores e pacientes; telefone E.164; consentimento explícito de WhatsApp; vínculos N:N com responsável principal; telas em português e isolamento entre clínicas. Relação completa dos arquivos em `arquivos-por-etapa.md`.

Os módulos estão em `backend/app/modules/tutors/` e `backend/app/modules/patients/`. Autenticação compartilhada, autorização e filtro de clínica estão em `backend/app/core/`. Migração Alembic: `f62c813aa353`, após `e303b8c5a9a4`. Frontend: `Tutors.tsx`, `Patients.tsx`, `PatientTutors.tsx` e `registry-api.ts`, integrados ao `App.tsx`. Nova dependência: `phonenumbers==9.0.42`, fixada no lockfile, para validar números e formatar E.164.

## Verificações executadas

| Verificação | Resultado real |
|---|---|
| pytest local com PostgreSQL isolado `vetsys_test` | 81 passaram; 1 aviso de depreciação |
| Ruff lint e formatação local | passaram |
| mypy local | sem erros em 47 arquivos |
| Vitest local | 19 passaram |
| ESLint, Prettier, TypeScript e build local | passaram |
| `npm run dev` | reconstruiu imagens e iniciou containers saudáveis; volumes preservados |
| `npm run check:backend` em container | 81 testes passaram; lint, formatação e mypy passaram |
| testes, lint, formatação, tipos e build do frontend em container | 19 testes passaram; demais comandos passaram |
| Supabase advisors local, segurança e desempenho, nível warn | nenhum problema encontrado; saída 0 |
| upgrade/downgrade/upgrade em banco temporário isolado | passou como parte do pytest |

Testes incluem CRUD, erros de validação, acesso por papel, paginação, busca com caracteres literais, unicidade de microchip por clínica, consentimento sem telefone/origem, revogação ao trocar telefone, arquivamento, vínculos e troca de principal. Consultas deliberadamente sem filtro comprovaram RLS nas três tabelas novas; testes também verificaram contexto limpo no pool, bloqueio de exclusão física e alteração de clínica, restrições de escrita por papel e chaves estrangeiras contra vínculos entre clínicas. Os testes anteriores continuam incluídos e passam.

O aviso existente é `StarletteDeprecationWarning`: uso de HTTPX no TestClient. Não foi ocultado nem tratado como falha funcional. Não foi adicionada dependência somente para ocultar o aviso.

## Fluxo real com Auth local

Foi executada verificação HTTP pelo proxy em `http://127.0.0.1:5173/api`, com login real de duas clínicas fictícias no Supabase local. Confirmados:

- login e identificação de clínicas diferentes;
- criação de tutor e paciente, normalização de telefone, data/origem de autorização e vínculo principal;
- busca por nome e microchip;
- HTTP 404 ao consultar tutor, paciente e vínculos de outra clínica, e busca sem resultados da outra clínica;
- troca de principal, arquivamento do tutor preservando vínculo anterior e remoção lógica de vínculo;
- mudança de telefone revogando autorização;
- OpenAPI da API executada com versão `0.3.0`.

Permanece um tutor e um paciente de demonstração, explicitamente fictícios, na primeira clínica local. O tutor temporário foi arquivado. Nenhuma mensagem foi enviada. Credenciais e o script dessa verificação ficam apenas em `.cache/`, ignorada pelo Git; o procedimento reprodutível e os comandos de testes estão no README.

## Como executar e verificar

Na raiz: `npm run dev`. Acesse `http://localhost:5173`, entre com a conta provisionada localmente e abra Tutores ou Animais. Para novos ambientes, siga o provisionamento e os comandos de qualidade descritos no README. Os testes usam Auth simulado, identificado como MOCK, e banco de testes local separado; a verificação de login real acima foi realizada à parte.

## Limitações e diferenças

Não foi feita revisão visual em navegador: não havia superfície de navegador disponível nas ferramentas deste ambiente. A interface foi verificada por testes de interação no DOM, TypeScript e build. Não afirmar validação visual ou de acessibilidade completa.

Não há restauração de cadastros, listagem de pacientes arquivados na interface ou histórico completo de eventos de consentimento. O estado atual e os dados da última concessão/revogação são preservados. A busca de tutores para vínculo oferece até 20 resultados e pede refinar o termo.

Todos os critérios funcionais da Etapa 2 foram verificados; a inspeção visual manual permanece pendente. Foram extraídas para `core` as dependências compartilhadas de autenticação e de repository para reutilização pelos novos módulos; o comportamento da Etapa 1 foi preservado pelos testes de regressão. Sem expansão para agenda, prontuário, mensagens ou financeiro. A parte financeira será planejada depois. Nenhum commit, push, deploy ou recurso pago foi criado.
