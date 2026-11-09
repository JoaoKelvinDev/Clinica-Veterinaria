# Etapa 7: orçamentos

Data: 2026-11-09.

## Contexto

Após concluir e publicar a Etapa 6, o responsável aprovou analisar a Etapa 7 e depois aprovou seu plano detalhado: itens, quantidades fracionadas, cálculo em centavos, desconto fixo, apresentação manual, decisão comunicada pelo tutor e revisões preservando o original. Cobrança, pagamentos, fiscal, estoque e envio automatizado ficam fora desta entrega.

## Decisão

- Criar o módulo `quotes`, nas camadas existentes de API, schemas, services, repositories e models. Consultar pacientes, tutores e atendimentos pelos seus services. Não ler conteúdo clínico do prontuário para preparar o orçamento.
- Usar `Quote` e `QuoteItem` no schema privado `vetsys`, com UUID, clínica e timestamps. O orçamento exige paciente e tutor ativo vinculado; o atendimento é opcional e deve pertencer ao paciente. Revisões guardam `source_quote_id`.
- Administrador, veterinário e recepção escrevem; auxiliar consulta. Autenticação, situação ativa e clínica são as já existentes. A decisão registrada é a do tutor, informada à equipe, sem aprovação clínica ou login do tutor.
- Itens manuais de serviço/produto, com descrição de até 300 caracteres. Sem catálogo ou vínculo com estoque. Permitir entre 1 e 100 itens, quantidade positiva de até 999.999,999 e três casas decimais, em `numeric(9,3)`/`Decimal`.
- Valores monetários são inteiros em centavos, sem float. Calcular `quantidade × preço unitário`, arredondando cada item com `ROUND_HALF_UP`, somar e subtrair o desconto fixo. O desconto pode igualar o subtotal. Usar `bigint` para centavos, com limite de 1.000.000.000.000 para item/subtotal/preço. A prévia do navegador usa `BigInt`; a API recusa total informado pelo cliente e preços fracionados em centavos.
- O banco gera `line_total_cents` com `round(quantity * unit_price_cents)`. Restrições validam limites e `total = subtotal - desconto`. Na apresentação, o gatilho confere quantidade de itens e soma em relação ao cabeçalho.
- Rascunho é editável. Apresentar registra usuário e horário, atualiza a foto dos nomes dos cadastros e muda a situação para `sent`. Esse evento é manual e não envia mensagens. A partir dele, itens, preços, quantidades, desconto, nomes, validade e vínculos ficam preservados.
- Somente um orçamento enviado e válido recebe aprovação ou recusa. Registrar origem (`in_person`, `phone`, `other`), observação opcional (obrigatória em `other`), usuário e horário. Estados aprovados e recusados são finais e imutáveis.
- Validade opcional por dia em `America/Fortaleza`, inclusive o dia informado. `expired` é derivado de um orçamento `sent` cujo prazo passou, tanto na leitura como nos filtros; não precisa de worker nem altera estados aprovados/recusados. A API e o banco impedem decisão depois do vencimento.
- Para alterar orçamento apresentado/finalizado, criar outro rascunho vinculado ao anterior, copiando itens e desconto. Nomes são obtidos dos cadastros atuais; uma validade vencida é retirada da cópia. A revisão não revoga ou altera automaticamente a decisão anterior.
- Exigir a versão lida pelo cliente nas mutações, incrementando-a em edição e transição. Bloquear o cabeçalho com `FOR UPDATE`; a operação perdedora ou baseada em versão antiga recebe 409. O gatilho de itens também bloqueia o pai para serializar alterações com a apresentação.
- Reforçar clínica e papéis em RLS, com referências compostas. Cabeçalhos não são apagados; itens de rascunho podem ser substituídos na mesma transação. Os gatilhos preservam cabeçalho e itens apresentados inclusive contra alterações administrativas. Identidade, criador, origem de revisão e clínica não têm permissão de atualização pelo papel runtime.
- Guardar criador, último editor, responsável pela apresentação e responsável pela decisão, com horários. Não introduzir auditoria financeira genérica ou reutilizar o log de conteúdo clínico para esta etapa.
- Migração Alembic `9182a5b73863`, após `90a37f9a5549`; API 0.9.0. Sem dependências ou serviços adicionais.

## Consequências

O módulo atende à estimativa de custos e ao histórico apresentado ao tutor. O rascunho não mantém todas as edições intermediárias; guarda versão e último responsável. Não há exclusão/restauração pela interface. Pacientes e tutores arquivados continuam identificáveis nos orçamentos históricos, pelos nomes preservados; novos orçamentos e revisões exigem cadastros e vínculos ativos.

Há busca por nome de paciente/tutor, filtro de situação e paginação. A decisão registrada não emite documento, assinatura digital, cobrança ou pagamento. A Etapa 8 de estoque exige plano e autorização próprios.

## Referências técnicas

- [PostgreSQL: tipos numéricos exatos e arredondamento](https://www.postgresql.org/docs/17/datatype-numeric.html).
- [PostgreSQL: colunas geradas](https://www.postgresql.org/docs/17/ddl-generated-columns.html).
- [Supabase: Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security).
