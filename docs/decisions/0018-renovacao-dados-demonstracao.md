# ADR 0018 — Renovação dos dados de demonstração

Data: 2026-11-12. Status: aprovado e executado no Supabase hospedado.

## Contexto

O responsável pediu substituir os exemplos iniciais por dados fictícios mais
detalhados, preservando os perfis. Aprovou arquivar os cadastros antigos e criar
6 tutores, 8 pacientes, 12 agendamentos, 3 atendimentos, pesos, 3 rascunhos MOCK
pendentes, 4 orçamentos, 8 produtos com lotes/alertas e 6 lançamentos financeiros.

Antes da execução foram encontrados quatro perfis no sistema e três identidades
no Supabase Auth. O perfil MARIA CAROLLINE estava sem identidade de login. O
responsável escolheu explicitamente manter esse estado e redistribuir os
exemplos entre BIBI e MICAELLY.

## Decisão

- Executar somente no projeto Supabase `vetsys-demo`, referência
  `qmkjdedkkxzchpqiijsq`, pela API hospedada e pelas regras atuais dos módulos.
  Sem mudanças de schema, permissões, provedores, senhas ou papéis.
- Arquivar logicamente os 4 tutores, 4 pacientes e 3 produtos iniciais. Descartar
  os 3 rascunhos antigos e concluir os atendimentos antigos cujos responsáveis
  possuem acesso disponível.
- Preservar documentos, exportações, pesos, auditoria e histórico. Não apagar
  fisicamente registros nem contornar as regras append-only.
- Preservar o atendimento antigo de Maria em aberto: sua conclusão exige o
  veterinário responsável. Não impersonar o perfil nem alterar a autorização.
- Marcar todos os novos exemplos como DEMO/fictícios. Telefones, documentos,
  endereços, identificadores e valores são sintéticos. Consentimentos existentes
  na carga são explicitamente simulações para o provedor MOCK.
- Criar apenas rascunhos clínicos pendentes; campos de diagnóstico e prescrição
  permanecem vazios. Nenhum registro clínico oficial ou aprovação automática.
- Salvar cópia anterior e checkpoints privados por operação em `.cache`, com
  resultado confirmado e IDs para retomada sem duplicar dados.

## Consequências

As listas ativas mostram o novo conjunto, e os históricos antigos continuam
preservados. Há 3 novos atendimentos abertos e 1 antigo de Maria, totalizando
4 no dashboard. Somente BIBI e MICAELLY têm login de avaliadora disponível;
o perfil de Maria continua no sistema, sem restauração do Auth.

A alteração dos dados é visível no sistema hospedado ao atualizar as listas;
não depende de uma nova implantação. Não foi alterado o banco local, não houve
envio real de mensagem, contratação, commit, push ou deploy.

Resultados e limitações em [Verificação da demonstração profissional](../demo-profissional-verificacao.md).
