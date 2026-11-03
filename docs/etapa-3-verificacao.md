# Verificação da Etapa 3

Data: 2026-11-03. Ambiente: Windows, Docker Desktop, Supabase local. Somente dados fictícios; custo de serviços hospedados: zero.

## Entregas e arquivos

Agenda por veterinário com as situações agendado, confirmado, em atendimento, concluído, cancelado e faltou; bloqueio de conflito de horário; reagendamento; atendimentos vinculados ao agendamento ou avulsos; listagem por dia e veterinário; isolamento entre clínicas. Decisões em `decisions/0005-etapa-3-agenda-e-atendimentos.md`.

Código no commit `87979f4`: módulo `backend/app/modules/scheduling/`, migração Alembic `690ced308c92` (após `f62c813aa353`), `frontend/src/Scheduling.tsx` e `frontend/src/scheduling-api.ts`. Nenhuma dependência nova nesta etapa.

## Verificações executadas

| Verificação | Resultado real |
|---|---|
| pytest local com PostgreSQL isolado `vetsys_test` | 112 passaram; 1 aviso de depreciação já existente |
| Ruff lint e formatação local | passaram |
| mypy local | sem erros em 56 arquivos |
| `npm run check:backend` em container | 112 testes passaram; lint, formatação e mypy passaram |
| Vitest local | 28 passaram |
| ESLint, Prettier, TypeScript e build local | passaram |
| Fluxo real pela API (`.cache/smoke-etapa-3.mjs`) | 26 de 26 verificações passaram |
| Revisão visual em navegador, 1280px e 375px | realizada; sem rolagem horizontal da página |

Os testes automatizados cobrem conflito de horário (inclusive dois pedidos simultâneos pelo mesmo horário), reagendamento com reversão em caso de conflito, cancelamento e falta liberando o horário, dia em `America/Fortaleza` com consulta que atravessa a meia-noite, início e conclusão idempotentes, somente o veterinário responsável operando o atendimento, leitores sem permissão de agendar, atendimento avulso, paciente arquivado preservando histórico e bloqueio de acesso e referências entre clínicas, também no banco.

## Fluxo real com Auth local

Executado pelo proxy em `http://127.0.0.1:5173/api`, com login real no Supabase local de um administrador e de um veterinário fictícios da primeira clínica e de um administrador da segunda. Confirmados:

- criar agendamento e recusar outro em intervalo sobreposto do mesmo veterinário (HTTP 409);
- confirmar; reagendar volta para “agendado” e libera o horário anterior;
- cancelar e marcar falta liberam o horário;
- administrador não inicia atendimento (HTTP 403); o veterinário responsável inicia e conclui; o agendamento passa a “em atendimento” e depois “concluído”; concluído não pode ser cancelado;
- listagem por dia, por veterinário e filtro de outro profissional vazio;
- atendimento listado no dia em que começou, que é o horário real de início;
- a outra clínica recebe 404 no agendamento e no atendimento e não vê a agenda.

A primeira execução teve uma falha no próprio script: ele procurava o atendimento no dia agendado (2030), mas o atendimento começa no horário atual. O script foi corrigido e a execução completa, em outra data, passou. Resultados em `.cache/smoke-etapa-3-resultados.json`.

Ficam na base local, explicitamente fictícios: o usuário “Veterinária fictícia” (CRMV-PI 00000) e agendamentos de verificação nos dias 15/03/2030 e 18/03/2030. Credenciais ficam somente em `.cache/`, ignorada pelo Git.

## Como executar e verificar

Na raiz: `npm run dev`. Acesse `http://localhost:5173`, entre com uma conta provisionada e abra **Agenda**. Para repetir o fluxo real: `node .cache/smoke-etapa-3.mjs AAAA-MM-DD`, com um dia ainda sem agendamentos e as contas em `.cache/acesso-local.json`. Comandos de qualidade no README e na seção 11 do `AGENTS.md`.

## Limitações e diferenças

- A coluna de horário repete a data completa em cada linha. No celular, a tabela rola horizontalmente dentro da própria área, e a situação e as ações ficam à direita.
- O fuso é fixo em `America/Fortaleza` até haver decisão sobre fuso por clínica.
- Sem lembretes, mensagens ou prontuário, conforme o escopo.
- Esta documentação foi escrita depois do commit do código, em 2026-11-03. Junto com ela foi feito um redesenho visual da interface, que não faz parte do escopo da Etapa 3 e deve ir em commit próprio.

Todos os critérios de aceite da Etapa 3 (agendamento sem conflito, mudança de situação, listagem por dia e veterinário) foram verificados. Nenhum commit, push, deploy ou recurso pago foi feito na verificação.
