# Verificação da Etapa 4

Data: 2026-11-03. Ambiente: Windows, Docker Desktop, Supabase local. Somente dados fictícios; custo de serviços hospedados: zero.

## Entregas e arquivos

Prontuário por atendimento com os campos do art. 9º da Resolução CFMV nº 1321/2020 (redação da nº 1653/2025), correção por nova versão, pesos, vacinas com os campos do art. 6º, linha do tempo do paciente, auditoria de leitura e escrita e isolamento entre clínicas. Decisões e fontes normativas em `decisions/0006-etapa-4-prontuario.md`.

- Backend: módulo `backend/app/modules/records/` (models, schemas, repositories, services, api) e migração Alembic `b7d41e9a2c55`, após `690ced308c92`. Em `scheduling`: `SchedulingService.for_clinic`, `patient_encounters` e a restrição única `uq_encounter_patient`, usada pelas chaves compostas. Versão da API: 0.5.0.
- Frontend: `Records.tsx`, `records-api.ts`, `Records.test.tsx`. Botão "Prontuário de…" em Animais e nos atendimentos da Agenda.
- Nenhuma dependência nova.

## Verificações executadas

| Verificação | Resultado real |
|---|---|
| pytest local com PostgreSQL isolado `vetsys_test` | 130 passaram; 1 aviso de depreciação já existente |
| Ruff lint e formatação; mypy | passaram; sem erros em 64 arquivos |
| `npm run check:backend` em container | 130 passaram; lint, formatação e mypy passaram |
| Vitest | 31 passaram |
| ESLint, Prettier, TypeScript e build | passaram |
| Migração upgrade/downgrade/upgrade em banco temporário | passou como parte do pytest |
| Fluxo real pela API (`.cache/smoke-etapa-4.mjs`) | 21 de 21 verificações passaram |
| Auditoria no banco local após o fluxo | leituras, inclusões e correção registradas, sem colunas de conteúdo clínico |
| Revisão visual em navegador, 1280px e 375px | realizada; sem rolagem horizontal da página |

Os 18 testes novos do backend cobrem:

- autoria, CRMV e local gravados;
- versão 2 preservando a 1, e recusa de uma segunda correção da mesma versão;
- campos obrigatórios e correção sem motivo;
- correção só pelo autor e no mesmo atendimento;
- somente veterinários registram prontuário e vacinas;
- recepção sem conteúdo clínico, também no banco;
- peso por auxiliar, com correção;
- campos e datas da vacina;
- 404 para outra clínica;
- `UPDATE` e `DELETE` recusados para o papel da aplicação e também para o administrador do banco;
- versão inconsistente recusada pelo gatilho.

## Fluxo real com Auth local

Executado pelo proxy em `http://127.0.0.1:5173/api` com login real. Confirmados:

- a veterinária fictícia abre atendimento avulso e registra a versão 1, com CRMV e local da clínica;
- registro sem diagnóstico presuntivo é recusado (422), e o administrador não registra (403);
- a correção cria a versão 2; uma segunda correção da versão 1 é recusada (409); o histórico mostra as duas versões;
- peso e vacina registrados; vacina sem partida e vacina vencida são recusadas (422);
- o administrador lê o prontuário, e a linha do tempo mostra só a versão vigente;
- a outra clínica recebe 404 no prontuário e no histórico;
- um registro feito após concluir o atendimento é aceito e fica datado.

Resultados em `.cache/smoke-etapa-4-resultados.json`. Ficam na base local, fictícios: um atendimento avulso de 03/11/2026 com registros, um peso e uma vacina de verificação.

## Como executar e verificar

Na raiz: `npm run dev`. A migração nova é aplicada na inicialização. Entre como veterinário, abra **Animais** e escolha "Prontuário de…", ou use o botão nos atendimentos da **Agenda**. Para repetir o fluxo real: `node .cache/smoke-etapa-4.mjs`.

## Limitações e diferenças

- **Fora do escopo, conforme aprovado:** laudos anexados (art. 9º, X), previstos para a Etapa 4b; exportação em PDF e cópia ao responsável; assinatura ICP-Brasil; internação e termos de consentimento.
- **Sem conta de recepção na base local:** o comportamento da recepção foi verificado pelos testes automatizados, não pelo fluxo real.
- **Sem interface para ler a auditoria:** o administrador tem permissão de leitura no banco, mas a tela não foi criada.
- **Linha do tempo sem paginação:** traz todos os atendimentos e registros do paciente.
- **Diferença em relação ao plano:** a auditoria é gravada sem `RETURNING`, porque a RLS só permite ao administrador ler essa tabela.

## Correções de funcionamento (mesmo dia, após revisão do responsável)

Encontradas percorrendo a interface real no navegador, como administrador e como veterinário, e corrigidas:

- **Deadlock no agendamento:** duas reservas simultâneas do mesmo horário podiam terminar em deadlock e responder 503. Agora respondem 409, como conflito de horário. Em 15 execuções seguidas de `test_race_for_same_slot_returns_one_conflict`, o banco registrou 5 deadlocks, e todas as execuções passaram.
- **Inicialização:** `npm run dev` falhava com a mensagem do Docker "ports are not available" quando outro programa ocupava a porta 5173 ou 8000. O script agora verifica as portas antes de subir os containers e explica o que fechar.
- **Tela inicial:** veterinário, auxiliar e recepção caíam numa página que ainda dizia que o atendimento viria "nas próximas etapas". A tela inicial passou a ser a Agenda. Para quem não é administrador, o item "Meu acesso" mostra clínica, nome, papel e CRMV.
- **Equipe e clínica:** salvar um usuário recarregava a tela inteira e apagava a confirmação. Agora a identidade é atualizada sem desmontar a tela, a confirmação aparece e o CRMV é exibido na lista. Renomear a clínica também mostra confirmação.
- **Agenda:** o aviso de conflito continuava na tela depois de "Cancelar edição". A coluna de horário mostra só a hora quando o horário é do dia escolhido.

Vulnerabilidades em 2026-11-03:

- `pip-audit` sobre o `uv.lock` exportado: nenhuma vulnerabilidade conhecida.
- `npm audit` na raiz: nenhuma.
- `npm audit` no frontend: 12 avisos moderados, todos da mesma origem, o `minimatch` 10.2.6 (GHSA-g3hv-75wg-m249, negação de serviço com padrões de glob). Ele é usado só pelo ESLint e pelo typescript-eslint, em desenvolvimento, e não entra no build. A correção (11.0.1 ou mais nova) foi publicada há menos de duas semanas e não foi adotada por cautela com a cadeia de suprimentos. Reavaliar com um `overrides` no `package.json`.

Depois das correções: 130 testes do backend e 32 do frontend passaram; lint, tipos, formatação e build passaram.

Os critérios de aceite da Etapa 4 (edição preserva a versão anterior; leitura e escrita auditadas) foram verificados. Nenhum commit, push, deploy ou recurso pago foi feito.
