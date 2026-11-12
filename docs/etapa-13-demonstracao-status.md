# Etapa 13 — Demonstração Vercel e Supabase

Data: 2026-11-11. Publicação concluída e verificada por HTTP. Inspeção visual em navegador permanece pendente.

## Acesso publicado

Interface: **https://vetsys-demo.vercel.app**. API: https://vetsys-demo-api.vercel.app; domínio usado pelo proxy: https://vetsys-demo-api-jkelvin.vercel.app. As avaliadoras precisam somente do endereço da interface e do login individual do sistema.

Foram criados dois projetos na equipe Vercel `jkelvin`, com as raízes independentes já preparadas: `vetsys-demo` (Vite/React) e `vetsys-demo-api` (FastAPI). Ambos chegaram a `READY`, com Node 22 e sem contratação de recursos pagos. O backend executa em `gru1`. A implantação usou os arquivos locais atuais, incluindo as alterações ainda sem commit das Etapas 12/13; não usou o `main` remoto antigo e não fez commit/push.

- Frontend: projeto `prj_GBulUNqlQj9K7GLXFUAETbZ0QN4Q`, implantação `dpl_3bN9RbbRfkmmgYVJXLqm8AHcSr9M`.
- Backend: projeto `prj_q6L5EJLLPsv343gOz51FOaiUdjee`, implantação `dpl_28tA8S4P2jfyvqfnNy7gZyaRJBGV`.
- `frontend/vercel.json` encaminha `/api/:path*` à API, preservando a autenticação Bearer da aplicação. O frontend recebe somente configuração pública; banco e chave secreta estão apenas no backend, com os valores sensíveis armazenados como segredos na Vercel.
- A conexão Vercel exigiu consentimento específico para a equipe, concluído pelo responsável. A revisão automática inicialmente rejeitou reduzir a proteção SSO. Depois de os dois builds estarem prontos, o responsável autorizou explicitamente liberar a produção dos dois projetos, mantendo previews protegidos. A configuração final é `ssoProtection.deploymentType=preview`; o login Supabase e as permissões da aplicação continuam exigidos.
- Auth do Supabase: `site_url=https://vetsys-demo.vercel.app` e redirecionamentos exatos para os dois aliases da interface. `config diff` foi revisado antes do push; somente essas duas propriedades foram alteradas. A conferência posterior retornou zero diferenças declaradas; as oito propriedades remotas não declaradas foram preservadas.

Os arquivos individuais atuais `.cache/acesso-bibi.txt` e `.cache/acesso-micaelly.txt` contêm o link público e os respectivos acessos hospedados. Em 12/11/2026, o perfil anterior foi desativado e seu arquivo de acesso foi retirado dos materiais atuais, conforme solicitação do responsável. As cópias anteriores foram preservadas em diretórios privados ignorados pelo Git. O manifesto local original e o ambiente `.env` não foram substituídos. Entregar somente o arquivo individual correspondente a cada avaliadora.

Esta página registra a publicação inicial com três contas. A avaliação atual utiliza somente BIBI e MICAELLY; veja a [verificação atual dos perfis](perfis-avaliadoras-verificacao.md).

## Verificação da publicação

Executada contra a interface pública e seu proxy `/api`, sem cookies de acesso da Vercel:

| Verificação                                                | Resultado observado                                                                                    |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| HTML, JavaScript e saúde pelo proxy                        | 200; configuração Auth hospedada e identificação de demonstração presentes                             |
| Ausência de senha do banco e chave secreta no JS publicado | Confirmada                                                                                             |
| Consulta de dados sem login                                | 401                                                                                                    |
| Login e identidade das três contas iniciais                | 200; papel veterinário, CRMV TESTE e clínica esperados                                                 |
| Dashboard e prontuário das três contas                     | 200; financeiro ausente do dashboard                                                                   |
| Administração e financeiro com contas veterinárias         | 403                                                                                                    |
| Administração e financeiro com administrador               | 200                                                                                                    |
| Upload e download de PDF fictício                          | 201/200; bytes idênticos                                                                               |
| Emissão de PDF de demonstração                             | 201; 46.564 bytes, legível em três páginas por `pypdf`                                                 |
| ZIP pequeno                                                | 200; 44.218 bytes, CRC válido, PDF idêntico e anexo presente                                           |
| Dois uploads de 4 MiB, em paciente de verificação separado | 201 para cada arquivo                                                                                  |
| Download de anexo de 4 MiB                                 | 200; SHA-256 idêntico                                                                                  |
| ZIP com os dois anexos de 4 MiB                            | 200; 6.397.579 bytes, CRC e hashes dos anexos conferidos                                               |
| Isolamento RLS pelo papel restrito                         | Paciente visível na própria clínica, invisível em contexto estrangeiro e sem contexto após a transação |
| Configuração serverless                                    | Seis testes passaram novamente                                                                         |
| Build de demonstração e formatação frontend                | Passaram novamente; builds remotos também concluídos                                                   |
| Auditoria npm de produção                                  | Zero vulnerabilidades retornadas por `npm audit --omit=dev --json`                                     |
| Logs de erro/fatal da API                                  | Nenhum registro encontrado nas janelas de verificação consultadas                                      |

A primeira tentativa de exportação retornou 422 porque o responsável fictício não possuía documento/endereço. O cadastro demonstrativo foi completado com o mesmo CPF fictício usado nos testes e endereço explicitamente fictício, e a emissão passou. Nenhuma regra foi relaxada. Os rascunhos MOCK não foram aprovados. Os testes acrescentaram um documento fictício e uma exportação ao primeiro paciente, além de um tutor/paciente identificado como verificação de limites, dois documentos grandes e sua exportação.

Evidências e scripts de verificação ficam em `.cache/vercel-public-verificacao.json`, `vercel-isolamento-verificacao.json`, `vercel-limites-verificacao.json`, `vercel-arquivos-verificacao.json` e nos scripts correspondentes. Os pacotes de origem foram montados por lista permitida, com conferência de ausência dos segredos antes do envio. Nenhuma ferramenta nova foi instalada.

O comando `uv run --frozen pytest tests/test_serverless.py` encontrou bloqueio de gravação no cache global do uv; a mesma verificação foi executada com o Python do ambiente virtual já existente e passou. Os comandos com rede precisaram da execução autorizada fora do sandbox. A auditoria completa informada pelo build remoto apontou dez alertas moderados; a consulta de produção acima retornou zero. Não foram atualizadas dependências durante a publicação.

## Autorizações e configuração

O responsável autorizou preparar e publicar uma demonstração na Vercel e no Supabase, com dados fictícios e contas de avaliação no papel de veterinário, com CRMVs explicitamente TESTE. Escolheu a organização `jkelvindev` e confirmou o custo informado de **US$ 0/mês**, sem contratar recursos pagos. Downloads de ferramentas novas dependem de autorização; nenhuma foi instalada nesta preparação.

Foi criado o projeto Supabase `vetsys-demo`, referência `qmkjdedkkxzchpqiijsq`, região `sa-east-1`, no plano gratuito. Os projetos anteriores da organização e a instância local foram preservados. A CLI já instalada foi vinculada somente em `.cache/vetsys-demo`, separada da configuração de desenvolvimento.

## Supabase preparado e verificado

- Schema gerado pelas migrações Alembic existentes, em modo offline, e aplicado no projeto novo. O Alembic permanece como único histórico da aplicação: revisão `e4b9de0589fe`, 22 tabelas de negócio e 55 políticas. RLS habilitada e forçada em todas as tabelas de negócio.
- Papel `vetsys_app` com login e senha aleatória privada; sem superusuário, bypass de RLS ou herança. Conexão pelo pooler em modo transação, TLS obrigatório, prepared statements desativados no cliente serverless.
- Cadastro público e login anônimo bloqueados; senha mínima de 12 caracteres. Alterações revisadas com `config diff` e limitadas ao projeto novo. A exigência TLS também foi ativada no banco.
- Bucket `vetsys-documents` privado, para PDF/JPG/PNG, mantendo o limite de armazenamento de 10 MiB. O navegador continua acessando anexos através da API autenticada.
- Inicialmente, administrador da demonstração e três contas de veterinário, sem envio de e-mails. Os CRMVs de avaliação são explicitamente TESTE e não representam registros profissionais. Atualmente somente BIBI e MICAELLY são veterinárias ativas.
- Uma clínica explicitamente fictícia, três tutores fictícios, pacientes Luna/Nina/Thor (DEMO), um atendimento e um peso para cada paciente, três rascunhos MOCK pendentes e três produtos demonstrativos. Os rascunhos não foram aprovados nem convertidos em registros oficiais.
- Os três logins foram verificados com Supabase Auth hospedado e uma API temporária em `127.0.0.1:8001`, conectada ao banco remoto com o papel restrito. Leitura de prontuário e ausência de dados financeiros no dashboard também foram verificadas. Isso ainda não comprova uma publicação funcional na Vercel.

As credenciais e os scripts de preparação estão exclusivamente em `.cache`, ignorado pelo Git. O ambiente local `.env` não foi substituído. As contas hospedadas reutilizam os logins/senhas individuais aprovados para as avaliadoras, com novos identificadores Auth próprios do projeto hospedado.

O advisor de segurança não apontou problemas de RLS, mas retornou o aviso `auth_leaked_password_protection`. A proteção contra senhas vazadas depende do plano Pro ou superior; não foi contratado upgrade. As senhas provisionadas são aleatórias e o cadastro público está bloqueado. [Documentação e remediação](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).

## Preparação no código

- `backend/app/core/config.py`, `db.py` e `app/main.py`: modo serverless ativado apenas com `VERCEL=1`, pool de uma conexão, sem overflow, TLS e configuração compatível com o pooler. O modo local mantém a configuração anterior.
- `backend/vercel.json`: FastAPI, região `gru1`, duração máxima de 60 segundos.
- `backend/.vercelignore` e `frontend/.vercelignore`: exclusão de arquivos locais e credenciais do pacote de implantação.
- `frontend/src/environment.ts`, `records-api.ts`, `PatientDocuments.tsx`, `App.tsx` e estilos: modo `VITE_DEMO_MODE=true`, identificação de ambiente fictício e limite de anexos de 4 MiB na interface, reservando espaço ao multipart. O modo local mantém 10 MiB.
- Testes de configuração serverless e ambiente da demonstração.

## Verificações desta preparação

- Backend: 379 testes passaram; Ruff check e formatação passaram em 136 arquivos; mypy passou nos mesmos 136 arquivos. Permanece o aviso conhecido de depreciação HTTPX/TestClient.
- Frontend: 131 testes passaram em 15 arquivos, com dois workers; build com TypeScript, ESLint e Prettier passaram. O bundle JS de 585,16 kB continua acima do aviso informativo de 500 kB.
- Build separado com `VITE_DEMO_MODE=true` e a configuração pública do Supabase hospedado passou. O pacote contém a URL Auth correta e a identificação de demonstração; foi conferida a ausência da chave secreta e da senha do banco no JavaScript gerado.
- Supabase remoto: revisão, contagem de tabelas/políticas, RLS forçada, configuração Auth/TLS, três logins, leitura clínica, rascunhos pendentes e Storage privado conferidos.

## Limites e pendências restantes

- O inventário atual de Computer Use retornou `apps=[]` e `browsers=[]`. Não foi realizada inspeção visual em desktop/celular nem interação com a interface em navegador real. A verificação acima é HTTP, autenticação, dados e arquivos; não comprova aparência responsiva.
- A interface limita uploads a 4 MiB; o ambiente local mantém 10 MiB. Downloads de 4 MiB e ZIP de aproximadamente 6,4 MB passaram neste runtime. Não foi validado todo o limite local de pacotes de 100 MiB, nem se promete equivalência entre limites de upload e resposta da plataforma. [Limites da hospedagem](https://vercel.com/docs/errors/function_payload_too_large).
- O worker contínuo Docker não foi implantado. Lembretes MOCK dependem do disparo manual já existente; não há envio real de WhatsApp ou IA real.
- A proteção contra senhas vazadas continua como único aviso do advisor de segurança; nenhum upgrade foi contratado. RLS habilitada e forçada foi reconferida nas 22 tabelas de negócio.
- Os testes completos de backend/frontend listados na preparação não foram repetidos nesta retomada: a alteração de produto desta sessão foi o arquivo de proxy `frontend/vercel.json`. Foram executadas as verificações de publicação descritas acima.

A demonstração está disponível no link público. Permanecem a conferência visual e as limitações explicitadas; não houve avanço para outra etapa, commit ou push.
