import type { ComponentProps } from 'react';
import { ActionScreen, ScreenArea, ScreenFeedback } from './Screen';
import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest } from './api';
import type { UserProfile } from './api';
import { errorMessage, parseLinks } from './registry-api';
import { displayDateTime } from './scheduling-api';
import {
  displayDate,
  displayWeight,
  entryFields,
  parseEntries,
  parseEntry,
  parseRecord,
  parseVaccine,
  parseWeight,
} from './records-api';
import type { PatientRecord, RecordEntry, VaccineRecord, WeightRecord } from './records-api';

import { PatientDocuments } from './PatientDocuments';
import { AiScribe } from './AiScribe';
import { RecordExports } from './RecordExports';

type Form =
  | { kind: 'entry'; supersedes: RecordEntry | null }
  | { kind: 'weight'; supersedes: WeightRecord | null }
  | { kind: 'vaccine'; supersedes: VaccineRecord | null };

export interface RecordTarget {
  patientId: string;
  patientName: string;
  encounterId?: string;
}

const today = () => new Date().toLocaleDateString('sv-SE', { timeZone: 'America/Fortaleza' });

function text(data: FormData, name: string): string | null {
  const value = String(data.get(name) ?? '').trim();
  return value === '' ? null : value;
}

function RecordsContent({
  token,
  user,
  target,
  onClose,
}: {
  token: string;
  user: UserProfile;
  target: RecordTarget;
  onClose: () => void;
}) {
  const isVet = user.role === 'veterinarian';
  const canWeigh = isVet || user.role === 'assistant';
  const [record, setRecord] = useState<PatientRecord | null>(null);
  const [incompleteTutor, setIncompleteTutor] = useState(false);
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [form, setForm] = useState<Form | null>(null);
  const [history, setHistory] = useState<RecordEntry[] | null>(null);

  useEffect(() => {
    let active = true;
    void Promise.all([
      apiRequest(token, `/patients/${target.patientId}/record`),
      apiRequest(token, `/patients/${target.patientId}/tutors`),
    ])
      .then(([body, links]) => {
        const result = parseRecord(body);
        const primary = parseLinks(links).find((link) => link.is_primary)?.tutor;
        if (active) {
          setRecord(result);
          setIncompleteTutor(!primary?.document || !primary.address);
        }
      })
      .catch((reason: unknown) => {
        if (active) setError(errorMessage(reason));
      });
    return () => {
      active = false;
    };
  }, [token, target.patientId, revision]);

  function open(next: Form) {
    setForm(next);
    setHistory(null);
    setError('');
    setNotice('');
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form) return;
    const data = new FormData(event.currentTarget);
    const correction = form.supersedes
      ? { supersedes_id: form.supersedes.id, correction_reason: text(data, 'correction_reason') }
      : {};
    setBusy(true);
    setError('');
    try {
      if (form.kind === 'entry') {
        const values = Object.fromEntries(entryFields.map(([name]) => [name, text(data, name)]));
        parseEntry(
          await apiRequest(
            token,
            `/encounters/${String(data.get('encounter_id'))}/record-entries`,
            {
              ...values,
              location: text(data, 'location'),
              follow_up_on: text(data, 'follow_up_on'),
              ...correction,
            },
            'POST',
          ),
        );
        setNotice(form.supersedes ? 'Correção registrada como nova versão.' : 'Registro salvo.');
      } else if (form.kind === 'weight') {
        const kg = Number(String(data.get('weight_kg')).replace(',', '.'));
        parseWeight(
          await apiRequest(
            token,
            `/patients/${target.patientId}/weights`,
            { weight_grams: Math.round(kg * 1000), ...correction },
            'POST',
          ),
        );
        setNotice('Peso registrado.');
      } else {
        const fields = ['vaccine_name', 'batch', 'manufacturer', 'dose'];
        const dates = ['manufactured_on', 'expires_on', 'next_dose_on'];
        parseVaccine(
          await apiRequest(
            token,
            `/patients/${target.patientId}/vaccines`,
            {
              encounter_id: String(data.get('encounter_id')),
              ...Object.fromEntries([...fields, ...dates].map((name) => [name, text(data, name)])),
              ...correction,
            },
            'POST',
          ),
        );
        setNotice('Vacina registrada.');
      }
      setForm(null);
      setRevision((current) => current + 1);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function showHistory(item: RecordEntry) {
    setBusy(true);
    setError('');
    try {
      setHistory(parseEntries(await apiRequest(token, `/record-entries/${item.id}/versions`)));
      setForm(null);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  const encounters = record?.encounters ?? [];
  const defaultEncounter =
    target.encounterId ?? encounters.find((item) => !item.completed_at)?.id ?? encounters[0]?.id;
  const encounterSelect = (selected?: string) => (
    <label>
      Atendimento
      <select name="encounter_id" required defaultValue={selected ?? defaultEncounter}>
        {encounters.map((item) => (
          <option key={item.id} value={item.id}>
            {displayDateTime(item.started_at)} com {item.veterinarian_name}
            {item.completed_at ? '' : ' (em andamento)'}
          </option>
        ))}
      </select>
    </label>
  );
  const reasonField = form?.supersedes && (
    <label>
      Motivo da correção
      <input name="correction_reason" required minLength={3} maxLength={500} />
    </label>
  );

  return (
    <ActionScreen
      title={<>Prontuário de {target.patientName}</>}
      onBack={() => {
        onClose();
      }}
      busy={busy}
    >
      <section className="panel registry">
        <div className="section-heading">
          <div>
            <p className="muted">
              Registros não são apagados. Corrigir cria uma nova versão e preserva a anterior.
            </p>
          </div>
        </div>
        <ScreenFeedback error={error} />
        <ScreenFeedback notice={notice} />
        {!record ? (
          !error && <p role="status">Carregando prontuário…</p>
        ) : (
          <>
            {incompleteTutor && (
              <p className="confirmation">
                O responsável principal está sem CPF ou endereço. Esses dados serão exigidos para
                emitir documentos do prontuário.
              </p>
            )}
            {record.clinical_access && (
              <RecordExports token={token} user={user} patientId={target.patientId} />
            )}
            {!record.clinical_access && (
              <p className="muted">
                Seu papel vê somente as datas dos atendimentos. O conteúdo clínico é restrito à
                equipe clínica.
              </p>
            )}
            {(isVet || canWeigh) && (
              <div className="actions">
                {isVet && (
                  <button
                    disabled={busy || encounters.length === 0}
                    onClick={() => open({ kind: 'entry', supersedes: null })}
                  >
                    Novo registro clínico
                  </button>
                )}
                {canWeigh && (
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => open({ kind: 'weight', supersedes: null })}
                  >
                    Registrar peso
                  </button>
                )}
                {isVet && (
                  <button
                    className="secondary"
                    disabled={busy || encounters.length === 0}
                    onClick={() => open({ kind: 'vaccine', supersedes: null })}
                  >
                    Registrar vacina
                  </button>
                )}
              </div>
            )}
            {isVet && encounters.length === 0 && (
              <p className="muted">
                Inicie um atendimento na Agenda para registrar no prontuário deste paciente.
              </p>
            )}

            {form?.kind === 'entry' && (
              <ActionScreen
                title={
                  <>
                    {form.supersedes
                      ? `Corrigir versão ${form.supersedes.version}`
                      : 'Novo registro clínico'}
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
                  key={form.supersedes?.id ?? 'novo'}
                  className="registry-form"

                  onSubmit={(event) => {
                    void submit(event);
                  }}
                >
                  {form.supersedes ? (
                    <input type="hidden" name="encounter_id" value={form.supersedes.encounter_id} />
                  ) : (
                    encounterSelect()
                  )}
                  <label>
                    Local do atendimento
                    <input
                      name="location"
                      maxLength={200}
                      defaultValue={form.supersedes?.location}
                      placeholder="Deixe em branco para usar a clínica"
                    />
                  </label>
                  {entryFields.map(([name, label, required]) => (
                    <label key={name}>
                      {required ? label : `${label} (opcional)`}
                      <textarea
                        name={name}
                        required={required}
                        maxLength={name === 'follow_up' ? 500 : 20000}
                        defaultValue={form.supersedes?.[name] ?? ''}
                      />
                    </label>
                  ))}
                  <label>
                    Data de retorno (opcional)
                    <input
                      name="follow_up_on"
                      type="date"
                      min={form.supersedes ? undefined : today()}
                      defaultValue={form.supersedes?.follow_up_on ?? ''}
                    />
                  </label>
                  <p className="muted">
                    Com data, o tutor recebe um lembrete de retorno por WhatsApp, se tiver
                    autorizado.
                  </p>
                  {reasonField}
                  <div className="actions">
                    <button disabled={busy}>{busy ? 'Salvando…' : 'Salvar registro'}</button>
                    <button type="button" className="secondary" onClick={() => setForm(null)}>
                      Cancelar
                    </button>
                  </div>
                </form>
              </ActionScreen>
            )}

            {form?.kind === 'weight' && (
              <ActionScreen
                title={<>{form.supersedes ? 'Corrigir peso' : 'Registrar peso'}</>}
                onBack={() => {
                  setForm(null);
                }}
                busy={busy}
                error={error}
                notice={notice}
              >
                <form
                  key={form.supersedes?.id ?? 'novo'}
                  className="registry-form"

                  onSubmit={(event) => {
                    void submit(event);
                  }}
                >
                  <label>
                    Peso em kg
                    <input
                      name="weight_kg"
                      required
                      inputMode="decimal"
                      pattern="[0-9]+([,.][0-9]{1,3})?"
                      title="Use até 3 casas decimais, como 12,5"
                    />
                  </label>
                  {reasonField}
                  <div className="actions">
                    <button disabled={busy}>{busy ? 'Salvando…' : 'Salvar peso'}</button>
                    <button type="button" className="secondary" onClick={() => setForm(null)}>
                      Cancelar
                    </button>
                  </div>
                </form>
              </ActionScreen>
            )}

            {form?.kind === 'vaccine' && (
              <ActionScreen
                title={<>{form.supersedes ? 'Corrigir vacina' : 'Registrar vacina'}</>}
                onBack={() => {
                  setForm(null);
                }}
                busy={busy}
                error={error}
                notice={notice}
              >
                <form
                  key={form.supersedes?.id ?? 'novo'}
                  className="registry-form"

                  onSubmit={(event) => {
                    void submit(event);
                  }}
                >
                  <p className="muted">
                    Campos da carteira de vacinação (Resolução CFMV 1321/2020).
                  </p>
                  {encounterSelect(form.supersedes?.encounter_id)}
                  <label>
                    Vacina
                    <input
                      name="vaccine_name"
                      required
                      maxLength={200}
                      defaultValue={form.supersedes?.vaccine_name}
                    />
                  </label>
                  <div className="field-pair">
                    <label>
                      Partida (lote)
                      <input
                        name="batch"
                        required
                        maxLength={80}
                        defaultValue={form.supersedes?.batch}
                      />
                    </label>
                    <label>
                      Dose
                      <input
                        name="dose"
                        required
                        maxLength={80}
                        placeholder="1ª dose, reforço…"
                        defaultValue={form.supersedes?.dose}
                      />
                    </label>
                  </div>
                  <label>
                    Fabricante
                    <input
                      name="manufacturer"
                      required
                      maxLength={200}
                      defaultValue={form.supersedes?.manufacturer}
                    />
                  </label>
                  <div className="field-pair">
                    <label>
                      Fabricação
                      <input
                        name="manufactured_on"
                        type="date"
                        required
                        defaultValue={form.supersedes?.manufactured_on}
                      />
                    </label>
                    <label>
                      Validade
                      <input
                        name="expires_on"
                        type="date"
                        required
                        defaultValue={form.supersedes?.expires_on}
                      />
                    </label>
                  </div>
                  <label>
                    Revacinação prevista (opcional)
                    <input
                      name="next_dose_on"
                      type="date"
                      defaultValue={form.supersedes?.next_dose_on ?? ''}
                    />
                  </label>
                  {reasonField}
                  <div className="actions">
                    <button disabled={busy}>{busy ? 'Salvando…' : 'Salvar vacina'}</button>
                    <button type="button" className="secondary" onClick={() => setForm(null)}>
                      Cancelar
                    </button>
                  </div>
                </form>
              </ActionScreen>
            )}

            {history && (
              <ActionScreen
                title={<>Histórico de versões</>}
                onBack={() => {
                  setHistory(null);
                }}
                busy={busy}
                error={error}
                notice={notice}
              >
                <section
                  className="registry-form"

                  key={history[0]?.root_id}
                >
                  <div className="section-heading"></div>
                  {history.map((item) => (
                    <EntryView key={item.id} item={item} />
                  ))}
                </section>
              </ActionScreen>
            )}

            {record.clinical_access && (
              <AiScribe
                token={token}
                user={user}
                patientId={target.patientId}
                encounters={encounters}
                defaultEncounter={defaultEncounter}
                onApproved={() => setRevision((current) => current + 1)}
              />
            )}

            <h3>Atendimentos</h3>
            {encounters.length === 0 ? (
              <p>Nenhum atendimento registrado para este paciente.</p>
            ) : (
              encounters.map((visit) => {
                const entries = record.entries.filter((item) => item.encounter_id === visit.id);
                const vaccines = record.vaccines.filter((item) => item.encounter_id === visit.id);
                return (
                  <article key={visit.id} className="visit">
                    <h4>
                      {displayDateTime(visit.started_at)} com {visit.veterinarian_name}
                      {visit.completed_at ? '' : ' (em andamento)'}
                    </h4>
                    {record.clinical_access && entries.length + vaccines.length === 0 && (
                      <p className="muted">Sem registros neste atendimento.</p>
                    )}
                    {entries.map((item) => (
                      <div key={item.id}>
                        <EntryView item={item} />
                        <div className="actions">
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
                            <button
                              className="secondary"
                              disabled={busy}
                              onClick={() => open({ kind: 'entry', supersedes: item })}
                            >
                              Corrigir registro
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                    {vaccines.map((item) => (
                      <div key={item.id} className="record-line">
                        <p>
                          <strong>{item.vaccine_name}</strong>, {item.dose}. Partida {item.batch},{' '}
                          {item.manufacturer}, fabricação {displayDate(item.manufactured_on)},
                          validade {displayDate(item.expires_on)}.
                          {item.next_dose_on &&
                            ` Revacinação prevista para ${displayDate(item.next_dose_on)}.`}
                        </p>
                        <p className="muted">
                          Aplicada por {item.author_name} ({item.author_crmv}) em{' '}
                          {displayDateTime(item.created_at)}
                          {item.correction_reason && `. Corrigida: ${item.correction_reason}`}
                        </p>
                        {item.author_id === user.id && (
                          <button
                            className="secondary"
                            disabled={busy}
                            onClick={() => open({ kind: 'vaccine', supersedes: item })}
                          >
                            Corrigir vacina
                          </button>
                        )}
                      </div>
                    ))}
                  </article>
                );
              })
            )}

            {record.clinical_access && (
              <>
                <h3>Pesagens</h3>
                {record.weights.length === 0 ? (
                  <p>Nenhum peso registrado.</p>
                ) : (
                  <ul className="link-list">
                    {record.weights.map((item) => (
                      <li key={item.id}>
                        <p>
                          <strong>{displayWeight(item.weight_grams)}</strong>{' '}
                          <span className="muted">
                            em {displayDateTime(item.created_at)} por {item.author_name}
                            {item.correction_reason && `. Corrigido: ${item.correction_reason}`}
                          </span>
                        </p>
                        {item.author_id === user.id && (
                          <button
                            className="secondary"
                            disabled={busy}
                            onClick={() => open({ kind: 'weight', supersedes: item })}
                          >
                            Corrigir peso
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                <PatientDocuments
                  token={token}
                  user={user}
                  patientId={target.patientId}
                  documents={record.documents}
                  encounters={encounters}
                  onSaved={() => setRevision((current) => current + 1)}
                />
              </>
            )}
          </>
        )}
      </section>
    </ActionScreen>
  );
}

function EntryView({ item }: { item: RecordEntry }) {
  return (
    <div className="record-entry">
      <dl>
        {entryFields.map(([name, label]) =>
          item[name] ? (
            <div key={name}>
              <dt>{label}</dt>
              <dd>{item[name]}</dd>
            </div>
          ) : null,
        )}
      </dl>
      <p className="muted">
        Versão {item.version}, registrada por {item.author_name} ({item.author_crmv}) em{' '}
        {displayDateTime(item.created_at)}, {item.location}
        {item.follow_up_on && `. Retorno previsto para ${displayDate(item.follow_up_on)}`}
        {item.correction_reason && `. Motivo da correção: ${item.correction_reason}`}
      </p>
    </div>
  );
}

export function Records(props: ComponentProps<typeof RecordsContent>) {
  return (
    <ScreenArea>
      <RecordsContent {...props} />
    </ScreenArea>
  );
}
