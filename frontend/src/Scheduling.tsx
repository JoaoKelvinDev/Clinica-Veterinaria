import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest, parseUser } from './api';
import type { UserProfile } from './api';
import { errorMessage, parsePage, parsePatient } from './registry-api';
import type { Page, Patient } from './registry-api';
import {
  displayDateTime,
  localDateTime,
  parseAppointment,
  parseEncounter,
  statusLabels,
  utcDateTime,
} from './scheduling-api';
import type { Appointment, AppointmentStatus, Encounter } from './scheduling-api';

interface Draft {
  id: string | null;
  patient_id: string;
  patient_name: string;
  veterinarian_id: string;
  starts_at: string;
  ends_at: string;
  kind: string;
  walkIn: boolean;
}
interface Action {
  item: Appointment | Encounter;
  kind: 'confirmed' | 'cancelled' | 'no_show' | 'start' | 'complete';
}
const actionLabels = {
  confirmed: 'Confirmar consulta',
  cancelled: 'Cancelar consulta',
  no_show: 'Registrar falta',
  start: 'Iniciar atendimento',
  complete: 'Concluir atendimento',
};

export function Scheduling({ token, user }: { token: string; user: UserProfile }) {
  const canBook = user.role === 'admin' || user.role === 'reception';
  const isVet = user.role === 'veterinarian';
  const [day, setDay] = useState(() => localDateTime(new Date()).slice(0, 10));
  const [vetFilter, setVetFilter] = useState('');
  const [vets, setVets] = useState<UserProfile[]>([]);
  const [appointments, setAppointments] = useState<Page<Appointment>>({ items: [], total: 0 });
  const [encounters, setEncounters] = useState<Page<Encounter>>({ items: [], total: 0 });
  const [appointmentOffset, setAppointmentOffset] = useState(0);
  const [encounterOffset, setEncounterOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [draft, setDraft] = useState<Draft | null>(null);
  const [action, setAction] = useState<Action | null>(null);
  const [patientQuery, setPatientQuery] = useState('');
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientSearched, setPatientSearched] = useState(false);

  useEffect(() => {
    let active = true;
    void apiRequest(token, '/veterinarians')
      .then((body) => {
        if (!Array.isArray(body)) throw new Error('Não foi possível carregar os veterinários.');
        const result = body.map(parseUser);
        if (active) setVets(result);
      })
      .catch((reason: unknown) => {
        if (active) setError(errorMessage(reason));
      });
    return () => {
      active = false;
    };
  }, [token, revision]);

  useEffect(() => {
    let active = true;
    const query = `day=${encodeURIComponent(day)}${vetFilter ? `&veterinarian_id=${encodeURIComponent(vetFilter)}` : ''}&limit=20`;
    void Promise.all([
      apiRequest(token, `/appointments?${query}&offset=${appointmentOffset}`),
      apiRequest(token, `/encounters?${query}&offset=${encounterOffset}`),
    ])
      .then(([a, e]) => {
        const bookings = parsePage(a, parseAppointment);
        const visits = parsePage(e, parseEncounter);
        if (active) {
          setAppointments(bookings);
          setEncounters(visits);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(errorMessage(reason));
          setAppointments({ items: [], total: 0 });
          setEncounters({ items: [], total: 0 });
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, day, vetFilter, appointmentOffset, encounterOffset, revision]);

  function refresh() {
    setLoading(true);
    setRevision((current) => current + 1);
  }
  function newDraft(walkIn: boolean) {
    setDraft({
      id: null,
      patient_id: '',
      patient_name: '',
      veterinarian_id: isVet ? user.id : '',
      starts_at: `${day}T09:00`,
      ends_at: `${day}T09:30`,
      kind: 'Consulta',
      walkIn,
    });
    setPatientQuery('');
    setPatients([]);
    setPatientSearched(false);
    setError('');
    setNotice('');
    setAction(null);
  }
  function edit(item: Appointment) {
    setDraft({
      id: item.id,
      patient_id: item.patient_id,
      patient_name: item.patient_name,
      veterinarian_id: item.veterinarian_id,
      starts_at: localDateTime(item.starts_at),
      ends_at: localDateTime(item.ends_at),
      kind: item.kind,
      walkIn: false,
    });
    setPatientQuery('');
    setPatients([]);
    setPatientSearched(false);
    setError('');
    setNotice('');
    setAction(null);
  }
  async function searchPatients() {
    setBusy(true);
    setError('');
    try {
      const page = parsePage(
        await apiRequest(
          token,
          `/patients?q=${encodeURIComponent(patientQuery.trim())}&limit=20&offset=0`,
        ),
        parsePatient,
      );
      setPatients(page.items);
      setPatientSearched(true);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      if (draft.walkIn) {
        parseEncounter(
          await apiRequest(token, '/encounters', { patient_id: draft.patient_id }, 'POST'),
        );
      } else {
        const values = {
          patient_id: draft.patient_id,
          veterinarian_id: draft.veterinarian_id,
          starts_at: utcDateTime(draft.starts_at),
          ends_at: utcDateTime(draft.ends_at),
          kind: draft.kind.trim(),
        };
        parseAppointment(
          await apiRequest(
            token,
            draft.id ? `/appointments/${draft.id}` : '/appointments',
            values,
            draft.id ? 'PATCH' : 'POST',
          ),
        );
      }
      setNotice(
        draft.walkIn
          ? 'Atendimento avulso iniciado. Consulte o dia de hoje para acompanhá-lo.'
          : 'Agendamento salvo. O horário precisa ser confirmado com o tutor.',
      );
      setDraft(null);
      refresh();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }
  async function executeAction() {
    if (!action) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      if (action.kind === 'start')
        parseEncounter(
          await apiRequest(token, `/appointments/${action.item.id}/start`, undefined, 'POST'),
        );
      else if (action.kind === 'complete')
        parseEncounter(
          await apiRequest(token, `/encounters/${action.item.id}/complete`, undefined, 'POST'),
        );
      else
        parseAppointment(
          await apiRequest(
            token,
            `/appointments/${action.item.id}/status`,
            { status: action.kind as AppointmentStatus },
            'PUT',
          ),
        );
      setNotice(
        action.kind === 'start'
          ? 'Atendimento iniciado agora. Consulte os atendimentos do dia de hoje para concluí-lo.'
          : `${actionLabels[action.kind]}: operação concluída.`,
      );
      setAction(null);
      refresh();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }
  const editable = (item: Appointment) =>
    item.status === 'scheduled' || item.status === 'confirmed';
  function ask(item: Appointment | Encounter, kind: Action['kind']) {
    setAction({ item, kind });
    setDraft(null);
    setError('');
    setNotice('');
  }

  return (
    <section className="panel registry" aria-labelledby="scheduling-title">
      <div className="section-heading">
        <div>
          <h2 id="scheduling-title">Agenda e atendimentos</h2>
          <p className="muted">
            Horários da clínica: America/Fortaleza. Atendimento avulso começa no horário atual.
          </p>
        </div>
        <div className="actions">
          {canBook && (
            <button disabled={busy} onClick={() => newDraft(false)}>
              Novo agendamento
            </button>
          )}
          {isVet && (
            <button disabled={busy} onClick={() => newDraft(true)}>
              Atendimento avulso
            </button>
          )}
        </div>
      </div>
      <div className="field-pair">
        <label>
          Dia da agenda
          <input
            type="date"
            required
            value={day}
            onChange={(event) => {
              if (event.target.value) {
                setDay(event.target.value);
                setLoading(true);
                setAppointmentOffset(0);
                setEncounterOffset(0);
                setError('');
              }
            }}
          />
        </label>
        <label>
          Filtrar por veterinário
          <select
            value={vetFilter}
            onChange={(event) => {
              setVetFilter(event.target.value);
              setLoading(true);
              setAppointmentOffset(0);
              setEncounterOffset(0);
              setError('');
            }}
          >
            <option value="">Todos os veterinários</option>
            {vets.map((vet) => (
              <option key={vet.id} value={vet.id}>
                {vet.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div>
        <button className="secondary" disabled={busy || loading} onClick={refresh}>
          Atualizar agenda
        </button>
      </div>
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
      {draft && (
        <form
          className="registry-form"
          onSubmit={(event) => {
            void save(event);
          }}
        >
          <h3>
            {draft.walkIn
              ? 'Abrir atendimento avulso'
              : draft.id
                ? 'Reagendar consulta'
                : 'Cadastrar agendamento'}
          </h3>
          <label>
            Buscar paciente por nome ou microchip
            <input
              value={patientQuery}
              maxLength={100}
              onChange={(event) => setPatientQuery(event.target.value)}
            />
          </label>
          <div>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => {
                void searchPatients();
              }}
            >
              Buscar pacientes
            </button>
          </div>
          {patientSearched && (
            <p className="muted">
              {patients.length
                ? 'Até 20 resultados; refine a busca se necessário.'
                : 'Nenhum paciente encontrado.'}
            </p>
          )}
          <label>
            Paciente
            <select
              required
              value={draft.patient_id}
              onChange={(event) => {
                const found = patients.find((patient) => patient.id === event.target.value);
                setDraft({
                  ...draft,
                  patient_id: event.target.value,
                  patient_name: found?.name ?? '',
                });
              }}
            >
              <option value="">Selecione o paciente</option>
              {draft.patient_id && !patients.some((patient) => patient.id === draft.patient_id) && (
                <option value={draft.patient_id}>{draft.patient_name}</option>
              )}
              {patients.map((patient) => (
                <option key={patient.id} value={patient.id}>
                  {patient.name} · {patient.species}
                  {patient.microchip ? ` · ${patient.microchip}` : ''}
                </option>
              ))}
            </select>
          </label>
          {!draft.walkIn && (
            <>
              <label>
                Veterinário responsável
                <select
                  required
                  value={draft.veterinarian_id}
                  onChange={(event) => setDraft({ ...draft, veterinarian_id: event.target.value })}
                >
                  <option value="">Selecione o veterinário</option>
                  {draft.veterinarian_id &&
                    !vets.some((vet) => vet.id === draft.veterinarian_id) && (
                      <option value={draft.veterinarian_id} disabled>
                        Profissional indisponível — selecione outro
                      </option>
                    )}
                  {vets.map((vet) => (
                    <option key={vet.id} value={vet.id}>
                      {vet.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="field-pair">
                <label>
                  Início
                  <input
                    required
                    type="datetime-local"
                    value={draft.starts_at}
                    onChange={(event) => setDraft({ ...draft, starts_at: event.target.value })}
                  />
                </label>
                <label>
                  Fim
                  <input
                    required
                    type="datetime-local"
                    value={draft.ends_at}
                    onChange={(event) => setDraft({ ...draft, ends_at: event.target.value })}
                  />
                </label>
              </div>
              <label>
                Tipo de atendimento
                <input
                  required
                  maxLength={80}
                  value={draft.kind}
                  onChange={(event) => setDraft({ ...draft, kind: event.target.value })}
                  placeholder="Consulta, retorno, vacinação…"
                />
              </label>
            </>
          )}
          <div className="actions">
            <button disabled={busy}>
              {busy
                ? 'Salvando…'
                : draft.walkIn
                  ? 'Iniciar atendimento avulso'
                  : 'Salvar agendamento'}
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => setDraft(null)}
            >
              Cancelar edição
            </button>
          </div>
        </form>
      )}
      {action && (
        <div className="confirmation">
          <p>
            <strong>{actionLabels[action.kind]}</strong> de {action.item.patient_name}?
          </p>
          {(action.kind === 'cancelled' || action.kind === 'no_show') && (
            <p>O horário será liberado e o agendamento será preservado.</p>
          )}
          <div className="actions">
            <button
              disabled={busy}
              onClick={() => {
                void executeAction();
              }}
            >
              Confirmar operação
            </button>
            <button className="secondary" disabled={busy} onClick={() => setAction(null)}>
              Voltar
            </button>
          </div>
        </div>
      )}
      <h3>Consultas agendadas</h3>
      {loading ? (
        <p role="status">Carregando agenda…</p>
      ) : appointments.items.length === 0 ? (
        <p>Nenhum agendamento neste dia.</p>
      ) : (
        <div className="table-scroll">
          <table className="agenda">
            <thead>
              <tr>
                <th>Horário</th>
                <th>Paciente / profissional</th>
                <th>Tipo</th>
                <th>Situação</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {appointments.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    {displayDateTime(item.starts_at)}
                    <br />
                    <span className="muted">até {displayDateTime(item.ends_at)}</span>
                  </td>
                  <td>
                    {item.patient_name}
                    <br />
                    <span className="muted">{item.veterinarian_name}</span>
                  </td>
                  <td>{item.kind}</td>
                  <td>
                    <span className={`status-tag ${item.status}`}>{statusLabels[item.status]}</span>
                  </td>
                  <td>
                    <div className="actions">
                      {canBook && editable(item) && (
                        <>
                          <button className="secondary" disabled={busy} onClick={() => edit(item)}>
                            Reagendar {item.patient_name}
                          </button>
                          {item.status === 'scheduled' && (
                            <button
                              className="secondary"
                              disabled={busy}
                              onClick={() => ask(item, 'confirmed')}
                            >
                              Confirmar {item.patient_name}
                            </button>
                          )}
                          <button
                            className="secondary"
                            disabled={busy}
                            onClick={() => ask(item, 'cancelled')}
                          >
                            Cancelar {item.patient_name}
                          </button>
                          <button
                            className="secondary"
                            disabled={busy}
                            onClick={() => ask(item, 'no_show')}
                          >
                            Faltou: {item.patient_name}
                          </button>
                        </>
                      )}
                      {isVet && item.veterinarian_id === user.id && editable(item) && (
                        <button disabled={busy} onClick={() => ask(item, 'start')}>
                          Iniciar {item.patient_name}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="pagination">
        <span>{appointments.total} agendamento(s)</span>
        <div className="actions">
          <button
            className="secondary"
            disabled={loading || appointmentOffset === 0}
            onClick={() => {
              setLoading(true);
              setAppointmentOffset(Math.max(0, appointmentOffset - 20));
            }}
          >
            Consultas anteriores
          </button>
          <button
            className="secondary"
            disabled={loading || appointmentOffset + 20 >= appointments.total}
            onClick={() => {
              setLoading(true);
              setAppointmentOffset(appointmentOffset + 20);
            }}
          >
            Próximas consultas
          </button>
        </div>
      </div>
      <h3>Atendimentos iniciados neste dia</h3>
      {loading ? (
        <p role="status">Carregando atendimentos…</p>
      ) : encounters.items.length === 0 ? (
        <p>Nenhum atendimento iniciado neste dia.</p>
      ) : (
        <div className="table-scroll">
          <table className="agenda">
            <thead>
              <tr>
                <th>Paciente / profissional</th>
                <th>Abertura</th>
                <th>Situação</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {encounters.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    {item.patient_name}
                    <br />
                    <span className="muted">
                      {item.veterinarian_name} · {item.appointment_id ? 'Agendado' : 'Avulso'}
                    </span>
                  </td>
                  <td>{displayDateTime(item.started_at)}</td>
                  <td>
                    {item.completed_at
                      ? `Concluído em ${displayDateTime(item.completed_at)}`
                      : 'Em atendimento'}
                  </td>
                  <td>
                    {isVet && item.veterinarian_id === user.id && !item.completed_at && (
                      <button disabled={busy} onClick={() => ask(item, 'complete')}>
                        Concluir {item.patient_name}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="pagination">
        <span>{encounters.total} atendimento(s)</span>
        <div className="actions">
          <button
            className="secondary"
            disabled={loading || encounterOffset === 0}
            onClick={() => {
              setLoading(true);
              setEncounterOffset(Math.max(0, encounterOffset - 20));
            }}
          >
            Atendimentos anteriores
          </button>
          <button
            className="secondary"
            disabled={loading || encounterOffset + 20 >= encounters.total}
            onClick={() => {
              setLoading(true);
              setEncounterOffset(encounterOffset + 20);
            }}
          >
            Próximos atendimentos
          </button>
        </div>
      </div>
    </section>
  );
}
