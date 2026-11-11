# AGENTS.md

> Documento de referência principal para agentes de código (Codex) que trabalham neste repositório.
> Idioma deste documento: português do Brasil. Leia-o por inteiro antes de qualquer ação.

---

## 0. Como usar este arquivo

### 0.1 Regras de leitura

1. Leia este arquivo integralmente antes de analisar ou alterar qualquer coisa.
2. Leia também qualquer `AGENTS.md` presente nos subdiretórios que você for tocar. Instruções mais específicas (mais próximas dos arquivos) têm prioridade sobre as gerais, desde que não contradigam a seção 3 (Princípios inegociáveis).
3. Se este arquivo estiver ausente, incompleto, contraditório ou descrever outro projeto, **informe o problema antes de implementar**.
4. **Não presuma requisitos que não estejam documentados aqui.** Quando algo estiver marcado como `PENDENTE` ou `PROPOSTA`, trate como decisão em aberto: pergunte ou proponha, nunca decida sozinho.

### 0.2 Legenda de status das decisões

| Marca | Significado |
|---|---|
| `DECIDIDO` | Definido pelo responsável do projeto. Siga. |
| `PROPOSTA` | Sugestão fundamentada, ainda não aprovada. Valide na etapa de planejamento. |
| `PENDENTE` | Sem definição. Pergunte antes de implementar qualquer coisa que dependa disso. |

### 0.3 Quem decide

O responsável pelo projeto (o desenvolvedor humano que conversa com você) aprova cada etapa. Você analisa, propõe e implementa **somente** o que foi aprovado.

---

## 1. Visão do produto

### 1.1 Nome

`PENDENTE`. Nome provisório nos textos: **Sistema Veterinário**. Não use nomes de marca em código ou pacotes até que o nome seja definido; use identificadores neutros (`vetsys` é aceitável como slug técnico provisório).

### 1.2 Problema

Clínicas veterinárias pequenas e médias enfrentam, no dia a dia:

- Tempo excessivo gasto com documentação e prontuário, muitas vezes ainda em ficha de papel.
- Comunicação desorganizada com tutores (telefone e WhatsApp pessoal), sem lembretes sistemáticos de vacina, retorno e consulta, o que gera faltas e perda de retorno.
- Dificuldade de comunicar custos ao tutor antes do procedimento, o que gera conflito e abandono de tratamento.
- Controle fraco de estoque de medicamentos e insumos (perdas por vencimento) e de caixa.
- Sistemas existentes que não conversam entre si.

### 1.3 Público-alvo

`DECIDIDO` como foco inicial: clínicas veterinárias pequenas no Brasil, começando por clientes locais do Piauí. O usuário final são médicos-veterinários, técnicos/auxiliares e recepção. O tutor (dono do animal) é usuário **indireto**: interage por WhatsApp, não faz login no sistema na fase inicial.

### 1.4 Proposta de valor

Um sistema de gestão de clínica veterinária (tipo PIMS) com IA embutida, cujo diferencial é fazer bem duas coisas em português do Brasil:

1. Reduzir o tempo de documentação (prontuário assistido por IA, com revisão obrigatória do veterinário).
2. Automatizar a comunicação com tutores via WhatsApp (lembretes, confirmações, retornos).

O restante (orçamento, estoque, fiscal) existe, mas deve ser simples e correto, não exaustivo. Concorrentes completos já existem; **não tente competir em amplitude**.

### 1.5 Módulos

`DECIDIDO`: os quatro grupos de funcionalidade fazem parte de um único produto integrado.

| Módulo | Resumo |
|---|---|
| Núcleo | Clínica, usuários, tutores, animais, atendimentos, agenda |
| Prontuário com IA | Registro clínico e rascunho gerado por IA a partir da consulta |
| Comunicação (WhatsApp) | Lembretes, confirmações, retornos, atendimento básico |
| Orçamento | Estimativa de custo apresentada ao tutor |
| Estoque e fiscal | Controle de lotes e validade, base para caixa e notas |

A **ordem de construção** está em `PROPOSTA` (seção 12) e deve ser confirmada pelo responsável.

---

## 2. Contexto de domínio

### 2.1 Glossário

| Termo | Significado |
|---|---|
| Tutor | Pessoa responsável pelo animal (cliente da clínica) |
| Animal / Paciente | Animal atendido. No código: `Patient` |
| Atendimento | Evento clínico de um paciente (consulta, retorno, cirurgia, vacinação). No código: `Encounter` |
| Prontuário | Histórico clínico completo e documento de valor legal do paciente |
| SOAP | Formato de nota clínica: Subjetivo, Objetivo, Avaliação, Plano |
| CRMV | Conselho Regional de Medicina Veterinária (registro do profissional, por estado) |
| CFMV | Conselho Federal de Medicina Veterinária (edita as normas) |
| Orçamento | Estimativa de custo de procedimentos e produtos |
| Lote | Conjunto de um produto com mesma validade, usado no controle de estoque |
| FEFO | First Expired, First Out: consome primeiro o que vence antes |
| NFS-e / NFC-e | Nota fiscal de serviço eletrônica / de consumidor eletrônica |
| Opt-in | Consentimento do tutor para receber mensagens |

### 2.2 Prontuário tem valor legal

O prontuário é considerado o principal documento da clínica veterinária e pode ser usado em perícias e processos. Consequências obrigatórias para o código:

- **Nunca apagar fisicamente** registros de prontuário. Use correção por nova versão, com autor, data e hora.
- Todo registro clínico precisa ter **autoria identificável** (usuário e, quando aplicável, CRMV).
- O tutor pode solicitar cópia do prontuário. O sistema deve conseguir **exportar** o prontuário de um paciente em formato legível (PDF e/ou impressão). Pesquisa preliminar indica norma do CFMV com prazo de entrega de até 5 dias úteis, mas **os campos obrigatórios e prazos exatos devem ser confirmados no texto oficial vigente das resoluções do CFMV antes de modelar o prontuário** (etapa de planejamento). Não invente campos obrigatórios de memória.

### 2.3 Privacidade (LGPD)

Dados de tutores (nome, telefone, endereço, CPF se houver) são dados pessoais. Aplique minimização: colete apenas o necessário e registre consentimento de comunicação por WhatsApp.

---

## 3. Princípios inegociáveis

1. **Humano no controle clínico.** A IA gera **rascunhos**. Nenhum texto gerado por IA vira registro oficial sem revisão e aprovação explícita de um veterinário. A IA não diagnostica, não prescreve e não substitui julgamento clínico.
2. **Prontuário é imutável na prática.** Append-only com versionamento (ver 2.2).
3. **Isolamento entre clínicas.** Dados de uma clínica nunca podem ser acessados por outra (ver 6.3).
4. **Segredos fora do código.** Nunca commitar chaves, tokens ou dados reais de tutores/animais. Use variáveis de ambiente e arquivos `.env.example`.
5. **Provedores externos atrás de interfaces.** WhatsApp, LLM, transcrição de áudio e emissão fiscal são acessados por interfaces, com implementação simulada (mock) explícita para desenvolvimento e testes.
6. **Simplicidade antes de generalização.** Não antecipe funcionalidades futuras nem crie abstrações sem necessidade atual.
7. **Honestidade nos relatórios.** Nunca declare como testado ou validado o que não foi efetivamente executado.

---

## 4. Metodologia de trabalho

O desenvolvimento é **incremental, por etapas, com aprovação humana antes de cada implementação**.

### 4.1 Fase de análise (padrão ao receber uma etapa)

Antes de escrever ou modificar código:

1. Analise os requisitos deste arquivo e as instruções dos subdiretórios.
2. Inspecione a estrutura atual do repositório, dependências, testes existentes e estado das alterações locais (`git status`).
3. Resuma seu entendimento do objetivo e dos limites da etapa.
4. Apresente a arquitetura proposta, aproveitando padrões existentes quando adequados.
5. Liste arquivos e diretórios que pretende criar ou modificar e a responsabilidade de cada um.
6. Informe dependências necessárias, justificando novas adições.
7. Identifique riscos, inconsistências, decisões pendentes e oportunidades de simplificação.
8. Defina critérios de aceite e os testes que demonstrarão o funcionamento.
9. Se houver alternativas relevantes, compare brevemente e recomende a mais adequada ao escopo.

**Nesta fase, apenas análise e inspeção.** Não altere arquivos, não instale dependências, não execute migrações, não configure serviços. Apresente o plano e **aguarde aprovação explícita**.

### 4.2 Fase de implementação (após aprovação)

- Implemente somente o plano aprovado e execute as verificações previstas nele.
- Preserve alterações existentes. Evite refatorações sem relação direta com a etapa.
- Se surgir necessidade que amplie o escopo, introduza custos ou altere decisão aprovada: explique o impacto e aguarde orientação antes de executar.
- Se faltarem credenciais ou informações essenciais, indique o bloqueio. Use provedores simulados apenas se previstos no plano, sempre com identificação explícita (nome da classe e log indicando "MOCK").

### 4.3 Fase de conclusão

Apresente:

- O que foi implementado e quais arquivos foram alterados.
- Como executar e verificar o resultado.
- Testes e verificações executados, **com resultados reais**.
- Limitações, pendências e critérios de aceite ainda não atendidos.
- Diferenças em relação ao plano aprovado.

Não publique, não faça deploy e não avance para a próxima etapa sem autorização.

---

## 5. Stack tecnológica

Status geral: `PROPOSTA`. Confirme na Etapa 0 antes de criar o projeto.

| Camada | Proposta | Justificativa |
|---|---|---|
| Backend | Python 3.12+, FastAPI | Familiaridade do responsável, bom ecossistema de IA |
| Validação | Pydantic v2 | Contratos de entrada e saída tipados |
| Banco | PostgreSQL | Relacional, adequado a dados clínicos e financeiros |
| ORM e migrações | SQLAlchemy 2.x + Alembic | Padrão maduro, migrações versionadas |
| Frontend | React + TypeScript + Vite | Familiaridade do responsável |
| Testes backend | pytest | Padrão do ecossistema |
| Testes frontend | Vitest + Testing Library | Integra com Vite |
| Containers | Docker + Docker Compose | Ambiente reproduzível |
| Jobs agendados | Simples primeiro (tabela de jobs + worker ou APScheduler) | Evitar Redis/Celery até haver necessidade comprovada |
| Lint e formatação | Ruff (Python), ESLint + Prettier (TS) | Padrão atual |
| Tipagem | mypy ou pyright (Python), `strict` no TypeScript | Segurança em refatorações |

Não adicione dependência nova sem justificar na fase de análise.

---

## 6. Arquitetura

### 6.1 Estilo

`PROPOSTA`: **monólito modular**. Um único backend, organizado em módulos de domínio com fronteiras claras. Sem microsserviços.

Fluxo de camadas dentro de cada módulo:

```
api (rotas, schemas HTTP)
  -> services (casos de uso, regras de negócio)
      -> repositories (acesso a dados)
          -> models (ORM)
```

Regras:

- Rotas não contêm regra de negócio.
- Services não conhecem HTTP.
- Repositories não contêm regra de negócio.
- Módulos se comunicam por **services** do outro módulo, nunca acessando diretamente as tabelas dele.

### 6.2 Estrutura de diretórios proposta

```
/
├── AGENTS.md
├── docker-compose.yml
├── .env.example
├── docs/
│   └── decisions/            # registros de decisão (ADR), um arquivo por decisão
├── backend/
│   ├── AGENTS.md             # regras específicas do backend (criar quando necessário)
│   ├── app/
│   │   ├── core/             # config, segurança, db, logging, erros
│   │   ├── modules/
│   │   │   ├── clinics/      # clínica, usuários, permissões
│   │   │   ├── tutors/
│   │   │   ├── patients/
│   │   │   ├── scheduling/   # agenda e atendimentos
│   │   │   ├── records/      # prontuário
│   │   │   ├── ai_scribe/    # rascunho assistido por IA
│   │   │   ├── messaging/    # WhatsApp, lembretes
│   │   │   ├── quotes/       # orçamento
│   │   │   ├── inventory/    # estoque e lotes
│   │   │   └── billing/      # caixa e fiscal (futuro)
│   │   ├── providers/        # interfaces + implementações (whatsapp, llm, stt, fiscal)
│   │   └── main.py
│   ├── migrations/
│   └── tests/
└── frontend/
    ├── AGENTS.md             # regras específicas do frontend (criar quando necessário)
    └── src/
```

Esta estrutura é `PROPOSTA`. Crie apenas os módulos da etapa atual, não todos de uma vez.

### 6.3 Multi-clínica (multi-tenant)

`PROPOSTA`: um único banco, com coluna `clinic_id` em todas as tabelas de negócio. O filtro por `clinic_id` deve ser aplicado **na camada de repository** de forma centralizada, para que seja impossível esquecê-lo em uma consulta individual. Testes de isolamento entre clínicas são obrigatórios para cada módulo que armazena dados.

### 6.4 Autenticação e permissões

`PENDENTE` (método de autenticação). `PROPOSTA` de papéis:

| Papel | Pode |
|---|---|
| `admin` | Tudo na clínica, incluindo usuários e configurações |
| `veterinarian` | Registrar e aprovar prontuário, prescrever, aprovar rascunhos de IA |
| `assistant` | Auxiliar no atendimento, sem aprovar registro clínico final |
| `reception` | Agenda, cadastro de tutor e animal, comunicação, sem acesso ao conteúdo clínico detalhado |

Somente `veterinarian` aprova conteúdo clínico.

### 6.5 Provedores externos (interfaces)

Cada integração externa tem uma interface e pelo menos uma implementação simulada:

| Interface | Finalidade | Implementação inicial |
|---|---|---|
| `MessagingProvider` | Enviar e receber WhatsApp | `MockMessagingProvider` |
| `LLMProvider` | Gerar texto estruturado | `MockLLMProvider` |
| `SpeechToTextProvider` | Transcrever áudio | `MockSpeechToTextProvider` |
| `FiscalProvider` | Emitir nota fiscal | Fora do escopo inicial |

Escolha do provedor real é `PENDENTE` para cada um. **Não escolha nem configure provedor real sem aprovação.** Ao propor, consulte a documentação oficial vigente, pois políticas e preços mudam.

---

## 7. Modelo de dados núcleo

Descrição conceitual. O esquema exato é definido e aprovado na etapa que o criar.

| Entidade | Campos relevantes (conceituais) |
|---|---|
| `Clinic` | id, nome, CNPJ (opcional), contato, configurações |
| `User` | id, clinic_id, nome, papel, CRMV e UF (se veterinário), ativo |
| `Tutor` | id, clinic_id, nome, telefone (WhatsApp), documento (opcional), endereço, consentimento de WhatsApp (data e origem) |
| `Patient` | id, clinic_id, nome, espécie, raça, sexo, castrado, nascimento ou idade estimada, pelagem, microchip (opcional), observações |
| `TutorPatient` | vínculo N:N entre tutor e paciente, com marca de responsável principal |
| `Appointment` | id, clinic_id, patient_id, veterinário, início, fim, tipo, status |
| `Encounter` | id, clinic_id, patient_id, appointment_id (opcional), veterinário, data |
| `RecordEntry` | id, encounter_id, conteúdo, versão, autor, criado_em, substitui (versão anterior) |
| `WeightRecord` | patient_id, peso, data |
| `VaccineRecord` | patient_id, vacina, partida (lote), fabricante, dose, fabricação, validade, data aplicada, próxima dose (art. 6º da Resolução CFMV nº 1321/2020) |
| `Quote`, `QuoteItem` | orçamento e itens, valores em centavos inteiros |
| `Product`, `Lot`, `StockMovement` | catálogo, lotes com validade, movimentações imutáveis |
| `Conversation`, `Message` | histórico de mensagens WhatsApp |
| `ReminderRule`, `ReminderJob` | regras e execuções de lembretes |
| `AiDraft` | rascunho gerado por IA, status (pendente, aprovado, descartado), vínculo ao encontro |
| `AuditLog` | quem, o quê, quando, em qual registro |

Convenções:

- Chaves primárias: UUID.
- Todas as tabelas de negócio: `clinic_id`, `created_at`, `updated_at`.
- Valores monetários: **inteiros em centavos**, nunca float.
- Datas e horas em UTC no banco; exibição no fuso `America/Fortaleza` (ou o da clínica, `PENDENTE`).
- Exclusão lógica (`deleted_at`) para entidades cadastrais. Prontuário e movimentações de estoque nunca são removidos.

---

## 8. Especificação dos módulos

### 8.1 Núcleo: tutores, animais e agenda

- Cadastro de tutor e animal com busca rápida por nome, telefone e microchip.
- Um tutor pode ter vários animais; um animal pode ter mais de um tutor.
- Telefone normalizado para formato internacional (E.164) para uso no WhatsApp.
- Agenda por veterinário com status: agendado, confirmado, em atendimento, concluído, cancelado, faltou.
- Impedir conflito de horário do mesmo veterinário.

### 8.2 Prontuário

- Estrutura base por atendimento: queixa principal, histórico, exame físico, avaliação, plano, prescrição, retorno sugerido. Os **campos obrigatórios finais** dependem da confirmação normativa (2.2).
- Edição gera nova versão, preservando a anterior e registrando autor e data.
- Linha do tempo do paciente (atendimentos, vacinas, pesos).
- Exportação do prontuário em PDF (etapa própria).

### 8.3 Prontuário com IA (scribe)

Fluxo conceitual:

```
áudio da consulta -> transcrição -> LLM gera rascunho SOAP estruturado
-> veterinário revisa e edita -> aprova -> vira RecordEntry oficial
```

Regras:

- O rascunho fica em `AiDraft`, **separado** do prontuário oficial.
- Só vira `RecordEntry` após aprovação de um `veterinarian`, que passa a ser o autor.
- Saída do LLM em **formato estruturado validado** por schema (Pydantic). Se inválida, tratar como falha, nunca gravar parcialmente.
- O prompt deve instruir a IA a **não inventar** informação ausente na transcrição e a marcar incertezas.
- Não registrar conteúdo clínico ou dados pessoais em logs de aplicação.
- Retenção do áudio: `PENDENTE`. Padrão seguro até decisão: **não persistir o áudio** após a transcrição.
- Aviso e consentimento do tutor para gravação: `PENDENTE`. Não implementar gravação real sem definição.
- Registrar no rascunho qual modelo e versão de prompt o geraram, para rastreabilidade.

### 8.4 Comunicação por WhatsApp

- Tipos de mensagem iniciais: confirmação de consulta, lembrete de consulta, lembrete de vacina, lembrete de retorno.
- Só enviar a tutores com **opt-in registrado**.
- Respeitar as regras vigentes da plataforma oficial de WhatsApp Business (modelos de mensagem aprovados, janela de conversa). **Consulte a documentação oficial atual na fase de análise**, não presuma.
- Webhooks de entrada devem ser **idempotentes** (mesma mensagem recebida duas vezes não duplica efeito).
- Respostas simples do tutor ("confirmo", "cancelar") atualizam o status da consulta.
- Um eventual agente conversacional **não dá orientação clínica**. Em caso de urgência ou dúvida de saúde, encaminha para atendimento humano da clínica. Escopo do agente conversacional é etapa própria e `PENDENTE`.
- Todas as mensagens enviadas e recebidas são registradas.
- Evitar conteúdo clínico detalhado nas mensagens (minimização de dados).

### 8.5 Orçamento

- Orçamento com itens (serviços e produtos), quantidades, valores unitários em centavos, desconto e total.
- Status: rascunho, enviado, aprovado, recusado, expirado.
- Pode ser vinculado a um atendimento e enviado ao tutor (canal definido na etapa).
- Aprovado é imutável; alteração gera novo orçamento.
- Cobrança e pagamento real estão fora do escopo inicial.

### 8.6 Estoque

- Produtos com unidade, estoque mínimo e controle por lote com validade.
- Movimentações imutáveis (entrada, saída, ajuste) com motivo e autor.
- Baixa por **FEFO**.
- Alertas de vencimento próximo e estoque abaixo do mínimo.
- Medicamentos de controle especial têm exigências legais próprias: **fora do escopo inicial** e `PENDENTE`.

### 8.7 Caixa e fiscal

- `PENDENTE` e **fora do escopo até decisão explícita**. A emissão de NFS-e depende do município e normalmente envolve provedor externo. Não implemente emissão fiscal sem plano aprovado.
- Exceção aprovada: financeiro básico manual da Etapa 10, limitado a recebimentos e despesas já realizados, histórico imutável e estorno administrativo; ver ADR 0013. Caixa completo, contas futuras e emissão fiscal permanecem fora do escopo.

---

## 9. Padrões de código

### 9.1 Idioma

`PROPOSTA`:

- Identificadores de código (classes, funções, tabelas, colunas): **inglês**.
- Textos de interface, mensagens ao usuário, documentação: **português do Brasil**.
- Termos de domínio seguem o glossário da seção 2.1 (ex.: tutor = `Tutor`, paciente = `Patient`).

### 9.2 Qualidade

- Tipagem completa em Python (type hints) e TypeScript em modo estrito.
- Funções pequenas, com uma responsabilidade.
- Erros de negócio tratados com exceções de domínio explícitas, convertidas em respostas HTTP padronizadas na borda. Nunca engolir exceção silenciosamente.
- Sem `print` de depuração no código final; use logging estruturado.
- Sem comentário que apenas repita o código. Comente o **porquê**, não o quê.
- Validação de entrada em toda borda (HTTP, webhooks, saída de LLM).
- Migrações de banco sempre versionadas e reversíveis quando possível.

### 9.3 Segurança

- Nenhum segredo no repositório.
- Consultas parametrizadas (via ORM), nunca concatenação de SQL.
- Hash seguro para senhas, se houver login por senha (`PENDENTE`).
- Registrar em `AuditLog` leitura e alteração de prontuário.
- Dados reais de pacientes nunca usados em testes ou fixtures. Use dados fictícios.

### 9.4 Git

- Commits pequenos e descritivos, preferencialmente no padrão Conventional Commits (`feat:`, `fix:`, `chore:`, `test:`, `docs:`).
- Não reescreva histórico nem faça push sem autorização.
- Preserve alterações locais não relacionadas à etapa.

---

## 10. Testes e critérios de aceite

### 10.1 Exigências mínimas por etapa

- Testes unitários para regras de negócio nos services.
- Testes de integração para repositories e rotas principais, com banco de teste isolado.
- Teste de **isolamento entre clínicas** em todo módulo que armazena dados.
- Testes dos caminhos de erro, não só do caminho feliz.
- Provedores externos sempre simulados nos testes.

### 10.2 Definição de pronto de uma etapa

Uma etapa só é considerada concluída quando:

1. Todos os critérios de aceite do plano aprovado foram atendidos **e verificados**.
2. Os testes da etapa passam, e os testes anteriores continuam passando.
3. Lint e checagem de tipos passam.
4. Há instruções claras de como executar e verificar.
5. O relatório final lista limitações e pendências sem omissões.

Se um comando de teste não puder ser executado no ambiente, informe isso explicitamente. Não afirme sucesso sem execução.

---

## 11. Comandos do projeto

Comandos atuais após a Etapa 11. Consulte `README.md` e os documentos `docs/etapa-N-verificacao.md` de cada etapa. As escolhas aprovadas de autenticação, ambiente gratuito local e isolamento estão em `docs/decisions/0003-etapa-1-auth-e-isolamento.md`; os cadastros estão em `docs/decisions/0004-etapa-2-tutores-e-pacientes.md`; a agenda está em `docs/decisions/0005-etapa-3-agenda-e-atendimentos.md`; o prontuário e suas fontes normativas estão em `docs/decisions/0006-etapa-4-prontuario.md`; documentos e laudos, em `docs/decisions/0007-etapa-4b-documentos.md`; lembretes e mensagens simuladas, em `docs/decisions/0008-etapa-5-lembretes-e-mensagens.md`; scribe simulado, em `docs/decisions/0009-etapa-6-scribe-simulado.md`; orçamentos, em `docs/decisions/0010-etapa-7-orcamentos.md`; estoque, em `docs/decisions/0011-etapa-8-estoque.md`; exportação em PDF, em `docs/decisions/0012-etapa-9-prontuario-pdf.md`; financeiro básico manual, em `docs/decisions/0013-etapa-10-financeiro.md`; navegação e interface compartilhadas, em `docs/decisions/0014-etapa-11-navegacao-e-interface.md`.

Pré-requisitos: Docker Desktop com containers Linux, Node.js 22.20+ da linha 22, npm e uv. O Supabase local não exige login na conta da nuvem. Nenhum projeto hospedado foi criado.

Na raiz:

```powershell
npm ci
npm run dev
```

`npm run dev` inicia Supabase local, configura o ambiente, aplica as migrações e sobe backend, frontend e worker de lembretes MOCK. Aplicação: `http://localhost:5173`. API: `http://localhost:8000/health`. Documentação: `http://localhost:8000/docs`. A rota de saúde continua verificando somente a API.

Para parar sem apagar dados:

```powershell
docker compose down
npm run db:stop
```

Para executar os aplicativos diretamente na máquina, mantenha Supabase local no Docker com `npm run db:start` e `npm run setup`. Em terminais separados:

```powershell
# Em backend/
uv sync --frozen
uv run --env-file ../.env --frozen uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Em outro terminal, em backend/, para os lembretes MOCK:
uv run --env-file ../.env --frozen python -m app.worker

# Em frontend/
npm ci
npm run dev
```

Verificações do backend, em `backend/`:

```powershell
uv run --env-file ../.env --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy
```

Os testes usam banco local isolado, configurado por `npm run setup`. Alternativa em container, na raiz: `npm run check:backend`.

Verificações do frontend, em `frontend/`:

```powershell
npm test
npm run lint
npm run format:check
npm run typecheck
npm run build
```

Migrações da aplicação, em `backend/`:

```powershell
uv run --env-file ../.env --frozen alembic upgrade head
```

O frontend não possui migrações de banco. A primeira clínica e seus usuários são provisionados pelo comando local `python -m app.bootstrap`; instruções e opções no README. Não existem contas ou senhas padrão no código.

---

## 12. Roadmap de etapas

`PROPOSTA`: a ordem abaixo prioriza uma base sólida e depois os diferenciais. Confirme com o responsável antes de iniciar cada etapa. Cada etapa tem escopo próprio, e o que está em "Fora do escopo" não deve ser feito nela.

### Etapa 0: Fundação do repositório

- **Objetivo:** projeto executável com estrutura, ambiente reproduzível e pipeline de qualidade.
- **Escopo:** estrutura de diretórios, Docker Compose com PostgreSQL, backend mínimo com rota de saúde (`/health`), frontend mínimo, configuração de lint, tipagem e testes, `.env.example`, preenchimento da seção 11.
- **Fora do escopo:** qualquer regra de negócio, autenticação, modelos de domínio.
- **Aceite:** ambiente sobe com um comando, `/health` responde, testes e lint rodam.

### Etapa 1: Clínica, usuários e autenticação

- **Objetivo:** identificar quem usa o sistema e isolar clínicas.
- **Escopo:** `Clinic`, `User`, papéis, autenticação (método a definir), filtro por `clinic_id` centralizado.
- **Fora do escopo:** cadastros clínicos, cobrança de assinatura.
- **Aceite:** usuário de uma clínica não acessa dados de outra (teste automatizado).

### Etapa 2: Tutores e animais

- **Objetivo:** cadastro e busca de tutores e pacientes.
- **Escopo:** CRUD de `Tutor`, `Patient`, vínculo N:N, busca, normalização de telefone, registro de consentimento de WhatsApp.
- **Fora do escopo:** prontuário, agenda, envio de mensagens.
- **Aceite:** cadastrar, buscar e vincular; isolamento entre clínicas testado.

### Etapa 3: Agenda e atendimentos

- **Objetivo:** agendar e acompanhar consultas.
- **Escopo:** `Appointment`, `Encounter`, status, conflito de horário.
- **Fora do escopo:** lembretes automáticos, prontuário detalhado.
- **Aceite:** agendamento sem conflito, mudança de status, listagem por dia e veterinário.

### Etapa 4: Prontuário

- **Objetivo:** registro clínico versionado e auditável.
- **Escopo:** `RecordEntry` com versionamento, peso, vacinas, linha do tempo, `AuditLog`. Confirmação normativa dos campos (2.2) como primeira tarefa.
- **Fora do escopo:** IA, exportação em PDF.
- **Aceite:** edição preserva versão anterior; leitura e escrita auditadas.

### Etapa 4b: Documentos e laudos (concluída em 2026-11-03)

- **Objetivo:** guardar a cópia de cada laudo de exame complementar no prontuário (art. 9º, X, da Resolução CFMV nº 1321/2020, com a redação da nº 1653/2025). Implementação e verificação registradas na ADR 0007 e em `docs/etapa-4b-verificacao.md`.
- **Fora do escopo:** pesquisa ou leitura de anexos por IA, que fica para depois das etapas do roadmap.

### Etapa 5: Lembretes por WhatsApp (com provedor simulado)

Implementação verificada em 2026-11-09, incluindo correções aprovadas de janela de envio, replanejamento e idempotência concorrente. Evidências e limitações em `docs/etapa-5-verificacao.md`; decisões em `docs/decisions/0008-etapa-5-lembretes-e-mensagens.md`.

- **Objetivo:** reduzir faltas e perda de retorno.
- **Escopo:** `MessagingProvider` com mock, regras de lembrete (consulta, vacina, retorno), jobs agendados, registro de mensagens, atualização de status por resposta simples.
- **Fora do escopo:** provedor real de WhatsApp, agente conversacional, campanhas promocionais.
- **Aceite:** com o mock, lembretes são gerados no momento certo, respeitam opt-in e são idempotentes.

### Etapa 6: Scribe de IA (com provedores simulados)

Plano aprovado e implementação verificada em 2026-11-09. Entrada por texto ou exemplo fictício, sem captura/upload de áudio real. Evidências e limitações em `docs/etapa-6-verificacao.md`; decisões em `docs/decisions/0009-etapa-6-scribe-simulado.md`.

- **Objetivo:** rascunho de prontuário a partir da consulta.
- **Escopo:** `AiDraft`, interfaces `SpeechToTextProvider` e `LLMProvider` com mocks, saída estruturada validada, fluxo de revisão e aprovação.
- **Fora do escopo:** provedores reais, retenção de áudio, captura de áudio no navegador (a menos que o plano aprovado inclua).
- **Aceite:** rascunho nunca vira registro oficial sem aprovação de veterinário; saída inválida é rejeitada.

### Etapa 7: Orçamento

Plano aprovado e implementação verificada em 2026-11-09: itens manuais, cálculo exato, apresentação manual, registro de decisão do tutor e revisão preservando o original. Evidências e limitações em `docs/etapa-7-verificacao.md`; decisões em `docs/decisions/0010-etapa-7-orcamentos.md`.

- **Escopo:** `Quote`, itens, status, cálculo em centavos, vínculo a atendimento.
- **Fora do escopo:** cobrança, pagamento, envio automatizado (se não aprovado).

### Etapa 8: Estoque

Plano aprovado e implementação verificada em 2026-11-09: produtos, lotes, movimentações imutáveis, baixa FEFO, ajustes e alertas. Evidências e limitações em `docs/etapa-8-verificacao.md`; decisões em `docs/decisions/0011-etapa-8-estoque.md`.

- **Escopo:** produtos, lotes, movimentações, FEFO, alertas de validade e mínimo.
- **Fora do escopo:** controlados, compras automáticas, fiscal.

### Etapa 9: Exportação do prontuário em PDF

Plano aprovado e implementação verificada em 2026-11-10: PDF preservado por emissão, versões anteriores, anexos originais em ZIP e auditoria. Sem assinatura digital incorporada; assinatura e entrega permanecem manuais. Evidências e limitações em `docs/etapa-9-verificacao.md`; decisões em `docs/decisions/0012-etapa-9-prontuario-pdf.md`.

- **Escopo:** preparação por veterinário, cópia PDF imutável, histórico e downloads PDF/ZIP com controle de acesso.
- **Fora do escopo:** certificado digital, recibo eletrônico, automação de pedidos/prazos e envio externo.

### Etapa 10: Financeiro básico manual

Plano aprovado e implementação verificada em 2026-11-10: recebimentos e despesas já realizados, centavos exatos, filtros, totais e histórico imutável com estorno administrativo na data financeira original. Administradores têm acesso completo; recepção somente a recebimentos; veterinários e auxiliares sem acesso. Evidências e limites em `docs/etapa-10-verificacao.md`; decisões em `docs/decisions/0013-etapa-10-financeiro.md`. Conferência visual manual pendente por indisponibilidade de navegador na sessão; testes automatizados da interface executados.

- **Escopo:** registros manuais, vínculos opcionais com tutor/paciente, consulta por período e correção por estorno e novo lançamento.
- **Fora do escopo:** contas futuras, parcelas, saldo inicial, abertura/fechamento de caixa, pagamentos, conciliação, fiscal e geração automática por orçamento/estoque.

### Etapa 11: Navegação interna e interface compartilhadas

Plano global aprovado e implementação automatizada verificada em 2026-11-11: telas próprias para ações e detalhes, botão Voltar junto ao título, preservação da lista no retorno, navegação por níveis e identidade visual comum a todas as áreas e perfis. Evidências em `docs/etapa-11-verificacao.md`; decisões em `docs/decisions/0014-etapa-11-navegacao-e-interface.md`. Inspeção visual em navegador real permanece pendente por indisponibilidade da ferramenta na sessão.

- **Escopo:** interface de todos os módulos existentes, estilos responsivos compartilhados, foco e testes de navegação; permissões anteriores preservadas.
- **Fora do escopo:** novas regras de negócio, backend/banco, dependências, URLs individuais, links diretos e histórico Voltar/Avançar do navegador.

### Etapas futuras (sem planejamento ainda)

Integração real de WhatsApp, provedores reais de IA, assinatura digital e fluxo de entrega do prontuário, ampliação de caixa e fiscal, relatórios, agente conversacional.

---

## 13. Fora do escopo global (fase inicial)

Não implemente, não configure e não proponha como parte de etapas iniciais, sem autorização explícita:

- Aplicativo móvel nativo.
- Telemedicina.
- IA diagnóstica por imagem ou integração com equipamentos de imagem (DICOM).
- Pagamentos online e gateway de cobrança.
- Emissão fiscal real.
- Portal de login para o tutor.
- Internacionalização para outros idiomas.
- Infraestrutura de produção, deploy e CI/CD (a menos que uma etapa específica peça).

---

## 14. Riscos e pontos de atenção

| Risco | Cuidado |
|---|---|
| Escopo grande para uma pessoa | Seguir etapas pequenas; resistir a antecipar módulos |
| Conformidade do prontuário | Confirmar normas do CFMV vigentes antes de modelar |
| Erros da IA no registro clínico | Revisão humana obrigatória; rascunho separado; rastreabilidade |
| Vazamento de dados | Isolamento por clínica, sem dados reais em testes, sem conteúdo clínico em logs |
| Regras do WhatsApp mudam | Consultar documentação oficial atual; interface de provedor desacoplada |
| Dependência de provedores | Interfaces e mocks; evitar acoplamento |
| Competição com sistemas completos | Focar no diferencial: prontuário com IA e WhatsApp em português |

---

## 15. Registro de decisões

Cada decisão relevante aprovada deve virar um arquivo curto em `docs/decisions/` (formato: contexto, decisão, consequências, data). Ao propor uma decisão que altera algo marcado `DECIDIDO` aqui, sinalize explicitamente o conflito e aguarde orientação. Quando uma decisão `PROPOSTA` ou `PENDENTE` for aprovada, o responsável atualiza o status neste arquivo.

---

## 16. Instruções para AGENTS.md em subdiretórios

Quando o backend e o frontend existirem, crie `backend/AGENTS.md` e `frontend/AGENTS.md` **somente quando o responsável autorizar**. Eles devem conter apenas regras específicas daquela parte (comandos, convenções de pastas, bibliotecas permitidas) e referenciar este arquivo para o restante. Não duplique conteúdo deste documento.

---

## 17. Modelo de prompt por etapa

O responsável usará o modelo abaixo ao iniciar ou continuar o trabalho. Ele reforça as regras da seção 4.

```
Quero iniciar ou continuar o desenvolvimento do Sistema Veterinário, uma ferramenta
destinada a clínicas veterinárias pequenas no Brasil (prontuário com IA, comunicação
por WhatsApp, orçamento e estoque).

As tecnologias previstas são [STACK APROVADA ou "conforme AGENTS.md, seção 5"].

Leia integralmente o arquivo AGENTS.md na raiz do projeto e as instruções adicionais
aplicáveis aos diretórios envolvidos. Utilize essas definições como referência
principal para compreender o produto, suas regras e sua arquitetura.

Se o arquivo estiver ausente, apresentar contradições ou descrever outro projeto,
informe o problema antes de implementar. Não presuma requisitos que não estejam
documentados.

Nossa metodologia será incremental, com minha supervisão e aprovação antes da
implementação de cada etapa.

Etapa atual
Quero trabalhar exclusivamente em [NÚMERO E NOME DA ETAPA].
O objetivo desta etapa é [RESULTADO CONCRETO ESPERADO].

Escopo autorizado:
- [ENTREGA 1]
- [ENTREGA 2]

Fora do escopo:
- [EXCLUSÃO 1]
- [EXCLUSÃO 2]

Antes de escrever ou modificar código, siga a seção 4.1 do AGENTS.md. Nesta fase,
realize apenas análise e inspeção, apresente o plano e aguarde minha aprovação
explícita.

Após minha aprovação, siga a seção 4.2. Ao concluir, siga a seção 4.3.
Não declare como validado o que não foi efetivamente verificado. Não publique,
faça deploy ou avance para a próxima etapa sem minha autorização.
```
