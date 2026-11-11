# Verificação da Etapa 11

Data: 2026-11-11, `America/Sao_Paulo`. Plano global aprovado antes da implementação. Continuação após interrupção da sessão, preservando as alterações já realizadas. Decisões na [ADR 0014](decisions/0014-etapa-11-navegacao-e-interface.md).

## Entrega e arquivos

- `frontend/src/Screen.tsx`: telas de ação, cabeçalho/Voltar, mensagens do contexto ativo, retorno à origem e telas aninhadas. Mantém a origem montada, oculta e inerte enquanto outra tela está ativa.
- `frontend/src/screen-focus.ts`: foco no título ao abrir uma área. `reveal.ts` removido após substituição de seus usos.
- `App.tsx`: navegação comum, ícones, edição da clínica em tela própria e preservação da agenda/lista de pacientes enquanto o prontuário está aberto.
- `Tutors.tsx`, `Patients.tsx`, `PatientTutors.tsx`: cadastro, edição, arquivamento e vínculos em telas próprias.
- `Scheduling.tsx`: formulários e confirmações da agenda.
- `Records.tsx`, `PatientDocuments.tsx`, `RecordExports.tsx`, `AiScribe.tsx`: prontuário, registros, pesos, vacinas, versões, documentos, PDFs e rascunhos, com retorno por etapa.
- `Inventory.tsx` e `Quotes.tsx`: detalhes, cadastros, movimentações, revisões e decisões com o mesmo padrão.
- `Financial.tsx`: novo lançamento e estorno em telas próprias; fechamento após gravação e preservação dos filtros da lista.
- `Messaging.tsx`: simulação de resposta em tela própria; envio e histórico existentes preservados.
- `UserAdministration.tsx`: edição de usuário com o mesmo cabeçalho e retorno.
- `styles.css`: menu, ícones, cartões, formulários, tabelas, totais financeiros e regras responsivas compartilhados; `hidden` prevalece sobre as regras de layout.
- `Screen.test.tsx`, testes dos módulos afetados e `test/setup.ts`: novas verificações de navegação e adaptação dos caminhos de abertura. O ambiente jsdom simula `scrollTo`, sem navegador real.
- README, AGENTS.md, ADR 0014 e este relatório.

Não foram adicionadas dependências, serviços, migrações ou variáveis de ambiente. Nenhum arquivo do backend foi alterado.

## Verificações

| Verificação | Resultado |
|---|---|
| Vitest completo com `--maxWorkers=2` | 116 testes passaram em treze arquivos |
| ESLint | passou, sem avisos |
| Prettier | passou |
| TypeScript | passou, também executado pelo build |
| Build Vite | passou; JS de 576,99 kB, acima do limite informativo de 500 kB |
| Inicialização local | aplicação reconstruída e iniciada com Supabase local; containers da aplicação saudáveis |
| Conferência HTTP local | 4/4 passaram: página inicial, saúde da API e módulos atualizados de navegação/documentos |
| Navegador real / screenshots | não executado: a ferramenta retornou `No browser is available` |
| Backend e banco | sem alteração; a suíte backend não foi repetida nesta etapa |

Uma execução com o paralelismo padrão, durante carga elevada no computador, terminou com dois timeouts de 5 segundos nos fluxos de cadastro de orçamento e financeiro, sem falha de asserção. A execução com dois workers foi utilizada para a verificação completa, sem alterar limites de timeout ou dependências.

Os novos testes exercitam tela exclusiva mantendo a origem montada, campos preservados, retorno por nível, foco, posição da lista, erro contextual, bloqueio de Voltar durante gravação, descarte de telas ao trocar o contexto e prioridade da edição de produto. As integrações verificam também clínica/equipe, produto/movimentação, versões de documento e abertura/retorno do prontuário pelos quatro papéis.

O teste do retorno do prontuário para os quatro papéis usa uma resposta de erro fictícia para confirmar que o usuário consegue voltar à mesma lista e busca mesmo quando a leitura falha. Os testes anteriores do prontuário continuam cobrindo leitura, correção e restrições de conteúdo.

Os testes adaptados de financeiro, documentos e mensagens abrem a tela pelo novo botão antes de preencher os campos. Testes anteriores de gravação, falhas, confirmações, valores exatos e permissões continuam executados.

## Executar e conferir

Na raiz, com Docker Desktop iniciado:

```powershell
npm run dev
```

Em `frontend/`:

```powershell
npm test -- --maxWorkers=2
npm run lint
npm run format:check
npm run typecheck
npm run build
```

Abra `http://localhost:5173` e confira:

1. Financeiro → Novo lançamento ou Estornar: somente o conteúdo da ação deve aparecer na área principal, com Voltar ao lado do título.
2. Estoque → produto → movimentação: cada Voltar retorna um nível; a busca e a página da lista ficam preservadas.
3. Animais → prontuário → documentos → correção: o retorno percorre as mesmas etapas sem recarregar a aplicação.
4. Cadastros, agenda, orçamento, equipe, rascunhos e PDFs: confira o mesmo cabeçalho e comportamento.
5. Recepção, veterinário, auxiliar e administrador: os controles disponíveis variam conforme as permissões anteriores, mantendo a mesma apresentação.
6. Em tela estreita, confira legibilidade, campos, navegação horizontal e tabelas com rolagem, sem sobreposição do botão Voltar.

## Limitações e pendências

- A conferência visual em navegador real, tanto desktop quanto celular, permanece pendente. CSS responsivo e comportamento foram implementados, mas não são apresentados como visualmente validados.
- As ações usam o botão Voltar da aplicação. Não foram adicionadas URLs próprias, links diretos ou integração com o histórico Voltar/Avançar do navegador.
- A preservação de filtros vale para abrir e voltar dentro do contexto montado. Recarregar, sair ou trocar de área pelo menu pode iniciar outro contexto.
- Voltar/cancelar não grava alterações do formulário. O fluxo de confirmação clínica e as confirmações administrativas continuam necessários.
- O aviso de tamanho do bundle permanece; não houve mudança de dependências para suprimi-lo.
- Não houve commit, push, publicação, deploy, criação de projeto hospedado ou nova integração externa.

O plano foi implementado no frontend, sem ampliação das regras de negócio. A pendência de inspeção visual está registrada para revisão humana.
