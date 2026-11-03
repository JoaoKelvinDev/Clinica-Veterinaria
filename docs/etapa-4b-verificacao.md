# Verificação da Etapa 4b

Data: 2026-11-03. Ambiente: Windows, Docker Desktop, Supabase local com Storage. Somente dados fictícios; custo: zero.

## Entregas e arquivos

Documentos e laudos no prontuário, com arquivo (PDF, JPG ou PNG até 10 MB), resumo escrito ou os dois; correção por nova versão; abertura protegida do arquivo; auditoria. Decisões em `decisions/0007-etapa-4b-documentos.md`.

**Backend**
- `app/providers/storage.py`;
- `app/modules/records/documents.py`;
- modelo `PatientDocument`, schemas, repository e rotas em `records`;
- migração `c91f3a7d2b04`, após `b7d41e9a2c55`;
- `Settings.supabase_secret_key`; API 0.6.0;
- testes em `tests/test_documents.py`.

**Frontend:** `PatientDocuments.tsx`, `PatientDocuments.test.tsx`, ampliações em `records-api.ts`, `Records.tsx` e `styles.css`.

**Ambiente**
- `supabase/config.toml`: Storage ligado, limite de 10 MiB, S3 desligado;
- `scripts/start-local.mjs`: não exclui mais o `storage-api`;
- `scripts/setup-local.mjs`: cria o bucket privado, de forma idempotente;
- `docker-compose.yml`: passa `SUPABASE_SECRET_KEY` ao backend.

**Dependência nova:** `python-multipart==0.0.32`.

## Verificações executadas

| Verificação | Resultado real |
|---|---|
| pytest local | 151 passaram |
| Ruff lint e formatação; mypy | passaram; sem erros em 68 arquivos |
| Vitest | 37 passaram |
| ESLint, Prettier, TypeScript e build | passaram; o build avisa que o pacote JS passou de 500 KB (aviso, não erro) |
| `pip-audit` sobre o `uv.lock` | nenhuma vulnerabilidade conhecida |
| `npm audit --omit=dev` (frontend) | nenhuma vulnerabilidade |
| Fluxo real pela API (`.cache/smoke-etapa-4b.mjs`) | 13 de 13 verificações passaram |
| Acesso direto ao Storage sem credencial | recusado (HTTP 400); bucket `vetsys-documents` com `public = false` |
| Navegador: anexar PDF, documento só com resumo, abrir arquivo, corrigir | funcionou; o formulário de correção abre a 16px do topo com foco no primeiro campo |

Os testes automatizados cobrem:

- documento só com arquivo, só com resumo e com os dois;
- recusas:
  - sem arquivo e sem resumo;
  - executável renomeado para `.pdf`;
  - arquivo vazio ou acima de 10 MB;
  - tipo de documento desconhecido;
  - data futura;
  - "manter arquivo" sem correção;
- correção mantendo e trocando o arquivo, com a versão anterior ainda abrível;
- segunda correção da mesma versão (409) e correção por quem não é autor (403);
- vínculo com atendimento de outro paciente (422);
- administrador e recepção sem permissão de incluir; recepção sem abrir; outra clínica com 404;
- arquivo adulterado no armazenamento não é servido (503);
- auditoria registrando inclusão e abertura;
- `UPDATE` e `DELETE` recusados, inclusive para o administrador do banco;
- RLS escondendo documentos da recepção;
- limpeza de nomes de arquivo;
- o provedor real nunca sobrescreve, envia `x-upsert: false` e não põe a chave na URL.

No navegador automatizado, "Abrir arquivo" abriu a nova aba e o Edge baixou o PDF, porque o modo sem janela não tem visualizador de PDF. No navegador normal, o PDF abre no visualizador da aba.

## Como executar e verificar

Na raiz: `npm run dev`. O Supabase local sobe com o Storage, o bucket é criado e a migração é aplicada. Entre como veterinário ou auxiliar, abra o prontuário em **Animais** e use **Adicionar documento**. Para repetir o fluxo real: `node .cache/smoke-etapa-4b.mjs`.

## Limitações

- Sem pré-visualização dentro da página; o arquivo abre numa nova aba ou é baixado.
- Objetos sem registro podem sobrar no Storage se a gravação no banco falhar depois do envio (ver ADR 0007).
- A conta de recepção não existe na base local; o comportamento da recepção foi verificado pelos testes automatizados.
- Ficam na base local, fictícios: documentos de verificação e de teste pela tela no paciente de demonstração.

Critério de aceite atendido: a cópia de cada laudo fica no prontuário, íntegra, auditada e sem poder ser apagada. Nenhum push, deploy ou recurso pago foi feito.
