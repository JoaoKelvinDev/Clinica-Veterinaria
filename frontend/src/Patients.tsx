import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest } from './api';
import { PatientTutors } from './PatientTutors';
import { errorMessage, parsePage, parsePatient } from './registry-api';
import type { Page, Patient } from './registry-api';

interface Draft {
  id: string | null;
  name: string;
  species: string;
  breed: string;
  sex: Patient['sex'];
  neutered: '' | 'yes' | 'no';
  birth_date: string;
  estimated_age_months: string;
  coat: string;
  microchip: string;
  notes: string;
}
const empty: Draft = {
  id: null,
  name: '',
  species: '',
  breed: '',
  sex: 'unknown',
  neutered: '',
  birth_date: '',
  estimated_age_months: '',
  coat: '',
  microchip: '',
  notes: '',
};

export function Patients({ token, canWrite }: { token: string; canWrite: boolean }) {
  const [page, setPage] = useState<Page<Patient>>({ items: [], total: 0 });
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('');
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [archive, setArchive] = useState<Patient | null>(null);
  const [selected, setSelected] = useState<Patient | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  useEffect(() => {
    let active = true;
    void apiRequest(token, `/patients?q=${encodeURIComponent(filter)}&limit=20&offset=${offset}`)
      .then((body) => {
        const result = parsePage(body, parsePatient);
        if (active) setPage(result);
      })
      .catch((reason: unknown) => {
        if (active) setError(errorMessage(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, filter, offset, revision]);
  function refresh() {
    setLoading(true);
    setRevision((current) => current + 1);
  }
  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setNotice('');
    setLoading(true);
    setOffset(0);
    setFilter(query.trim());
    setRevision((current) => current + 1);
  }
  function edit(item: Patient) {
    setDraft({
      ...item,
      breed: item.breed ?? '',
      neutered: item.neutered === null ? '' : item.neutered ? 'yes' : 'no',
      birth_date: item.birth_date ?? '',
      estimated_age_months:
        item.estimated_age_months === null ? '' : String(item.estimated_age_months),
      coat: item.coat ?? '',
      microchip: item.microchip ?? '',
      notes: item.notes ?? '',
    });
    setArchive(null);
    setSelected(null);
    setError('');
    setNotice('');
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const values = {
        name: draft.name.trim(),
        species: draft.species.trim(),
        breed: draft.breed.trim() || null,
        sex: draft.sex,
        neutered: draft.neutered === '' ? null : draft.neutered === 'yes',
        birth_date: draft.birth_date || null,
        estimated_age_months:
          draft.estimated_age_months === '' ? null : Number(draft.estimated_age_months),
        coat: draft.coat.trim() || null,
        microchip: draft.microchip.trim() || null,
        notes: draft.notes.trim() || null,
      };
      const result = parsePatient(
        await apiRequest(
          token,
          draft.id ? `/patients/${draft.id}` : '/patients',
          values,
          draft.id ? 'PATCH' : 'POST',
        ),
      );
      setDraft(null);
      setSelected(result);
      setNotice('Cadastro do paciente salvo. Vincule os tutores abaixo.');
      refresh();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setSaving(false);
    }
  }
  async function confirmArchive() {
    if (!archive) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      await apiRequest(token, `/patients/${archive.id}`, undefined, 'DELETE');
      setArchive(null);
      setSelected(null);
      setNotice('Paciente arquivado.');
      refresh();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setSaving(false);
    }
  }
  return (
    <section className="panel registry" aria-labelledby="patients-title">
      <div className="section-heading">
        <div>
          <h2 id="patients-title">Animais</h2>
          <p className="muted">Pacientes e seus responsáveis.</p>
        </div>
        {canWrite && (
          <button
            onClick={() => {
              setDraft({ ...empty });
              setArchive(null);
              setSelected(null);
              setError('');
              setNotice('');
            }}
          >
            Novo paciente
          </button>
        )}
      </div>
      <form className="search-form" onSubmit={search}>
        <label>
          Buscar paciente
          <input
            maxLength={100}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Nome ou microchip"
          />
        </label>
        <button className="secondary">Pesquisar</button>
      </form>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="success-message">
          {notice}
        </p>
      )}
      {loading ? (
        <p role="status">Carregando pacientes…</p>
      ) : page.items.length === 0 ? (
        <p>Nenhum paciente encontrado.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Espécie / raça</th>
                <th>Microchip</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {page.items.map((item) => (
                <tr key={item.id}>
                  <td>{item.name}</td>
                  <td>
                    {item.species}
                    {item.breed ? ` / ${item.breed}` : ''}
                  </td>
                  <td>{item.microchip ?? 'Não informado'}</td>
                  <td>
                    <div className="actions">
                      <button
                        className="secondary"
                        onClick={() => {
                          setSelected(item);
                          setDraft(null);
                          setArchive(null);
                        }}
                      >
                        Tutores de {item.name}
                      </button>
                      {canWrite && (
                        <>
                          <button
                            className="secondary"
                            aria-label={`Editar paciente ${item.name}`}
                            onClick={() => edit(item)}
                          >
                            Editar
                          </button>
                          <button
                            className="secondary"
                            aria-label={`Arquivar paciente ${item.name}`}
                            onClick={() => {
                              setArchive(item);
                              setDraft(null);
                              setSelected(null);
                              setError('');
                            }}
                          >
                            Arquivar
                          </button>
                        </>
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
        <span>{page.total} paciente(s)</span>
        <div className="actions">
          <button
            className="secondary"
            disabled={loading || offset === 0}
            onClick={() => {
              setLoading(true);
              setOffset(Math.max(0, offset - 20));
            }}
          >
            Anterior
          </button>
          <button
            className="secondary"
            disabled={loading || offset + 20 >= page.total}
            onClick={() => {
              setLoading(true);
              setOffset(offset + 20);
            }}
          >
            Próxima
          </button>
        </div>
      </div>
      {archive && (
        <div className="confirmation">
          <p>
            Arquivar <strong>{archive.name}</strong>? O cadastro e os vínculos serão preservados.
          </p>
          <div className="actions">
            <button
              disabled={saving}
              onClick={() => {
                void confirmArchive();
              }}
            >
              Confirmar arquivamento
            </button>
            <button className="secondary" disabled={saving} onClick={() => setArchive(null)}>
              Cancelar
            </button>
          </div>
        </div>
      )}
      {draft && (
        <form
          className="registry-form"
          onSubmit={(event) => {
            void save(event);
          }}
        >
          <h3>{draft.id ? 'Editar paciente' : 'Cadastrar paciente'}</h3>
          <div className="field-pair">
            <label>
              Nome do paciente
              <input
                required
                maxLength={200}
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
            </label>
            <label>
              Espécie
              <input
                required
                maxLength={80}
                placeholder="Ex.: canina"
                value={draft.species}
                onChange={(e) => setDraft({ ...draft, species: e.target.value })}
              />
            </label>
          </div>
          <div className="field-pair">
            <label>
              Raça
              <input
                maxLength={120}
                value={draft.breed}
                onChange={(e) => setDraft({ ...draft, breed: e.target.value })}
              />
            </label>
            <label>
              Sexo
              <select
                value={draft.sex}
                onChange={(e) => setDraft({ ...draft, sex: e.target.value as Patient['sex'] })}
              >
                <option value="unknown">Não informado</option>
                <option value="male">Macho</option>
                <option value="female">Fêmea</option>
              </select>
            </label>
          </div>
          <label>
            Castrado
            <select
              value={draft.neutered}
              onChange={(e) =>
                setDraft({ ...draft, neutered: e.target.value as Draft['neutered'] })
              }
            >
              <option value="">Não informado</option>
              <option value="yes">Sim</option>
              <option value="no">Não</option>
            </select>
          </label>
          <div className="field-pair">
            <label>
              Data de nascimento
              <input
                type="date"
                value={draft.birth_date}
                onChange={(e) =>
                  setDraft({ ...draft, birth_date: e.target.value, estimated_age_months: '' })
                }
              />
            </label>
            <label>
              Idade estimada (meses)
              <input
                type="number"
                min={0}
                step={1}
                disabled={Boolean(draft.birth_date)}
                value={draft.estimated_age_months}
                onChange={(e) => setDraft({ ...draft, estimated_age_months: e.target.value })}
              />
            </label>
          </div>
          <p className="muted">Informe a data de nascimento ou a idade estimada, quando souber.</p>
          <div className="field-pair">
            <label>
              Pelagem
              <input
                maxLength={120}
                value={draft.coat}
                onChange={(e) => setDraft({ ...draft, coat: e.target.value })}
              />
            </label>
            <label>
              Microchip
              <input
                maxLength={50}
                value={draft.microchip}
                onChange={(e) => setDraft({ ...draft, microchip: e.target.value })}
              />
            </label>
          </div>
          <label>
            Observações cadastrais
            <textarea
              rows={3}
              maxLength={2000}
              value={draft.notes}
              onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
            />
          </label>
          <div className="actions">
            <button disabled={saving}>{saving ? 'Salvando…' : 'Salvar paciente'}</button>
            <button
              type="button"
              className="secondary"
              disabled={saving}
              onClick={() => setDraft(null)}
            >
              Cancelar edição
            </button>
          </div>
        </form>
      )}
      {selected && (
        <PatientTutors
          key={selected.id}
          patient={selected}
          token={token}
          canWrite={canWrite}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}
