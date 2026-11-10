# Verificação da Etapa 9

Data: 2026-11-10, `America/Sao_Paulo`. Windows, Python 3.12, Docker Desktop e Supabase exclusivamente local. Plano detalhado aprovado antes da implementação. Todos os exemplos e dados de teste são fictícios. Decisões na [ADR 0012](decisions/0012-etapa-9-prontuario-pdf.md).

## Entregas e arquivos

- `backend/app/modules/records/export_api.py`, `export_models.py`, `export_repository.py`, `export_schemas.py`, `exports.py`, `pdf.py`: geração, preservação, listagem, download PDF/ZIP, validação e conferência de integridade.
- `records/services.py` e `repositories.py`: coleta de todas as versões do paciente para exportação, preservando a leitura habitual das versões vigentes.
- `patients/services.py`: consulta dos responsáveis vinculados para emissão, incluindo paciente arquivado.
- `core/dependencies.py`: autenticação compartilhada com transação consistente na geração; as demais rotas preservam o comportamento anterior.
- `app/main.py`: rotas e versão 0.11.0.
- `migrations/env.py` e `versions/7373a052b884_add_immutable_medical_record_exports.py`: tabela append-only, índices, referências, RLS e proteção contra alterações.
- `backend/pyproject.toml` e `uv.lock`: ReportLab 5.1.0, pypdf 7.0.1 para desenvolvimento e dependências transitivas resolvidas.
- `tests/test_record_exports.py`, `conftest.py`, `test_migrations.py`: regras, conteúdo, arquivos, permissões, isolamento, concorrência e reversibilidade.
- `frontend/src/RecordExports.tsx`, `record-exports-api.ts`, `RecordExports.test.tsx`, integração em `Records.tsx` e estilos em `styles.css`.
- README, seção 11 e Etapa 9 no AGENTS.md, ADR 0012 e este relatório.

## Verificações executadas

| Verificação | Resultado real |
|---|---|
| pytest completo, `vetsys_test` | 300 passaram; um aviso de depreciação HTTPX/TestClient existente |
| Ruff lint e formatação | passaram; 122 arquivos |
| mypy | passou; 122 arquivos |
| Vitest | 82 passaram, em onze arquivos |
| ESLint, Prettier e TypeScript | passaram |
| Build frontend | passou; JS de 557,38 kB, com aviso informativo acima de 500 kB |
| Migração upgrade/downgrade/upgrade | passou no banco temporário dentro do pytest; 21 tabelas de negócio com RLS e 53 políticas |
| Inicialização local | Docker Desktop, Supabase e aplicação iniciados; API, frontend e worker passaram nos healthchecks |
| Supabase advisors local, todos os tipos, nível warn | nenhum problema encontrado |
| Fluxo com Auth real local pelo proxy frontend | 16/16 verificações passaram |
| Inspeção adicional do PDF e ZIP do fluxo real | 5/5 verificações passaram |
| Renderização visual dos exemplos | três PDFs, 13 páginas, inspecionadas sem cortes ou sobreposições |

Os 32 casos novos do backend cobrem conteúdo clínico e versões anteriores, autoria, CPF/endereço, dados profissionais, confirmação de assinatura manual, arquivos originais no ZIP e documentos sem arquivo, hashes, paginação, pacientes arquivados, papéis e usuários inativos, isolamento na API/repository/RLS, imutabilidade administrativa, falhas de Storage/renderer, limite operacional, textos longos, tags literais, acentos e glifos indisponíveis. Incluem permissão antes de tocar repositories/Storage e ausência de conteúdo clínico nas mensagens de falha do renderer.

O teste de concorrência pausa uma geração após estabelecer o snapshot, grava uma correção em outra requisição e retoma a coleta. O PDF mantém somente o estado anterior à correção; a próxima transação do pool volta a `read committed`. Outro teste gera rascunho de IA pendente e verifica que seu texto não aparece no PDF.

Os 12 casos novos do frontend cobrem abertura da listagem, formulário e payload, emissão sem pessoa jurídica, cadastro incompleto, erro preservando campos, permissões dos três perfis de consulta, recepção sem acesso, download PDF/ZIP, paginação e rejeição de arquivo com tipo inesperado.

## Conferência visual

O script local `.cache/pdf-etapa-9-exemplos.py` gerou:

| Exemplo | Páginas | Tamanho |
|---|---:|---:|
| Curto, identificação e registro clínico | 3 | 47.033 bytes |
| Texto extenso, nome longo, acentos, tags literais e palavra sem espaços | 6 | 49.857 bytes |
| Correção, peso, vacina e documento sem original | 4 | 49.712 bytes |

Todas as páginas foram renderizadas com Poppler em um container temporário e inspecionadas em folhas de contato. Foram conferidos margens, texto longo, paginação, campo de assinatura e diferenciação de versão substituída. pypdf confirmou a numeração e a presença do marcador final do texto longo. Os exemplos, PNGs e folhas de contato estão em `.cache/pdf-etapa-9/`, ignorados pelo Git. Não contêm dados reais.

A ferramenta de navegação retornou listas vazias de apps/navegadores. A revisão visual manual da tela da aplicação permanece pendente; isso não impediu a inspeção visual dos PDFs renderizados.

## Fluxo real local

Executado por `node .cache/smoke-etapa-9.mjs`, com as contas fictícias já provisionadas e `http://127.0.0.1:5173/api`. Criou paciente, tutor vinculado, atendimento e registro clínico fictícios; um rascunho de IA pendente; um documento externo com PDF original e outro apenas com resumo. Conferiu opções de emissão, recusou criação por administrador e ausência de ciência de assinatura manual.

A exportação foi preparada por veterinário e baixada como PDF e ZIP. Verificou hash e cabeçalhos, bloqueio de outra clínica, nova versão clínica, preservação byte a byte do PDF anterior e criação de outra emissão, além da paginação. Permanecem no ambiente local os registros e as duas emissões fictícias desse fluxo.

Uma inspeção posterior com Python confirmou: hash do PDF; mesmos bytes do PDF dentro do ZIP; hash do anexo original; ausência do texto do rascunho; e conteúdo anterior à correção preservado. Resultados em `.cache/smoke-etapa-9-resultados.json`; arquivos do fluxo em `.cache/pdf-etapa-9/fluxo-*`. Esses scripts usam contas deste computador e não são versionados; os testes automatizados são a reprodução portátil.

O primeiro teste de integração foi impedido pelo Docker parado. O Docker Desktop foi iniciado e o ambiente local restaurado, preservando volumes. Os testes foram executados novamente e passaram. Nenhum dado da aplicação foi limpo nem houve remarcação manual de revisão.

## Como executar e verificar

Na raiz:

```powershell
npm.cmd run dev
```

Em `http://localhost:5173`, entre como veterinário e abra **Animais → Prontuário → Ver exportações em PDF → Preparar novo PDF**. Selecione responsável com CPF/endereço, preencha os dados profissionais e, quando aplicável, do estabelecimento, confira as informações e confirme a ciência de assinatura/entrega manuais.

Depois, use **Baixar PDF** ou **Baixar PDF e anexos (ZIP)**. Confira autoria, datas, versões anteriores e documentos sem original. Corrija um registro clínico e baixe a emissão anterior: ela deve permanecer igual; prepare outra cópia para incluir a correção. Administradores e auxiliares podem baixar emissões existentes; recepção não deve acessar esses controles.

Em `backend/`:

```powershell
uv run --env-file ../.env --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy
```

Em `frontend/`:

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run format:check
npm.cmd run typecheck
npm.cmd run build
```

Nesta rodada, uv usou `--offline` nas verificações, cache em `.cache/uv` e mypy em `.cache/mypy-verificacao-etapa-9`. As novas dependências foram baixadas do registro após aprovação. Poppler foi instalado somente no container temporário de QA, removido automaticamente ao terminar.

## Limitações e diferenças

- PDF sem assinatura digital incorporada, conforme aprovado. Conferência do solicitante, assinatura manual/externa, protocolo, prazos e comprovante de recebimento continuam manuais. Não há integração de certificado, validação de assinatura externa ou registro automático de entrega.
- CPF/CNPJ passam por formato básico, sem consulta a cadastro externo, validação de titularidade ou comprovação da identidade. O formulário não substitui a conferência profissional da clínica. Cadastros refletem a emissão, sem reconstruir alterações históricas de identificação/responsabilidade.
- PDF até 10 MiB; PDF mais anexos até 100 MiB. Excesso falha sem truncar o prontuário. Falha do banco após gravar no Storage pode deixar objeto órfão, sem emissão visível; não foi criada rotina de exclusão de arquivos clínicos.
- PDF não incorpora os arquivos externos: os originais disponíveis acompanham o ZIP. Resumo não substitui laudo ausente. Caracteres sem glifo na fonte usam notação `[U+XXXX]`.
- Sem envio por WhatsApp/e-mail, portal do tutor, recibo eletrônico, automação de solicitação ou alegação de conformidade jurídica integral. Armazenamento local e hashes não substituem backup ou assinatura.
- A revisão visual da tela permanece pendente por indisponibilidade do navegador. Não foi executada nova auditoria de vulnerabilidades das dependências. Permanecem os avisos informativos de HTTPX/TestClient e tamanho do bundle; a CLI não foi atualizada.
- Sem diferenças funcionais em relação ao plano aprovado. Os limites operacionais e a representação de glifos foram documentados. Nenhum commit, push, deploy, recurso pago ou avanço para outra etapa foi realizado.
