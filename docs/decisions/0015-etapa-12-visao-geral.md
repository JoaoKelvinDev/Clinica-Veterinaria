# ADR 0015 — Visão geral da clínica

Data: 2026-11-11. Status: plano aprovado pelo responsável antes da implementação.

## Contexto

Após a padronização de navegação da Etapa 11, foi aprovada uma tela inicial que reúna os sinais da rotina e permita abrir as áreas existentes. Os resumos precisam considerar todos os registros da clínica, preservando as permissões anteriores.

## Decisão

- Adicionar **Visão geral** ao menu e torná-la a tela inicial após entrar. Agenda continua acessível pelo menu e pelo cartão. Os atalhos usam o estado React e o foco compartilhado da Etapa 11, sem recarregar a página.
- Expor `GET /dashboard`, autenticado e com `Cache-Control: no-store`. O módulo agrega respostas dos services de agenda, mensagens, estoque e financeiro; cada módulo mantém suas consultas e schemas. Nenhuma tabela de outro módulo é consultada diretamente pelo dashboard.
- Reutilizar `ConsistentAuthContext`: uma transação `REPEATABLE READ` reúne os resumos. Calcular uma única referência de tempo, com dia e mês em `America/Fortaleza`, e informar o instante de geração. Uma gravação concorrente aparecerá na próxima leitura completa.
- Agenda: contar todos os agendamentos que intersectam o dia, por situação, com a mesma regra da agenda existente. Contar separadamente todos os atendimentos ainda em aberto, inclusive de dias anteriores, deixando isso explícito na tela.
- Comunicação: contar mensagens marcadas como necessitando atenção e ainda não resolvidas. A contagem não usa o limite de 50 itens da lista. O modo MOCK permanece explícito; consultar o painel não processa lembretes nem envia mensagens.
- Estoque: contar produtos ativos cujo saldo disponível está abaixo do mínimo. Lotes vencidos e a vencer precisam ter saldo positivo; a janela de vencimento inclui hoje e o trigésimo dia. Manter as mesmas regras da lista de estoque, em consulta agregada sem paginação.
- Financeiro: considerar o mês civil corrente e somente lançamentos vigentes, excluindo estornados na data financeira original. Administrador recebe recebimentos, despesas e diferença; recepção recebe somente recebimentos, com os outros campos nulos. Veterinários e auxiliares recebem `financial: null`, sem executar a consulta financeira. Centavos agregados continuam como strings inteiras, formatadas com `BigInt` na interface.
- Manter isolamento nos repositories e RLS existentes. O retorno contém contagens, período e totais autorizados, sem nomes de tutores/pacientes, telefones ou conteúdo clínico.
- Carregar ao abrir a tela e oferecer atualização manual. Mostrar carregamento, erro e ausência de registros de forma distinta. Uma atualização com falha remove os totais anteriores; uma resposta atrasada de outra sessão é ignorada.

## Consequências

Não há novas dependências, tabelas, migrações, credenciais ou integrações. A versão da API passa para `0.13.0`. Não há gravação, aprovação, estorno ou envio a partir dos cartões. Os atalhos abrem a área correspondente; filtros específicos e relatórios exportáveis permanecem fora desta etapa.

O painel não tem atualização automática em tempo real. A diferença financeira não representa lucro contábil nem saldo bancário. Atendimentos em aberto podem incluir pendências antigas, conforme indicado na interface.

Testes cobrem os quatro papéis, isolamento, volumes superiores às páginas, limites de dia/mês, estornos, ausência de efeitos colaterais e leitura consistente durante gravação concorrente. A conferência estética em navegador real permanece pendente porque a ferramenta não disponibilizou navegador. Evidências em [Verificação da Etapa 12](../etapa-12-verificacao.md).
