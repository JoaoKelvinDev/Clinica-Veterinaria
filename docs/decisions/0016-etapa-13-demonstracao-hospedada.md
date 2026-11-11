# ADR 0016 — Demonstração hospedada

Data: 2026-11-11. Status: aprovado e publicado; inspeção visual pendente.

## Contexto

O responsável autorizou publicar a demonstração do código atual para BIBI, MICAELLY e MARIA CAROLLINE usando Vercel e Supabase, escolheu a organização Supabase `jkelvindev` e limitou o custo a US$ 0/mês, sem recursos pagos. O ambiente local e os projetos anteriores devem ser preservados. Commit e push ficam com o responsável; novas ferramentas exigem autorização antes do download.

## Decisão

- Supabase gratuito `vetsys-demo`, referência `qmkjdedkkxzchpqiijsq`, em `sa-east-1`. Migrações Alembic existentes no schema `vetsys`, RLS habilitada e forçada, conexão TLS com papel restrito e pooler em transação, Auth sem cadastro público e Storage privado.
- Dois projetos Vercel na equipe `jkelvin`: `vetsys-demo` entrega a interface Vite/React e `vetsys-demo-api` executa a API FastAPI em `gru1`. A implantação recebe os arquivos locais atuais, incluindo alterações sem commit. Não é criada integração Git nem publicado o `main` remoto desatualizado.
- Endereço das avaliadoras: `https://vetsys-demo.vercel.app`. O encaminhamento `/api` conecta a interface à API. O frontend usa somente configurações públicas; a senha do banco e a chave secreta ficam no backend como segredos.
- Depois dos builds, o responsável aprovou especificamente liberar os dois projetos de produção da exigência de login na Vercel. Previews continuam protegidos. O login Supabase e as permissões do sistema são mantidos. Essa aprovação resolveu a rejeição inicial da revisão automática à alteração SSO.
- Site URL e redirecionamentos do Supabase usam os domínios exatos da interface. Configurações remotas não declaradas são preservadas.
- Contas veterinárias TESTE e dados fictícios; os rascunhos MOCK permanecem pendentes. Nenhum provedor real de IA/WhatsApp, cobrança ou envio de mensagens foi adicionado.

## Consequências

As avaliadoras usam um único link, sem conta na Vercel. O backend funciona como serverless, sem worker contínuo; lembretes dependem do disparo manual MOCK existente. A demonstração limita uploads pela interface a 4 MiB, preservando 10 MiB no ambiente local.

Foram verificados três logins, papéis, acesso clínico, isolamento RLS, PDF/ZIP e arquivos de 4 MiB; um ZIP de aproximadamente 6,4 MB também passou com integridade conferida. Não foi validado o limite local de 100 MiB. Não há navegador disponível para revisão visual desktop/celular. A proteção contra senhas vazadas permanece como aviso do plano gratuito, sem upgrade.

Credenciais individuais são entregues somente pelos arquivos privados ignorados pelo Git. Evidências e limitações detalhadas em [Etapa 13](../etapa-13-demonstracao-status.md). Nenhum commit/push foi executado.
