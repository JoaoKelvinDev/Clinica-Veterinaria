import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest } from './api';
import type { UserProfile } from './api';
import { draftStatuses, parseDraft, parseDrafts, soapGroups } from './ai-scribe-api';
import type { AiDraft } from './ai-scribe-api';
import { entryFields } from './records-api';
import type { TimelineEncounter } from './records-api';
import { errorMessage } from './registry-api';
import { displayDateTime } from './scheduling-api';
import { reveal } from './reveal';

export function AiScribe({
  token,
  user,
  patientId,
  encounters,
  defaultEncounter,
  onApproved,
}: {
  token: string;
  user: UserProfile;
  patientId: string;
  encounters: TimelineEncounter[];
  defaultEncounter?: string | undefined;
  onApproved: () => void;
}) {
  const canAct = user.role === 'veterinarian';
  const [opened, setOpened] = useState(false);
  const [drafts, setDrafts] = useState<AiDraft[] | null>(null);
  const [selected, setSelected] = useState<AiDraft | null>(null);
  const [generation, setGeneration] = useState(false);
  const [source, setSource] = useState('text');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    if (!opened) return;
    let active = true;
    void apiRequest(token, `/patients/${patientId}/ai-drafts`)
      .then((body) => {
        if (active) setDrafts(parseDrafts(body));
      })
      .catch((reason: unknown) => {
        if (active) setError(errorMessage(reason));
      });
    return () => {
      active = false;
    };
  }, [token, patientId, opened]);

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const draft = parseDraft(
        await apiRequest(
          token,
          `/encounters/${String(data.get('encounter_id'))}/ai-drafts`,
          source === 'text'
            ? { source, transcript: String(data.get('transcript')) }
            : { source, sample_id: 'consultation' },
          'POST',
        ),
      );
      setDrafts((current) => [draft, ...(current ?? [])]);
      setSelected(draft);
      setGeneration(false);
      setNotice('Rascunho MOCK gerado. Nenhum registro oficial foi criado.');
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  function updated(draft: AiDraft) {
    setDrafts(
      (current) => current?.map((item) => (item.id === draft.id ? draft : item)) ?? [draft],
    );
    setSelected(draft);
  }

  async function approve(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError('');
    setNotice('');
    const text = (name: string) => String(data.get(name) ?? '').trim() || null;
    try {
      updated(
        parseDraft(
          await apiRequest(
            token,
            `/ai-drafts/${selected.id}/approve`,
            {
              review_confirmed: data.get('review_confirmed') === 'on',
              record: {
                ...Object.fromEntries(entryFields.map(([key]) => [key, text(key)])),
                location: text('location'),
                follow_up_on: text('follow_up_on'),
              },
            },
            'POST',
          ),
        ),
      );
      setNotice('Rascunho aprovado. Registro oficial criado com sua autoria.');
      onApproved();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function discard() {
    if (!selected) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      updated(parseDraft(await apiRequest(token, `/ai-drafts/${selected.id}/discard`, {}, 'POST')));
      setNotice('Rascunho descartado. Nenhum registro oficial foi criado.');
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="scribe-title">
      <div className="section-heading">
        <h3 id="scribe-title">Rascunhos assistidos (MOCK)</h3>
        <button className="secondary" disabled={busy} onClick={() => setOpened(!opened)}>
          {opened ? 'Fechar rascunhos' : 'Abrir rascunhos'}
        </button>
      </div>
      {opened && (
        <>
          <p className="confirmation">
            Modo de testes (MOCK): sem IA ou transcrição de áudio reais. O simulador organiza campos
            rotulados; o veterinário revisa e completa antes de aprovar.
          </p>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          {notice && (
            <p className="success-message" role="status">
              {notice}
            </p>
          )}
          {canAct && (
            <button
              className="secondary"
              disabled={busy || drafts === null || encounters.length === 0}
              onClick={() => {
                setGeneration(true);
                setSelected(null);
                setError('');
                setNotice('');
              }}
            >
              Novo rascunho MOCK
            </button>
          )}
          {generation && (
            <form
              className="registry-form"
              ref={reveal}
              onSubmit={(event) => {
                void generate(event);
              }}
            >
              <h4>Gerar rascunho MOCK</h4>
              <label>
                Atendimento do rascunho
                <select
                  name="encounter_id"
                  required
                  defaultValue={defaultEncounter ?? encounters[0]?.id}
                >
                  {encounters.map((item) => (
                    <option key={item.id} value={item.id}>
                      {displayDateTime(item.started_at)} com {item.veterinarian_name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Entrada
                <select value={source} onChange={(event) => setSource(event.target.value)}>
                  <option value="text">Transcrição em texto</option>
                  <option value="mock_audio">Exemplo fictício de transcrição (MOCK)</option>
                </select>
              </label>
              {source === 'text' ? (
                <>
                  <label>
                    Transcrição da consulta
                    <textarea name="transcript" required maxLength={20000} rows={8} />
                  </label>
                  <p className="muted">
                    No MOCK, use estes rótulos, um por linha:{' '}
                    {entryFields.map(([, label]) => `${label}:`).join(' ')}
                  </p>
                </>
              ) : (
                <p>
                  Exemplo fictício sem gravação ou envio de arquivo. Diagnóstico e campos ausentes
                  ficarão vazios.
                </p>
              )}
              <div className="actions">
                <button disabled={busy}>Gerar rascunho</button>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => setGeneration(false)}
                >
                  Cancelar geração
                </button>
              </div>
            </form>
          )}
          {!drafts && !error && <p role="status">Carregando rascunhos…</p>}
          {drafts?.length === 0 && <p>Nenhum rascunho para este paciente.</p>}
          {drafts && (
            <ul className="link-list">
              {drafts.map((item) => (
                <li key={item.id}>
                  <span>
                    {draftStatuses[item.status]} · {displayDateTime(item.created_at)} ·{' '}
                    {item.llm_model}
                  </span>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => {
                      setSelected(item);
                      setGeneration(false);
                      setError('');
                      setNotice('');
                    }}
                  >
                    {canAct && item.status === 'pending' ? 'Revisar rascunho' : 'Ver rascunho'}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {selected && (
            <div className="registry-form" key={selected.id} ref={reveal}>
              <h4>Revisão do rascunho — {draftStatuses[selected.status]}</h4>
              <p className="muted">
                Atendimento:{' '}
                {displayDateTime(
                  encounters.find((item) => item.id === selected.encounter_id)?.started_at ??
                    selected.created_at,
                )}{' '}
                · Modelo {selected.llm_model} · Prompt {selected.prompt_version}
              </p>
              <p>
                As edições são gravadas ao aprovar. Fechar esta tela perde as edições ainda não
                aprovadas.
              </p>
              <div className="field-pair scribe-review">
                <div>
                  <h4>Transcrição de origem</h4>
                  <p className="document-summary">{selected.transcript}</p>
                  <h4>Incertezas e informações ausentes</h4>
                  <ul>
                    {selected.content.uncertainties.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                  <ul>
                    {entryFields
                      .filter(([key, , required]) => required && !selected.content[key])
                      .map(([, label]) => (
                        <li key={label}>{label}: não informado; preencha antes de aprovar.</li>
                      ))}
                  </ul>
                  <details>
                    <summary>Conteúdo gerado original</summary>
                    {entryFields.map(([key, label]) => (
                      <p key={key}>
                        <strong>{label}: </strong>
                        {selected.content[key] ?? 'Não informado'}
                      </p>
                    ))}
                  </details>
                </div>
                {canAct && selected.status === 'pending' ? (
                  <form
                    onSubmit={(event) => {
                      void approve(event);
                    }}
                  >
                    {soapGroups.map((group) => (
                      <fieldset key={group.title}>
                        <legend>{group.title}</legend>
                        {group.fields.map((key) => {
                          const field = entryFields.find(([name]) => name === key)!;
                          return (
                            <label key={key}>
                              {field[1]}
                              {field[2] ? '' : ' (opcional)'}
                              <textarea
                                name={key}
                                required={field[2]}
                                maxLength={key === 'follow_up' ? 500 : 20000}
                                defaultValue={selected.content[key] ?? ''}
                              />
                            </label>
                          );
                        })}
                      </fieldset>
                    ))}
                    <label>
                      Local do registro aprovado
                      <input
                        name="location"
                        maxLength={200}
                        placeholder="Deixe em branco para usar a clínica"
                      />
                    </label>
                    <label>
                      Data de retorno do registro aprovado (opcional)
                      <input
                        name="follow_up_on"
                        type="date"
                        min={new Date().toLocaleDateString('sv-SE', {
                          timeZone: 'America/Fortaleza',
                        })}
                      />
                    </label>
                    <label className="checkbox">
                      <input name="review_confirmed" type="checkbox" required />
                      Revisei a transcrição e todos os campos e assumo a autoria do registro.
                    </label>
                    <div className="actions">
                      <button disabled={busy}>Aprovar e registrar no prontuário</button>
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => {
                          void discard();
                        }}
                      >
                        Descartar rascunho
                      </button>
                    </div>
                  </form>
                ) : (
                  <div>
                    <h4>Conteúdo original preservado</h4>
                    {entryFields.map(([key, label]) => (
                      <p key={key}>
                        <strong>{label}: </strong>
                        {selected.content[key] ?? 'Não informado'}
                      </p>
                    ))}
                    {selected.record_entry_id && (
                      <p>Registro oficial disponível nos atendimentos deste prontuário.</p>
                    )}
                    {selected.resolved_at && (
                      <p className="muted">Finalizado em {displayDateTime(selected.resolved_at)}</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
