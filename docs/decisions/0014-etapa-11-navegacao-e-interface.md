# ADR 0014 — Navegação interna e interface compartilhadas

Data: 2026-11-11. Status: plano global aprovado pelo responsável antes da implementação.

## Contexto

Formulários e detalhes apareciam acima ou abaixo das listas, exigindo procurar o conteúdo. O responsável pediu telas próprias, com Voltar ao lado do título, sem recarregar a página, e o mesmo comportamento e identidade visual em todas as áreas e perfis.

## Decisão

- Adotar o fluxo lista → detalhe/ação → Voltar em tutores, pacientes, agenda, prontuário, documentos, PDFs, rascunhos de IA, orçamento, estoque, financeiro, simulação de mensagens e administração da clínica/equipe.
- Usar o componente compartilhado `Screen.tsx`, sem bibliotecas novas. A tela de origem permanece montada e é ocultada com `hidden` e `inert`; a tela ativa é exibida na área principal por um portal React. Isso preserva filtros, paginação e campos da origem sem duplicar os dados em outro estado.
- Permitir telas aninhadas, como estoque → produto → movimentação ou prontuário → documentos → correção. Apenas a mais profunda fica visível e acessível. Voltar fecha somente a ação atual. Para edição de produto sobre detalhe mantido aberto, usar prioridade explícita.
- Padronizar cabeçalho com título e botão Voltar. Focar o título ao entrar, sem abrir automaticamente o teclado do celular ou selecionar uma ação destrutiva. Restaurar foco e posição da lista ao retornar; respeitar a ausência do elemento original com foco alternativo no título da área. A transição não usa animação de rolagem.
- Bloquear o botão Voltar da ação enquanto sua gravação está em andamento. Os botões de confirmação existentes continuam necessários. Abrir a tela não registra, estorna, arquiva ou aprova automaticamente.
- Mostrar erros e confirmações no contexto ativo. Erros preservam os campos preenchidos. Depois de salvar, manter o destino previsto pelo fluxo: lista atualizada, detalhe atualizado ou revisão concluída, sem recarga completa.
- Manter a identidade do projeto em azul, verde e detalhes em violeta; compartilhar superfícies, cartões, cabeçalhos, botões e tabelas, com menu identificado por ícones e adaptação para telas pequenas. Não introduzir marca ou nome comercial.
- Preservar as regras de permissão: aparência e navegação comuns não concedem novas ações a um papel. A API, os cálculos, a autoria clínica, as aprovações e o isolamento por clínica não mudam.
- Manter a navegação em estado React. Esta etapa não acrescenta URLs individuais, links diretos para registros ou integração do histórico de ações com os botões Voltar/Avançar do navegador. O botão Voltar do produto atende ao fluxo aprovado.

## Consequências

Filtros da lista são preservados inclusive quando o prontuário é aberto pela agenda ou pelos pacientes. Trocar de área pelo menu continua iniciando o contexto daquela área; não há persistência de filtros após recarregar ou sair da sessão.

Voltar/cancelar um formulário não salva suas edições. Isso continua explícito no fluxo de aprovação do rascunho de IA. Downloads de arquivos continuam usando os mecanismos existentes do navegador. O antigo helper de rolagem `reveal.ts` foi substituído pela navegação e pelo foco compartilhados.

O backend, o banco, as dependências e os contratos HTTP permanecem inalterados. A conferência estética e responsiva em navegador real permanece pendente no ambiente de execução, que não disponibilizou navegador à ferramenta de interface. Os testes automatizados verificam a navegação e as permissões observáveis na interface.
