import type { ComponentProps } from 'react';
import { ActionScreen, ScreenArea, ScreenFeedback } from './Screen';
import { useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest } from './api';
import { maxDocumentMegabytes } from './environment';
import type { UserProfile } from './api';
import { errorMessage } from './registry-api';
import { displayDateTime } from './scheduling-api';
import {
  displayDate,
  displaySize,
  documentKinds,
  fetchDocumentFile,
  maxDocumentBytes,
  parseDocuments,
  uploadDocument,
} from './records-api';
import type { PatientDocument, TimelineEncounter } from './records-api';

const today = () => new Date().toLocaleDateString('sv-SE', { timeZone: 'America/Fortaleza' });

/** Laudos e documentos de outros profissionais: arquivo, resumo escrito ou os dois. */
function PatientDocumentsContent({
  token,
  user,
  patientId,
  documents,
  encounters,
  onSaved,
}: {
  token: string;
  user: UserProfile;
  patientId: string;
  documents: PatientDocument[];
  encounters: TimelineEncounter[];
  onSaved: () => void;
}) {
  const canAdd = user.role === 'veterinarian' || user.role === 'assistant';
  const [form, setForm] = useState<{ supersedes: PatientDocument | null } | null>(null);
  const [history, setHistory] = useState<PatientDocument[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  function open(supersedes: PatientDocument | null) {
    setForm({ supersedes });
    setHistory(null);
    setError('');
    setNotice('');
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form) return;
    const data = new FormData(event.currentTarget);
    const file = data.get('file');
    const hasFile = file instanceof File && file.size > 0;
    if (!hasFile) data.delete('file');
    if (hasFile && file.size > maxDocumentBytes) {
      setError(`O arquivo passa de ${maxDocumentMegabytes} MB.`);
      return;
    }
    const summary = String(data.get('summary') ?? '').trim();
    const keepFile = data.get('keep_file') === 'true';
    if (!hasFile && !summary && !keepFile) {
      setError('Anexe um arquivo ou escreva um resumo do documento.');
      return;
    }
    // Campos vazios não são enviados: o backend os trata como ausentes.
    for (const [name, value] of [...data.entries()])
      if (typeof value === 'string' && value.trim() === '') data.delete(name);
    if (form.supersedes) data.set('supersedes_id', form.supersedes.id);
    setBusy(true);
    setError('');
    try {
      await uploadDocument(token, patientId, data);
      setForm(null);
      setNotice(form.supersedes ? 'Correção do documento registrada.' : 'Documento adicionado.');
      onSaved();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function openFile(item: PatientDocument) {
    // A aba é aberta já no clique, para o navegador não tratá-la como pop-up.
    const tab = window.open('', '_blank');
    setError('');
    try {
      const url = URL.createObjectURL(await fetchDocumentFile(token, item.id));
      if (tab) tab.location.href = url;
      else {
        const link = document.createElement('a');
        link.href = url;
        link.download = item.file_name ?? 'documento';
        link.click();
      }
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (reason) {
      tab?.close();
      setError(errorMessage(reason));
    }
  }

  async function showHistory(item: PatientDocument) {
    setBusy(true);
    setError('');
    try {
      setHistory(parseDocuments(await apiRequest(token, `/documents/${item.id}/versions`)));
      setForm(null);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  const previous = form?.supersedes;
  return (
    <>
      <div className="section-heading">
        <h3>Documentos e laudos</h3>
        {canAdd && (
          <button className="secondary" disabled={busy} onClick={() => open(null)}>
            Adicionar documento
          </button>
        )}
      </div>
      <ScreenFeedback error={error} />
      <ScreenFeedback notice={notice} />
      {form && (
        <ActionScreen
          title={
            <>
              {previous ? `Corrigir documento (versão ${previous.version})` : 'Adicionar documento'}
            </>
          }
          onBack={() => {
            setForm(null);
          }}
          busy={busy}
          error={error}
          notice={notice}
        >
          <form
            key={previous?.id ?? 'novo'}
            className="registry-form"

            onSubmit={(event) => {
              void submit(event);
            }}
          >
            <p className="muted">
              Anexe o arquivo, escreva um resumo ou faça os dois. PDF, JPG ou PNG de até{' '}
              {maxDocumentMegabytes} MB.
            </p>
            <label>
              Tipo
              <select name="kind" required defaultValue={previous?.kind ?? 'lab_report'}>
                {Object.entries(documentKinds).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <div className="field-pair">
              <label>
                Origem (profissional, clínica ou laboratório)
                <input
                  name="origin_name"
                  required
                  maxLength={200}
                  defaultValue={previous?.origin_name}
                />
              </label>
              <label>
                CRMV da origem (opcional)
                <input
                  name="origin_crmv"
                  maxLength={40}
                  placeholder="CRMV-PI 0000"
                  defaultValue={previous?.origin_crmv ?? ''}
                />
              </label>
            </div>
            <div className="field-pair">
              <label>
                Data do documento
                <input
                  name="document_date"
                  type="date"
                  required
                  max={today()}
                  defaultValue={previous?.document_date}
                />
              </label>
              <label>
                Atendimento relacionado (opcional)
                <select name="encounter_id" defaultValue={previous?.encounter_id ?? ''}>
                  <option value="">Nenhum</option>
                  {encounters.map((item) => (
                    <option key={item.id} value={item.id}>
                      {displayDateTime(item.started_at)} com {item.veterinarian_name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Arquivo (opcional)
              <input
                name="file"
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
              />
            </label>
            {previous?.file_name && (
              <label className="checkbox">
                <input name="keep_file" type="checkbox" value="true" defaultChecked />
                Manter o arquivo atual ({previous.file_name}) se nenhum novo for anexado
              </label>
            )}
            <label>
              Resumo (opcional)
              <textarea
                name="summary"
                maxLength={20000}
                placeholder="Ex.: hemograma de 10/10 sem alterações; vacinado em outra clínica…"
                defaultValue={previous?.summary ?? ''}
              />
            </label>
            {previous && (
              <label>
                Motivo da correção
                <input name="correction_reason" required minLength={3} maxLength={500} />
              </label>
            )}
            <div className="actions">
              <button disabled={busy}>{busy ? 'Enviando…' : 'Salvar documento'}</button>
              <button type="button" className="secondary" onClick={() => setForm(null)}>
                Cancelar
              </button>
            </div>
          </form>
        </ActionScreen>
      )}
      {history && (
        <ActionScreen
          title="Versões do documento"
          onBack={() => setHistory(null)}
          busy={busy}
          error={error}
          notice={notice}
        >
          <section className="registry-form" key={history[0]?.root_id}>
            {history.map((item) => (
              <DocumentView key={item.id} item={item} />
            ))}
          </section>
        </ActionScreen>
      )}
      {documents.length === 0 ? (
        <p>Nenhum documento anexado.</p>
      ) : (
        <ul className="link-list">
          {documents.map((item) => (
            <li key={item.id}>
              <DocumentView item={item} />
              <div className="actions">
                {item.file_name && (
                  <button
                    className="secondary"
                    onClick={() => {
                      void openFile(item);
                    }}
                  >
                    Abrir arquivo
                  </button>
                )}
                {item.version > 1 && (
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => {
                      void showHistory(item);
                    }}
                  >
                    Ver versões anteriores
                  </button>
                )}
                {item.author_id === user.id && (
                  <button className="secondary" disabled={busy} onClick={() => open(item)}>
                    Corrigir documento
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function DocumentView({ item }: { item: PatientDocument }) {
  return (
    <div className="record-line">
      <p>
        <strong>{documentKinds[item.kind]}</strong> de {item.origin_name}
        {item.origin_crmv && ` (${item.origin_crmv})`}, {displayDate(item.document_date)}
        {item.file_name && item.size_bytes !== null && (
          <span className="muted">
            , arquivo {item.file_name} ({displaySize(item.size_bytes)})
          </span>
        )}
      </p>
      {item.summary && <p className="document-summary">{item.summary}</p>}
      <p className="muted">
        Versão {item.version}, adicionado por {item.author_name}
        {item.author_crmv && ` (${item.author_crmv})`} em {displayDateTime(item.created_at)}
        {item.correction_reason && `. Motivo da correção: ${item.correction_reason}`}
      </p>
    </div>
  );
}

export function PatientDocuments(props: ComponentProps<typeof PatientDocumentsContent>) {
  const [opened, setOpened] = useState(false);
  return (
    <ScreenArea>
      <section className="module-card">
        <div>
          <h3>Documentos e laudos</h3>
          <p className="muted">Exames, documentos externos e suas versões preservadas.</p>
        </div>
        <button className="secondary" onClick={() => setOpened(true)}>
          Ver documentos e laudos
        </button>
      </section>
      {opened && (
        <ActionScreen title="Documentos e laudos do paciente" onBack={() => setOpened(false)}>
          <PatientDocumentsContent {...props} />
        </ActionScreen>
      )}
    </ScreenArea>
  );
}
