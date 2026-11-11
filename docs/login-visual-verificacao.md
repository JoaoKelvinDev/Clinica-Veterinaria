# Nova tela de entrada — verificação

Data: 2026-11-11. Implementada localmente após aprovação explícita do plano e
confirmação de que a mudança abrange somente o visual inicial de login.

## Implementação

- `frontend/src/LoginScreen.tsx`: apresentação de entrada, recuperação de sessão
  e acesso indisponível; formulário integrado ao fluxo existente e controle de
  mostrar/ocultar senha com rótulo acessível.
- `frontend/src/login-screen.css`: cores, fontes, layout, ilustração, foco e
  animações limitados à `.login-screen`; imagem lateral no desktop e faixa de
  imagem no celular. Inclui regra para movimento reduzido e larguras pequenas.
- `frontend/src/assets/`: foto original da referência, fontes locais Nunito e
  Fraunces, licenças e registro das origens. Não depende de requisição do navegador
  ao Google Fonts ou ao Lovable.
- `frontend/src/App.tsx`: substituição somente da apresentação anterior à entrada
  no sistema. Funções de autenticação, sessão e telas internas foram preservadas.
- `frontend/src/Authentication.test.tsx` e `LoginScreen.test.tsx`: cobertura dos
  comportamentos da nova entrada e regressões de autenticação.
- ADR 0017 e README: decisões, instruções e limites da entrega.

Referência visual: repositório `JoaoKelvinDev/pawprint-clinic-welcome`, commit
`5b93d996cec2771700449bc22929edd12189a238`. Não foram trazidos TanStack Start,
Tailwind, Lucide ou os componentes não usados do protótipo. Nenhuma dependência
foi instalada e nenhum arquivo de configuração de pacotes foi alterado.

## Comandos e resultados executados

Em `frontend/`:

| Comando | Resultado |
|---|---|
| `rtk proxy npm.cmd test -- --maxWorkers=2` | 137 testes passaram em 16 arquivos |
| `rtk proxy npm.cmd test -- src/Authentication.test.tsx --maxWorkers=2` | 11 testes passaram após ajuste final de tipagem do mock |
| `rtk proxy npm.cmd run lint` | Passou, sem avisos |
| `rtk proxy npm.cmd run format:check` | Passou |
| `rtk proxy npm.cmd run typecheck` | Passou |
| `rtk proxy npm.cmd run build` | Passou; imagem e fontes locais emitidas em `dist/assets` |

A primeira checagem de tipos identificou a assinatura estreita do mock
`subscribe` no teste de expiração. O mock foi tipado com `AuthGateway['subscribe']`;
a checagem de tipos, o build e os testes de autenticação passaram após a correção.

O bundle JavaScript ficou em 590,26 kB (159,85 kB gzip). Permanece o aviso
informativo acima de 500 kB. Imagem: 165.178 bytes; Nunito: 276.932 bytes;
Fraunces: 360.440 bytes. Assinaturas dos arquivos e licenças foram conferidas no
download, com hashes registrados em `.cache/login-assets-verificacao.json`.

## Comportamentos verificados automaticamente

- Credenciais são enviadas pelo fluxo existente, e o sucesso abre o dashboard.
- Erros de credenciais aparecem sem liberar os dados da clínica.
- Mostrar/ocultar senha preserva o valor e não submete o formulário.
- Campos e envio ficam desativados durante a autenticação.
- Recuperação de sessão existente não exige nova digitação de credenciais.
- Expiração retorna à entrada sem manter os dados da clínica ou a senha.
- Usuário bloqueado pode encerrar a sessão e retornar ao formulário.
- Configuração Auth ausente desativa o envio e mostra orientação.
- A demonstração informa dados fictícios e serviços simulados antes do login.
- Testes existentes de navegação e permissões continuam passando.

Os testes de autenticação usam `AuthGateway` e HTTP simulados. Não foi realizado
novo login com credenciais hospedadas nesta entrega, pois não há mudança no
provedor nem publicação da nova tela.

## Como conferir localmente

Com o ambiente local habitual iniciado, abra `http://localhost:5173` sem uma
sessão ativa. Se já estiver autenticado, use **Sair** para visualizar a entrada.
O comando habitual na raiz continua sendo `rtk proxy npm.cmd run dev`.

Confira a entrada no desktop e no celular, a navegação por teclado, o controle
de senha e o login de uma conta fictícia. Após entrar, os módulos devem manter
o visual e o comportamento anteriores.

## Limites e pendências

- O inventário Computer Use retornou `apps=[]` e `browsers=[]`. Não foi possível
  conferir a aparência renderizada, o layout responsivo ou a navegação real de
  teclado em navegador. Regras CSS implementadas não equivalem a validação visual.
- A leitura visual do arquivo de imagem original foi realizada, sem edição.
- Backend, banco, permissões, telas internas e configuração Auth foram preservados.
  Não foram executados testes de backend, pois nenhum arquivo dele foi alterado.
- A nova versão ainda não foi publicada na Vercel. O link hospedado continua
  atendendo a versão anterior até autorização específica para publicar a mudança.
- Nenhum commit, push, alteração no repositório Lovable ou contratação foi feito.

Não houve ampliação do plano aprovado. A revisão visual permanece pendente pela
indisponibilidade do navegador.
