# Renovação da demonstração — dados detalhados

Executada em 2026-11-12 no Supabase `vetsys-demo`, referência
`qmkjdedkkxzchpqiijsq`, após aprovação explícita do plano. Acesso pelo sistema:
https://vetsys-demo.vercel.app.

## Perfis e acessos preservados

Os quatro perfis da aplicação foram comparados antes e depois: IDs, clínica,
nomes, papéis, situação e CRMVs TESTE permaneceram iguais. Senhas e dados de
login não foram alterados, e nenhuma identidade Auth foi criada ou excluída.

Antes desta execução já havia somente três identidades Auth: administrador,
BIBI e MICAELLY. Um perfil anterior permanecia no cadastro da aplicação, mas sem
identidade de login. O responsável escolheu **manter sem login** e ajustar a
distribuição dos exemplos. Os acessos disponíveis de BIBI e MICAELLY foram
conferidos, incluindo o bloqueio de administração e financeiro.

O arquivo privado de acesso do perfil anterior recebeu aviso de indisponibilidade para
não ser distribuído como login ativo. As informações anteriores foram guardadas
em `.cache/demo-profissional-v1/`; nenhuma credencial foi publicada no repositório.

Após a conferência manual inicial em 12/11/2026, o responsável pediu manter
somente BIBI e MICAELLY na avaliação. O perfil anterior foi desativado pela API,
e seu acesso foi retirado dos materiais privados atuais. As duas avaliadoras
são agora as únicas veterinárias na lista ativa; autoria e vínculos históricos
continuam preservados. A verificação HTTP adicional passou em 18 checagens;
os hashes das linhas clínicas permaneceram iguais. Detalhes em
[Verificação dos perfis](perfis-avaliadoras-verificacao.md).

## Dados antigos

| Item                                    | Resultado                                                              |
| --------------------------------------- | ---------------------------------------------------------------------- |
| 4 tutores e 4 pacientes                 | Arquivados logicamente, fora das listas ativas                         |
| 3 produtos iniciais sem saldo           | Arquivados logicamente                                                 |
| 3 rascunhos MOCK antigos                | Descartados pelo fluxo autorizado do sistema                           |
| Atendimentos antigos de BIBI e MICAELLY | Concluídos pelos respectivos acessos                                   |
| Atendimento do perfil anterior          | Preservado em aberto, com paciente arquivado                           |
| 3 pesos antigos                         | Preservados, com os mesmos IDs                                         |
| 3 documentos e 2 exportações PDF        | Preservados; download autenticado e SHA-256 idênticos à cópia anterior |
| Auditoria                               | Preservada e ampliada pelas novas leituras e operações                 |

Não houve exclusão física de prontuário, documentos, PDFs, movimentações ou
históricos. O atendimento do perfil anterior exige o veterinário responsável para concluir;
essa regra não foi contornada.

## Novo conjunto ativo

| Área                        | Conteúdo                                                                                                                    |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Tutores                     | 6 cadastros fictícios com telefone normalizado, documento sintético, endereço de teste e situação de consentimento simulada |
| Pacientes                   | Amora, Bento, Cacau, Chico, Jade, Lola, Pipoca e Zoe, todos identificados como DEMO                                         |
| Identificação dos pacientes | Espécie, raça, sexo, castração, nascimento, pelagem, identificador de microchip de teste e observações                      |
| Vínculos                    | 8 responsáveis principais e 2 secundários; há tutores com mais de um paciente                                               |
| Agenda                      | 12 agendamentos, 4 por dia em 12, 13 e 14/11/2026, no fuso America/Fortaleza                                                |
| Atendimentos novos          | 3 abertos, distribuídos entre BIBI e MICAELLY                                                                               |
| Pesos novos                 | 8 registros, um por novo paciente                                                                                           |
| Rascunhos                   | 3 exemplos MOCK detalhados para Amora, Bento e Lola, pendentes de revisão                                                   |
| Estoque                     | 8 produtos, 12 lotes, 12 entradas e 2 baixas FEFO, todas fictícias                                                          |
| Alertas de estoque          | 2 produtos abaixo do mínimo e 3 lotes com vencimento próximo                                                                |
| Orçamentos                  | 4 exemplos: rascunho, enviado, aprovado e recusado; decisões explicitamente simuladas                                       |
| Financeiro                  | 6 lançamentos manuais fictícios: 3 recebimentos e 3 despesas já realizados no cenário                                       |

Os rascunhos organizam relatos e dados demonstrativos fornecidos, com incertezas
e campos ausentes indicados. Os campos estruturados de diagnóstico presuntivo,
diagnóstico conclusivo e prescrição ficaram vazios. Foram conferidos **zero
rascunhos aprovados e zero registros clínicos oficiais** no banco.

No financeiro, os recebimentos somam **R$ 600,00**, as despesas **R$ 248,00** e
a diferença é **R$ 352,00**. Todos são valores de demonstração, sem pagamento,
cobrança, transação bancária ou emissão fiscal real. Cálculos e transporte foram
verificados em centavos inteiros.

## Execução e evidências

1. Inventário do projeto e dos acessos; conferência de que os cadastros antigos
   correspondiam aos IDs da carga inicial, sem dados adicionais desconhecidos.
2. Cópia anterior privada em `.cache/demo-profissional-v1/antes.json`, com hash
   conferido após a execução.
3. Validação prévia pelos schemas Pydantic atuais: cadastros, telefones,
   ausência de conflitos de agenda, lotes, quantidades, dinheiro e rascunhos MOCK.
4. Aplicação pela API, mantendo os services, RLS e regras de negócio existentes.
5. Verificação de **39 critérios pela API**, todos aprovados, e **119 operações
   de escrita confirmadas** com IDs salvos para retomada.
6. Download dos cinco arquivos antigos, conferindo tamanho e SHA-256; todos
   coincidiram com os metadados anteriores.
7. Teste de isolamento com `vetsys_app`: novo paciente visível na própria clínica,
   invisível em contexto estrangeiro e sem contexto após encerrar a transação.

Um bloqueio transitório de renomeação de checkpoint no Windows interrompeu a
primeira execução após parte do arquivamento. Os checkpoints e o estado remoto
foram conferidos antes da retomada. O salvamento recebeu tentativas curtas para
esse bloqueio local; operações já concluídas não foram repetidas. A conferência
final não encontrou duplicação dos novos cadastros.

Comandos executados na raiz, usando as ferramentas já instaladas:

```powershell
rtk proxy node .cache/renovar-demo-profissional.mjs plan
rtk proxy backend/.venv/Scripts/python.exe .cache/validar-demo-profissional.py
rtk proxy node --check .cache/renovar-demo-profissional.mjs
rtk proxy node .cache/renovar-demo-profissional.mjs backup
rtk proxy node .cache/renovar-demo-profissional.mjs apply
rtk proxy node .cache/verificar-preservacao-demo.mjs
rtk proxy backend/.venv/Scripts/python.exe .cache/verificar-isolamento-profissional.py
rtk proxy node .cache/finalizar-demo-profissional.mjs
```

Os comandos com rede receberam a autorização de execução fora do sandbox.
Scripts, dados sintéticos, cópia anterior, IDs e resultados detalhados ficam
em `.cache/demo-profissional-v1/` e arquivos auxiliares ignorados pelo Git.
Não repetir scripts de provisionamento antigos: eles não representam esta carga
e podem recriar cadastros arquivados ou o acesso que se decidiu manter ausente.

## Conferência final do banco

- 4 perfis da aplicação e 3 identidades Auth, como no início desta operação.
- Tutores: 6 ativos e 4 arquivados. Pacientes: 8 ativos e 4 arquivados.
- Produtos: 8 ativos e 3 arquivados; 12 lotes e 14 movimentações.
- 12 agendamentos; 6 atendimentos históricos e novos, dos quais 4 abertos.
- 11 pesos: 3 anteriores e 8 novos. Os 3 documentos e 2 PDFs anteriores permanecem.
- 3 rascunhos pendentes e 3 descartados; zero aprovados e zero registros clínicos oficiais.
- 4 orçamentos e 6 lançamentos financeiros; zero mensagens enviadas.
- 22 tabelas de negócio com RLS habilitada e forçada; papel de runtime sem
  superusuário ou bypass de RLS, usando TLS.

O advisor de segurança manteve somente o aviso já existente de proteção contra
senhas vazadas desativada. Não houve alteração de plano ou contratação.
[Detalhes da proteção](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).

## Limites e como conferir

Atualize as listas na aplicação hospedada ou entre novamente como BIBI/MICAELLY.
Na agenda, consulte 12–14/11/2026. No dashboard, o contador de atendimentos abertos
inclui **3 novos e 1 histórico com paciente arquivado**, totalizando 4. O financeiro exige o
acesso administrativo; continua oculto e bloqueado para as veterinárias.

Nenhuma função do produto, dependência, schema, política ou configuração de
hospedagem foi alterada. Por ser uma operação de dados pela API existente,
não foram repetidas as suítes completas de código do frontend/backend; foram
executadas as validações e conferências operacionais descritas acima.

A aparência da interface não foi inspecionada em navegador nesta operação.
O worker contínuo não está hospedado; os lembretes permanecem MOCK e dependem
do disparo manual existente. Esta carga não enviou mensagens nem criou vacinas,
diagnósticos, prescrições ou registros clínicos aprovados.

Não foi feito deploy, commit ou push. O ambiente local e o arquivo
`frontend/.gitignore` criado anteriormente pela ação do usuário/CLI foram preservados.
