# Verificação dos acessos BIBI e MICAELLY

Data: 2026-11-12. Solicitação: testar os acessos e as permissões existentes no
sistema publicado. Verificação por HTTP em `https://vetsys-demo.vercel.app`,
com autenticação no Supabase `qmkjdedkkxzchpqiijsq`.

## Resultado

As 85 checagens de identidade, respostas HTTP, leitura, filtros e bloqueios
passaram. Foram usados os acessos privados já provisionados, sem troca de
senha, criação de conta ou alteração de permissões.

| Perfil   | Login                | Papel                               | Agendamentos em 12–14/11/2026 | Novos atendimentos abertos |
| -------- | -------------------- | ----------------------------------- | ----------------------------- | -------------------------- |
| BIBI     | Verificado, HTTP 200 | Veterinário, CRMV TESTE-BIBI/PI     | 7                             | 2                          |
| MICAELLY | Verificado, HTTP 200 | Veterinário, CRMV TESTE-MICAELLY/PI | 5                             | 1                          |

Para cada conta foram conferidos:

- Identidade Auth, perfil ativo, clínica esperada e CRMV TESTE.
- Acesso ao dashboard com financeiro ausente.
- Leitura dos 8 pacientes, 6 tutores, 8 produtos e 4 orçamentos demonstrativos.
- Leitura do prontuário, peso e rascunho MOCK pendente do paciente do cenário.
- Filtros de agenda e atendimentos por veterinário em 12, 13 e 14/11/2026.
- Bloqueio HTTP 403 para lista e detalhe de usuários.
- Bloqueio HTTP 403 para lista e detalhe de lançamentos financeiros.

Sem autenticação, `/api/me` retornou HTTP 401. A página pública respondeu HTTP 200. As respostas testadas vieram do proxy `/api` do domínio publicado.

## Preservação e limites

Nenhum cadastro, atendimento, orçamento, estoque, lançamento ou perfil foi
alterado pelo teste. Não foram aprovados rascunhos. Leituras de prontuário
geram a auditoria normal do sistema, e os logins atualizam a atividade de Auth.

A conferência posterior no banco confirmou 4 perfis, 3 identidades Auth,
8 pacientes ativos, 12 agendamentos, 3 rascunhos pendentes, zero aprovados,
zero registros clínicos oficiais e 6 lançamentos financeiros. Maria continua
sem identidade de login, como decidido anteriormente; não foi testado ou
restaurado o acesso dela.

Não foram tentadas ações de escrita para testar bloqueios, nem fluxos de
aprovação clínica, logout ou renovação de sessão. A verificação comprova os
acessos de leitura e os bloqueios listados acima.

O inventário Computer Use retornou `apps=[]` e `browsers=[]`. Não houve clique,
preenchimento ou inspeção visual em navegador real. A aparência, a navegação
por telas e a responsividade permanecem pendentes de conferência visual.

## Evidência e reprodução

Script privado ignorado pelo Git:

```powershell
rtk proxy node --check .cache/testar-perfis-avaliadoras.mjs
rtk proxy node .cache/testar-perfis-avaliadoras.mjs
```

Resultado detalhado em `.cache/teste-perfis-2026-11-12/resultado.json`.
O script lê as credenciais dos arquivos privados existentes e não as imprime.
Não foram instaladas ferramentas, alterado código do produto ou feito deploy,
commit ou push.
