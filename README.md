# Sistema Veterinário

Aplicação para clínicas veterinárias pequenas no Brasil. Etapas implementadas: fundação; clínica, usuários e autenticação; tutores e animais; agenda e atendimentos. Prontuário e os demais módulos serão desenvolvidos em etapas próprias.

## Ambiente gratuito e local

PostgreSQL e Supabase Auth executam no Docker, neste computador. Nenhum projeto hospedado, plano pago, envio de e-mail ou implantação é configurado. Os projetos existentes da conta Supabase não são alterados. Não é preciso autenticar a CLI na conta da nuvem.

Pré-requisitos: Docker Desktop iniciado com containers Linux, Node.js 22.20+ da linha 22, npm e [uv](https://docs.astral.sh/uv/). O uv disponibiliza Python 3.12 e instala as dependências fixadas em `backend/uv.lock`.

Na primeira execução, na raiz:

```powershell
npm ci
```

Depois, para iniciar toda a aplicação com um comando:

```powershell
npm run dev
```

Esse comando cria/verifica uma rede Docker que publica portas somente em `127.0.0.1`, inicia Supabase local, gera a configuração ignorada pelo Git, aplica as migrações Alembic e inicia backend e frontend. A primeira execução baixa imagens e pode demorar. Os dados locais são preservados nas próximas inicializações.

- Aplicação: <http://localhost:5173>
- API: <http://localhost:8000/docs>
- Saúde da API: <http://localhost:8000/health> → `{"status":"ok"}`
- Supabase Auth local: <http://127.0.0.1:54321/auth/v1>

`/health` verifica somente a API, não o banco ou o Auth. Supabase Studio, Storage, Realtime e serviços de IA não são necessários nesta etapa e ficam desativados.

Para parar, sem apagar dados:

```powershell
docker compose down
npm run db:stop
```

## Primeiro administrador e novos usuários

O cadastro público está bloqueado. Provisionar contas é uma ação explícita e local. Em `backend/`:

```powershell
uv run --env-file ../.env --frozen python -m app.bootstrap --clinic-name "Clínica fictícia" --name "Administrador fictício" --email "admin@example.test"
```

O comando pede uma senha com pelo menos 12 caracteres sem exibi-la e informa o identificador da clínica. Não envia convites ou e-mails. Repetir o comando para um usuário já provisionado não troca sua senha nem cria outra clínica.

Para adicionar alguém à clínica existente, substitua `UUID_DA_CLINICA` pelo identificador retornado:

```powershell
uv run --env-file ../.env --frozen python -m app.bootstrap --clinic-id UUID_DA_CLINICA --name "Recepção fictícia" --email "recepcao@example.test" --role reception
```

Papéis: `admin`, `veterinarian`, `assistant`, `reception`. Veterinários exigem `--crmv` e `--crmv-state`. A interface permite ao administrador alterar nome, papel, CRMV/UF e situação ativa dos usuários provisionados. Não é permitido remover o último administrador ativo.

Para a verificação desta entrega, foram provisionadas duas clínicas fictícias. O acesso de demonstração está em `.cache/acesso-local.txt`, apenas neste computador, ignorado pelo Git. Senhas não são fixadas no código ou nesta documentação. Quem clonar o repositório deve usar o comando de provisionamento acima.

## Tutores e animais — Etapa 2

Após entrar, abra **Tutores** ou **Animais**. Administradores e recepção cadastram, alteram e arquivam; veterinários e auxiliares consultam. O backend e o banco também verificam as permissões.

Em Tutores, busque por nome ou telefone. O telefone é opcional e normalizado para E.164; números nacionais usam Brasil como região padrão. Documento e endereço são opcionais. Autorizar WhatsApp exige telefone e origem da autorização, com data registrada pelo servidor. Trocar o telefone revoga a autorização; registre outra somente se o tutor a conceder. Nenhuma mensagem é enviada nesta etapa.

Em Animais, busque por nome ou microchip. Nome e espécie são obrigatórios; os demais campos são opcionais. Informe nascimento ou idade estimada em meses. O microchip é único entre pacientes ativos da mesma clínica. Ao salvar ou abrir “Tutores de…”, vincule os responsáveis: um tutor pode cuidar de vários pacientes, e cada paciente pode ter vários tutores. O primeiro vínculo é principal; é possível escolher outro. Remover o principal não escolhe automaticamente um substituto.

Arquivar preserva o cadastro. Tutores arquivados permanecem nos vínculos anteriores, identificados como arquivados, com autorização revogada; não são oferecidos para novos vínculos. Esta entrega não inclui restauração de cadastros ou consulta de pacientes arquivados pela interface.

## Agenda e atendimentos — Etapa 3

Após entrar, abra **Agenda**. Escolha o dia e, se quiser, filtre por veterinário. Os horários seguem o fuso `America/Fortaleza`.

Administradores e recepção agendam, reagendam, confirmam, cancelam ou marcam falta. O mesmo veterinário não pode ter dois agendamentos no mesmo intervalo; cancelados e faltas liberam o horário e continuam registrados. Reagendar volta a situação para “Agendado”, pois o novo horário precisa ser confirmado com o tutor.

O veterinário responsável inicia e conclui o atendimento. Ele também pode abrir um atendimento avulso, sem agendamento, que começa no horário atual. Auxiliares consultam a agenda. Nesta etapa não há lembretes, mensagens ou prontuário.

## Autenticação e isolamento

O frontend autentica pelo cliente oficial Supabase e envia o token à API. A API verifica a identidade com o servidor Auth e consulta o perfil ativo, sua clínica e papel no banco em cada requisição. Não aceita clínica ou papel informados pelo cliente para autorizar acesso.

As tabelas ficam no schema privado `vetsys`, sem acesso pela Data API. O filtro centralizado dos repositories é reforçado por RLS obrigatório. A conexão da aplicação usa `vetsys_app`, sem privilégios administrativos ou bypass de RLS; a API recusa conexões privilegiadas. O contexto é limitado à transação e não fica no pool.

Logout encerra a sessão no cliente e impede renovar o token. Um token já emitido pode continuar válido até expirar, em até 15 minutos. Desativar o usuário na aplicação bloqueia suas próximas requisições imediatamente. As sessões do navegador são gerenciadas pelo SDK do Supabase; nenhuma senha é armazenada pela aplicação.

## Executar os aplicativos fora dos containers

Supabase local continua dependendo do Docker. Na raiz:

```powershell
npm run db:start
npm run setup
```

Em terminais separados, depois de parar os containers da aplicação com `docker compose down`:

```powershell
# Em backend/
uv sync --frozen
uv run --env-file ../.env --frozen uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log

# Em frontend/
npm ci
npm run dev
```

## Verificações

Em `backend/`:

```powershell
uv run --env-file ../.env --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy
```

Os testes de integração exigem `npm run setup` antes. Usam exclusivamente `vetsys_test`, com dados fictícios; recusam conexão remota. O teste de migração cria um banco temporário identificado por UUID, verifica upgrade/downgrade/upgrade e o remove ao terminar. O banco da aplicação não é limpo pelos testes. O Auth é simulado nos testes automatizados; o login real local foi verificado separadamente nesta entrega.

Para executar a mesma verificação do backend em container, após construir as imagens, use na raiz:

```powershell
npm run check:backend
```

Em `frontend/`, depois de `npm ci`:

```powershell
npm test
npm run lint
npm run format:check
npm run typecheck
npm run build
```

Diagnóstico de segurança local, na raiz:

```powershell
npx supabase db advisors --local --type all --level warn --fail-on warn
```

## Migrações e configuração

As migrações do schema da aplicação são mantidas somente no Alembic. Para aplicar, em `backend/`:

```powershell
uv run --env-file ../.env --frozen alembic upgrade head
```

Não execute downgrade no banco com dados que precisam ser preservados: o downgrade inicial remove as tabelas desta etapa. O teste de reversibilidade usa somente banco temporário isolado.

`npm run setup` gera `.env` e `frontend/.env.local`. Não versionar esses arquivos. A API em execução recebe somente a conexão restrita, a URL de Auth e a chave publicável. A conexão administrativa e a chave secreta ficam exclusivas dos comandos locais de configuração/provisionamento. O frontend recebe apenas URL e chave publicável. Os arquivos `.env.example` não contêm credenciais.

## Limitações

Ambiente exclusivo de desenvolvimento local, sem HTTPS e sem deploy. Recuperação de senha, convites, edição de e-mail/senha pela interface e múltiplas clínicas por usuário ficam fora desta entrega. A migração para projeto hospedado depende de decisão futura e confirmação de custo zero ou nova autorização.

Os resultados executados e a limitação de revisão visual estão em `docs/etapa-1-verificacao.md` e `docs/etapa-2-verificacao.md`. As decisões aprovadas estão em `docs/decisions/`. O aviso de depreciação HTTPX/TestClient continua documentado; os testes passam sem ocultá-lo.

Os commits e o envio ao repositório `JoaoKelvinDev/Clinica-Veterinaria` ficam com o responsável. A relação de arquivos e as instruções para separar as duas entregas estão em `docs/arquivos-por-etapa.md`. A parte financeira empresarial será planejada depois da etapa em andamento, conforme orientação do responsável; não foi implementada nesta entrega.
