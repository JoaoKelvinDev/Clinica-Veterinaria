# Sistema Veterinário

Aplicação para clínicas veterinárias pequenas no Brasil. Etapas implementadas: fundação; clínica, usuários e autenticação; tutores e animais; agenda e atendimentos; prontuário; documentos e laudos; lembretes e mensagens com provedor simulado; scribe com provedores simulados; orçamentos; estoque; exportação do prontuário em PDF; financeiro básico manual; navegação compartilhada; visão geral da clínica. As integrações e funções futuras serão desenvolvidas em etapas próprias.

## Visão geral da clínica — Etapa 12

Após entrar, a tela inicial **Visão geral** reúne a agenda do dia, os atendimentos em aberto (inclusive de dias anteriores), as mensagens aguardando atenção e os alertas de estoque. Administradores veem também recebimentos, despesas e diferença do mês; recepção vê somente recebimentos; veterinários e auxiliares não recebem dados financeiros.

As contagens consideram todos os registros elegíveis da clínica, independentemente da paginação. Dia e mês seguem `America/Fortaleza`. O financeiro exclui estornados na data financeira original; a diferença não representa lucro contábil nem saldo bancário. Os alertas de validade incluem apenas lotes com saldo positivo de produtos ativos, com janela de hoje até 30 dias.

Use os botões dos cartões para abrir cada área sem recarregar a página. **Agenda** continua no menu. Os resumos carregam ao abrir a Visão geral e pelo botão **Atualizar visão geral**; não há atualização automática. Em caso de falha, a tela mostra um erro e permite tentar novamente, sem apresentar totais antigos como atuais. Mensagens continuam em modo MOCK.

Decisões na [ADR 0015](docs/decisions/0015-etapa-12-visao-geral.md); verificações e pendência de revisão visual em [Verificação da Etapa 12](docs/etapa-12-verificacao.md).

## Ambiente gratuito e local

No desenvolvimento local, PostgreSQL e Supabase Auth executam no Docker, neste computador. Os comandos desta seção não criam projetos hospedados nem contratam planos pagos. Separadamente, a demonstração com dados fictícios foi autorizada e publicada na Vercel com o Supabase gratuito `vetsys-demo`. Os projetos anteriores da conta Supabase foram preservados. Não é preciso autenticar a CLI na conta da nuvem para executar o ambiente local.

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

`/health` verifica somente a API, não o banco ou o Auth. O Storage local guarda os anexos do prontuário num bucket privado, criado pelo `npm run dev`. Supabase Studio, Realtime e serviços de IA não são necessários e ficam desativados.

Para parar, sem apagar dados:

```powershell
docker compose down
npm run db:stop
```

## Demonstração hospedada — Etapa 13

O Supabase de demonstração possui banco isolado, Auth e Storage privado. A avaliação utiliza somente BIBI e MICAELLY, com papel de veterinário e identificações TESTE, somente para dados fictícios. Os rascunhos clínicos de exemplo permanecem pendentes de revisão.

Em 12/11/2026, os dados iniciais foram arquivados e substituídos nas listas ativas por 6 tutores, 8 pacientes detalhados, agenda de demonstração, rascunhos pendentes, orçamentos, estoque e financeiro fictício. Os quatro perfis e os históricos foram preservados. BIBI e MICAELLY são as únicas veterinárias ativas; o perfil anterior foi desativado pela API e retirado dos materiais atuais de avaliação, mantendo a autoria e o atendimento histórico em aberto. Veja [verificação da renovação](docs/demo-profissional-verificacao.md) e [ADR 0018](docs/decisions/0018-renovacao-dados-demonstracao.md).

Acesse **https://vetsys-demo.vercel.app** com o login individual fornecido pelo responsável. A interface React e a API Python são dois projetos Vercel do mesmo sistema; o proxy `/api` conecta ambos. Não é necessário login na Vercel para acessar a produção. Na publicação inicial foram verificados os três logins, permissões, isolamento RLS, anexos e PDF/ZIP pelo domínio público. Após a renovação, os acessos disponíveis de BIBI e MICAELLY passaram por 85 checagens HTTP de identidade, leitura e bloqueios; veja [verificação dos perfis](docs/perfis-avaliadoras-verificacao.md). A inspeção visual em navegador permanece pendente.

O modo `VERCEL=1` configura a API serverless; `VITE_DEMO_MODE=true` identifica a demonstração e limita anexos pela interface a 4 MiB. No ambiente local permanecem 10 MiB. O worker contínuo não foi implantado: lembretes usam o disparo manual MOCK existente. Downloads de 4 MiB e ZIP de aproximadamente 6,4 MB passaram; pacotes de 100 MiB não foram validados. Os arquivos individuais de acesso em `.cache` já contêm o link público; as versões locais anteriores foram preservadas.

Estado, verificações, limites e próximos passos em [Etapa 13 — Demonstração](docs/etapa-13-demonstracao-status.md). Credenciais continuam exclusivamente em arquivos ignorados pelo Git.

A nova tela de entrada baseada no projeto Lovable `pawprint-clinic-welcome` foi implementada localmente, com foto e fontes locais e autenticação existente. A mudança abrange somente a entrada; dashboard e módulos internos mantêm o visual anterior. Essa versão ainda aguarda revisão visual e autorização para publicação. Veja [verificação da tela de entrada](docs/login-visual-verificacao.md) e [ADR 0017](docs/decisions/0017-tela-de-entrada-lovable.md).

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

## Prontuário — Etapa 4

Abra **Animais** e escolha “Prontuário de…”, ou use o botão no atendimento da **Agenda**. O prontuário segue o art. 9º da Resolução CFMV nº 1321/2020, com a redação da nº 1653/2025.

Cada registro pertence a um atendimento e guarda data, hora, local, autor e CRMV. Relato do responsável, estado geral e diagnóstico presuntivo são obrigatórios. Nada é apagado: “Corrigir registro” cria uma nova versão com motivo, e a anterior continua em “Ver versões anteriores”. Somente o autor corrige o próprio registro.

Veterinários registram prontuário e vacinas; auxiliares registram peso; administradores e auxiliares consultam. A recepção vê apenas as datas dos atendimentos. Vacinas exigem nome, partida, fabricante, dose, fabricação e validade. Leituras e registros ficam na auditoria, sem conteúdo clínico.

A exportação em PDF está descrita na Etapa 9 abaixo. Assinatura com certificado digital não está implementada.

## Documentos e laudos — Etapa 4b

No prontuário, em **Documentos e laudos**, veterinários e auxiliares usam **Adicionar documento** para laudos de exame, históricos de outros veterinários ou clínicas, receitas e outros documentos. Informe tipo, origem e data e anexe o arquivo, escreva um resumo ou faça os dois. Arquivos aceitos: PDF, JPG ou PNG de até 10 MB, conferidos pelo conteúdo.

Os arquivos ficam no Supabase Storage local, num bucket privado; o navegador só os recebe pelo backend, que confere a permissão e a integridade (SHA-256). Nada é apagado: **Corrigir documento** cria uma nova versão e pode manter o arquivo anterior. A recepção não vê os documentos.

## Lembretes e mensagens — Etapa 5

Abra **Mensagens** para consultar próximos lembretes, envios processados, histórico e respostas que precisam de atenção. O modo **MOCK** é explícito: nenhuma mensagem sai do computador e não há integração real com WhatsApp.

O serviço `worker` do Docker verifica os lembretes a cada minuto. As regras atuais são fixas: pedido de confirmação 24 horas antes da consulta; lembrete 2 horas antes, depois da confirmação; vacina 7 dias antes da próxima dose; retorno 2 dias antes da data informada no prontuário. Os avisos de vacina e retorno são planejados para 9h. Se o prazo já chegou, o planejamento usa a próxima janela permitida antes do evento.

Os lembretes saem a partir de 8h e antes de 20h, em `America/Fortaleza`. Se o worker retomar à noite, aguarda a próxima janela; eventos que já passaram não geram envio. O destinatário é o tutor principal ativo, com telefone e autorização de WhatsApp ainda válidos no momento do envio. Reagendamentos, cancelamentos e correções de vacina ou retorno ajustam os lembretes pendentes.

Administradores e recepção podem disparar lembretes vencidos, simular respostas e marcar pendências como resolvidas. Veterinários e auxiliares consultam. Na simulação, **CONFIRMO** confirma a consulta associada à mensagem mais recente, **CANCELAR** cancela e **SAIR** revoga a autorização dos tutores com aquele telefone na clínica. Respostas não reconhecidas ou sem consulta identificada seguem para a equipe. Repetir o mesmo identificador de mensagem, inclusive simultaneamente, não repete seus efeitos.

As mensagens automáticas evitam detalhes clínicos. Não há envio livre pela equipe, campanhas, agente conversacional, webhook público ou configuração das regras pela interface. Decisões em `docs/decisions/0008-etapa-5-lembretes-e-mensagens.md`; resultados e limitações em `docs/etapa-5-verificacao.md`.

## Rascunhos assistidos — Etapa 6

No prontuário de um paciente, abra **Rascunhos assistidos (MOCK)**. Um veterinário com CRMV cadastrado pode escolher **Novo rascunho MOCK**, selecionar um atendimento e colar uma transcrição de até 20 mil caracteres, ou usar o exemplo fictício de transcrição.

Não há IA ou transcrição de áudio reais nesta entrega. O `MockSpeechToTextProvider` devolve um exemplo fixo, sem gravação ou upload de áudio. O `MockLLMProvider` copia linhas com os rótulos indicados na tela para os campos correspondentes; texto sem rótulo fica no relato do responsável. Ele não interpreta semanticamente a consulta nem propõe diagnóstico ou conduta. Campos ausentes ficam vazios e exigem revisão.

Na revisão, a transcrição e o conteúdo gerado original ficam disponíveis ao lado dos campos SOAP editáveis. Complete relato, estado geral e diagnóstico presuntivo, confira os demais campos, marque **Revisei a transcrição e todos os campos e assumo a autoria do registro** e use **Aprovar e registrar no prontuário**. A aprovação cria um registro novo, com autoria e CRMV do veterinário aprovador, auditoria e planejamento de retorno quando houver data. O solicitante e o aprovador podem ser veterinários diferentes da mesma clínica.

Gerar ou descartar nunca cria registro oficial. O rascunho original e sua transcrição são preservados, inclusive após o descarte. As edições da revisão são gravadas somente na aprovação: fechar ou recarregar a tela perde edições ainda não aprovadas. Um rascunho finalizado não pode ser reaberto; correções do registro oficial seguem o versionamento já existente.

Administradores e auxiliares consultam os rascunhos; a recepção não os acessa. Modelo, provedor e versão do prompt ficam registrados. Não há envio dos dados a um provedor externo. Decisões em `docs/decisions/0009-etapa-6-scribe-simulado.md`; resultados, comandos e limitações em `docs/etapa-6-verificacao.md`.

## Orçamentos — Etapa 7

Abra **Orçamentos** para criar e acompanhar estimativas. Administradores, veterinários e recepção escrevem; auxiliares consultam. Escolha um paciente, um tutor ativo vinculado a ele e, se desejar, um atendimento do mesmo paciente.

Informe serviços ou produtos manualmente, sem catálogo ou movimentação de estoque. Quantidades aceitam até três casas decimais; preços e desconto, até duas, com vírgula ou ponto e sem separador de milhar. Cada item é arredondado para centavos, com meio centavo para cima; depois os itens são somados e o desconto fixo é subtraído. O desconto pode zerar o total, mas não superar o subtotal. O backend calcula os valores finais e o banco confere os totais dos itens.

**Salvar rascunho** permite continuar editando. Depois de mostrar o orçamento ao tutor, use **Marcar como apresentado**: a situação passa a **Enviado**, sem disparar mensagens. Nessa etapa ficam preservados nomes, vínculos, itens, validade e valores. Para corrigir, use **Criar revisão**, que cria outro rascunho vinculado ao original; o orçamento anterior permanece preservado. Criar uma revisão não revoga uma aprovação anterior automaticamente.

Use **Registrar aprovação** ou **Registrar recusa** para registrar a decisão comunicada pelo tutor. Informe origem presencial, telefone ou outra; a última opção exige observação. O sistema registra usuário e horário. Não há acesso do tutor ao sistema, cobrança ou pagamento.

A validade é opcional e vale até o fim do dia informado em `America/Fortaleza`. Orçamentos enviados vencidos aparecem como **Expirado** e não recebem aprovação ou recusa; podem originar uma revisão. Orçamentos já aprovados ou recusados preservam sua situação. Atualizações concorrentes ou baseadas em uma versão antiga recebem conflito: reabra o orçamento para carregar a versão atual.

Limites desta entrega: 100 itens por orçamento; quantidade máxima de 999.999,999; subtotal e valores em centavos limitados a 1.000.000.000.000. Não há envio por WhatsApp, PDF, assinatura digital, catálogo, baixa de estoque ou emissão fiscal. Decisões em `docs/decisions/0010-etapa-7-orcamentos.md`; resultados e comandos em `docs/etapa-7-verificacao.md`.

## Estoque — Etapa 8

Após entrar, abra **Estoque**. O administrador cadastra produtos com uma única unidade de controle (por exemplo, un, mL ou g), estoque mínimo e exigência de validade. Quantidades têm até três casas decimais; use vírgula ou ponto, sem separador de milhar. O limite por lançamento ou mínimo é 999.999,999. Unidade e exigência de validade ficam preservadas após a primeira movimentação; nome e mínimo continuam editáveis.

Administrador, veterinário e auxiliar cadastram lotes, registram entradas e fazem saídas; recepção consulta. O código do lote é único por produto e fica preservado junto com sua validade. Cadastre o lote e depois registre a entrada; novos recebimentos podem usar o mesmo lote. Uma entrada normal em lote vencido é recusada.

**Registrar saída FEFO** consome os lotes válidos que vencem antes, com lotes sem validade por último. A validade inclui o último dia informado, no fuso `America/Fortaleza`. Se faltar saldo disponível, nenhuma baixa é registrada. A tela separa saldo físico, disponível e vencido; vencidos só saem do físico após ajuste de descarte.

Somente o administrador usa **Ajustar inventário**: quantidade positiva acrescenta; negativa reduz. Informe a diferença, não o saldo final, e um motivo. **Corrigir lançamento** cria um novo ajuste vinculado ao original. O histórico guarda autor, motivo e horário, sem permitir edição ou exclusão. **Arquivar produto** exige saldo físico zero e mantém a consulta do histórico no filtro Arquivados.

Alertas indicam disponível abaixo do mínimo, saldo em lotes que vencem nos próximos 30 dias e vencidos com saldo. São recalculados ao carregar/atualizar a tela. Quando outra operação alterar o produto, uma versão antiga recebe conflito: use **Atualizar produto** e confira o saldo antes de tentar novamente.

Sem medicamentos controlados, compras, múltiplos depósitos, custos financeiros, fiscal, mensagens ou baixa automática por orçamento/vacina. Decisões em `docs/decisions/0011-etapa-8-estoque.md`; resultados e comandos em `docs/etapa-8-verificacao.md`.

## Prontuário em PDF — Etapa 9

No prontuário, abra **Ver exportações em PDF**. Veterinários ativos com CRMV usam **Preparar novo PDF**: selecione um responsável vinculado com CPF e endereço preenchidos; informe endereço, telefone e e-mail profissionais e, quando aplicável, razão social, CNPJ e registro do estabelecimento no CRMV. Confira os dados e confirme a ciência de assinatura e entrega manuais.

O PDF inclui identificação, atendimentos, registros vigentes, pesos, vacinas, prescrições e documentos externos. Versões anteriores aparecem em seção separada, com seus motivos de correção. Rascunhos de IA não aprovados ficam fora. Cada emissão preserva seu próprio arquivo: baixar novamente entrega os mesmos bytes, mesmo após correções posteriores. Prepare uma nova emissão para incluir alterações.

**Baixar PDF e anexos (ZIP)** inclui o PDF, os arquivos originais disponíveis e um manifesto com hashes. Os originais ficam separados e não são convertidos ou mesclados. Documentos registrados apenas como resumo são identificados como sem arquivo original; um resumo não substitui a cópia de um laudo ausente.

Administradores, veterinários e auxiliares baixam cópias existentes; recepção não acessa as exportações. Geração e downloads são auditados. Os arquivos ficam no Storage privado e seus hashes são conferidos antes do download.

**A cópia não possui assinatura digital incorporada.** Conferir identidade/autorização de quem solicita, assinar e obter comprovante de recebimento continuam sendo procedimentos manuais da clínica. O download não registra entrega ao tutor. CPF/CNPJ recebem conferência de formato, sem comprovação de titularidade.

Limites: PDF até 10 MiB e PDF mais anexos até 100 MiB. O sistema recusa excesso sem cortar o histórico. Caracteres indisponíveis na fonte são representados por `[U+XXXX]`. Não há envio por WhatsApp/e-mail, assinatura com certificado, recibo eletrônico ou gestão de pedidos/prazos. Decisões em `docs/decisions/0012-etapa-9-prontuario-pdf.md`; evidências em `docs/etapa-9-verificacao.md`.

## Financeiro básico manual — Etapa 10

Abra **Financeiro** para registrar valores **já recebidos ou pagos**, com descrição, categoria, valor em reais, data financeira e forma de pagamento. Dinheiro, Pix, cartões e transferência são classificações manuais: o sistema não movimenta dinheiro. Tutor e animal são opcionais; se informar ambos, devem estar vinculados no cadastro. Datas futuras não são aceitas.

Administradores registram e consultam recebimentos e despesas, veem os totais completos e fazem estornos. A recepção registra e consulta somente recebimentos e seus totais; não acessa despesas, diferença geral ou estorno. Veterinários e auxiliares não têm acesso ao financeiro nesta etapa. As restrições também são aplicadas pela API e pelo banco.

Use os filtros de período, descrição, categoria, forma, tipo e situação. A tela começa no mês atual; para ver registros antigos, ajuste o período. Os totais consideram todos os resultados filtrados, independentemente da página, e excluem lançamentos estornados. A diferença apresentada **não é lucro contábil nem saldo bancário**.

Lançamentos não são editados nem apagados. Para corrigir, o administrador escolhe **Estornar**, informa o motivo e registra um novo lançamento. O original permanece com sua autoria, e o estorno guarda autor e horário próprios. O estorno corrige os totais da **data financeira original**, mesmo quando registrado depois. Ele é administrativo: uma devolução real deve ser registrada manualmente como despesa.

Orçamentos aprovados não geram lançamentos automaticamente. Não há contas futuras a pagar/receber, parcelamento, conciliação, saldo inicial, abertura/fechamento de caixa, pagamento online ou emissão fiscal. Decisões na [ADR 0013](docs/decisions/0013-etapa-10-financeiro.md); testes, comandos e limites em [Verificação da Etapa 10](docs/etapa-10-verificacao.md).

## Navegação e interface — Etapa 11

Todas as áreas usam o fluxo **lista → tela da ação ou detalhe → Voltar**, dentro da aplicação, sem recarregar a página. O botão **← Voltar** fica ao lado do título. Enquanto a ação está aberta, a tela anterior fica preservada: ao retornar, a busca, os filtros, a página e a posição da lista continuam disponíveis.

Isso vale para cadastros, agenda, prontuário, documentos, PDFs, rascunhos, orçamentos, estoque, financeiro, simulação de mensagens e equipe. A apresentação é compartilhada entre recepção, veterinários, auxiliares e administradores; as ações disponíveis continuam respeitando as permissões de cada papel.

No Financeiro, use **Novo lançamento** ou **Novo recebimento** para abrir o formulário. **Estornar** abre sua própria tela com motivo e confirmação. Em Estoque, é possível abrir um produto e depois uma movimentação; cada Voltar retorna um nível. No prontuário, documentos, histórico de versões, exportações e formulários também seguem esse padrão.

Erros ficam junto da ação e preservam os dados preenchidos. Voltar/cancelar não grava edições. O botão Voltar da ação fica indisponível durante a gravação. A navegação usa o botão do produto; não foram adicionados links diretos ou histórico de ações nos botões Voltar/Avançar do navegador. Sair, recarregar ou trocar de área pelo menu pode iniciar outro contexto.

Menu, cartões, tabelas, botões e formulários compartilham estilos e regras responsivas. A inspeção visual manual da nova interface permanece pendente nesta entrega; comportamento e permissões foram verificados por testes automatizados. Decisões na [ADR 0014](docs/decisions/0014-etapa-11-navegacao-e-interface.md); resultados em [Verificação da Etapa 11](docs/etapa-11-verificacao.md).

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

# Em outro terminal, em backend/, para os lembretes MOCK:
uv run --env-file ../.env --frozen python -m app.worker

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

`npm run setup` gera `.env` e `frontend/.env.local`. Não versionar esses arquivos. A API em execução recebe a conexão restrita, a URL de Auth, a chave publicável e a chave secreta necessária ao Storage privado. A conexão administrativa fica exclusiva dos comandos de configuração/provisionamento. O frontend recebe apenas URL e chave publicável. Os arquivos `.env.example` não contêm credenciais.

## Limitações

O ambiente local continua independente da demonstração hospedada da Etapa 13, que usa HTTPS na Vercel e Supabase remoto. Recuperação de senha, convites, edição de e-mail/senha pela interface e múltiplas clínicas por usuário permanecem fora desta entrega. Não houve contratação de recursos pagos.

Os resultados executados e as limitações de cada etapa estão em `docs/etapa-N-verificacao.md`, incluindo `docs/etapa-9-verificacao.md`. As decisões aprovadas estão em `docs/decisions/`. O aviso de depreciação HTTPX/TestClient continua documentado; os testes passam sem ocultá-lo.

Os commits e o envio ao repositório `JoaoKelvinDev/Clinica-Veterinaria` ficam com o responsável. A relação de arquivos e as instruções para separar as duas entregas estão em `docs/arquivos-por-etapa.md`. A parte financeira empresarial será planejada depois da etapa em andamento, conforme orientação do responsável; não foi implementada nesta entrega.
