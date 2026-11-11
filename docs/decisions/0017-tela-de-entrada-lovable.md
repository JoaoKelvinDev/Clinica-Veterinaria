# ADR 0017 — Tela de entrada baseada na referência Lovable

Data: 2026-11-11. Status: aprovado e implementado localmente; revisão visual e publicação pendentes.

## Contexto

O responsável desenvolveu a interface de entrada no repositório
[pawprint-clinic-welcome](https://github.com/JoaoKelvinDev/pawprint-clinic-welcome)
e aprovou sua adaptação exclusivamente à tela inicial de login. O desenho de
referência usa React, TanStack Start, Tailwind, ícones Lucide e um formulário
simulado que sempre retorna erro.

## Decisão

- Usar o layout, a foto original, os tons verde/creme, as fontes Nunito/Fraunces
  e o controle de mostrar/ocultar senha como referência da nova entrada.
- Adaptar a apresentação para React/Vite e CSS isolado, sem novas dependências.
  O componente `LoginScreen` recebe o estado e o envio do fluxo existente de `App`.
- Preservar `AuthGateway`, autenticação Supabase, recuperação/expiração de sessão,
  entrada no dashboard, saída da sessão e bloqueio de usuários sem acesso.
- Limitar todos os seletores da nova folha à classe `.login-screen`; fontes e
  animações têm nomes próprios. Os estilos e componentes das telas internas
  permanecem como estavam.
- Usar o nome provisório Sistema Veterinário. Cartões decorativos descrevem
  funcionalidades, sem pacientes, horários, estatísticas ou suporte inventados.
  O modo demonstrativo é identificado antes do login. O status continua vindo
  de `/api/health`, que verifica somente a disponibilidade da API.
- Manter a persistência de sessão atual. Recuperação de senha e controle
  adicional de persistência por checkbox ficam fora desta mudança.
- Servir imagem e fontes pela aplicação; preservar as licenças SIL OFL 1.1
  das fontes. A origem dos recursos está em `frontend/src/assets/README.md`.

## Consequências

O formulário usa a autenticação existente e não contém o temporizador simulado
da referência. Não houve alteração de backend, banco, permissões, dependências
ou configuração da hospedagem. O projeto original do Lovable não foi modificado.

Os recursos locais acrescentam aproximadamente 803 kB de imagem e fontes antes
da compressão de transporte. O build continua apresentando o aviso informativo
de JavaScript acima de 500 kB, já existente antes desta alteração.

Os testes e checks estão em [Verificação da tela de entrada](../login-visual-verificacao.md).
Sem navegador disponível na sessão, aparência e responsividade ainda exigem
conferência visual. A nova tela não foi publicada, e nenhum commit/push foi feito.
