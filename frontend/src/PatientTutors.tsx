import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest } from './api';
import { errorMessage, parseLinks, parsePage, parseTutor } from './registry-api';
import type { Patient, Tutor, TutorLink } from './registry-api';

export function PatientTutors({
  patient,
  token,
  canWrite,
  onClose,
}: {
  patient: Patient;
  token: string;
  canWrite: boolean;
  onClose: () => void;
}) {
  const [links, setLinks] = useState<TutorLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [query, setQuery] = useState('');
  const [candidates, setCandidates] = useState<Tutor[]>([]);
  const [searched, setSearched] = useState(false);
  const [primary, setPrimary] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [unlink, setUnlink] = useState<Tutor | null>(null);
  useEffect(() => {
    let active = true;
    void apiRequest(token, `/patients/${patient.id}/tutors`)
      .then((body) => {
        const result = parseLinks(body);
        if (active) setLinks(result);
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
  }, [token, patient.id, revision]);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = parsePage(
        await apiRequest(token, `/tutors?q=${encodeURIComponent(query.trim())}&limit=20&offset=0`),
        parseTutor,
      );
      setCandidates(result.items);
      setSearched(true);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }
  async function link(tutor: Tutor, isPrimary: boolean) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      setLinks(
        parseLinks(
          await apiRequest(
            token,
            `/patients/${patient.id}/tutors`,
            { tutor_id: tutor.id, is_primary: isPrimary },
            'POST',
          ),
        ),
      );
      setNotice('Vínculo salvo.');
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }
  async function confirmUnlink() {
    if (!unlink) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await apiRequest(token, `/patients/${patient.id}/tutors/${unlink.id}`, undefined, 'DELETE');
      setUnlink(null);
      setLoading(true);
      setRevision((current) => current + 1);
      setNotice('Vínculo removido.');
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="registry-form" aria-labelledby="links-title">
      <div className="section-heading">
        <h3 id="links-title">Tutores de {patient.name}</h3>
        <button className="secondary" onClick={onClose}>
          Fechar vínculos
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
      {loading ? (
        <p role="status">Carregando vínculos…</p>
      ) : links.length === 0 ? (
        <p>Nenhum tutor vinculado.</p>
      ) : (
        <ul className="link-list">
          {links.map((item) => (
            <li key={item.id}>
              <div>
                <strong>{item.tutor.name}</strong>
                {item.is_primary && <span className="role-tag">Principal</span>}
                {item.tutor.deleted_at && <span className="role-tag">Arquivado</span>}
                <p className="muted">{item.tutor.phone ?? 'Telefone não informado'}</p>
              </div>
              {canWrite && (
                <div className="actions">
                  {!item.is_primary && !item.tutor.deleted_at && (
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => {
                        void link(item.tutor, true);
                      }}
                    >
                      Definir {item.tutor.name} como principal
                    </button>
                  )}
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => setUnlink(item.tutor)}
                  >
                    Remover vínculo com {item.tutor.name}
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {unlink && (
        <div className="confirmation">
          <p>
            Remover o vínculo com <strong>{unlink.name}</strong>? Se era o principal, escolha outro
            responsável depois.
          </p>
          <div className="actions">
            <button
              disabled={busy}
              onClick={() => {
                void confirmUnlink();
              }}
            >
              Confirmar remoção do vínculo
            </button>
            <button className="secondary" disabled={busy} onClick={() => setUnlink(null)}>
              Cancelar remoção
            </button>
          </div>
        </div>
      )}
      {canWrite && (
        <>
          <form
            className="search-form"
            onSubmit={(event) => {
              void search(event);
            }}
          >
            <label>
              Buscar tutor para vincular
              <input
                maxLength={100}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Nome ou telefone"
              />
            </label>
            <button className="secondary" disabled={busy}>
              Buscar tutores
            </button>
          </form>
          <p className="muted">
            Até 20 resultados. Refine a busca se necessário. O primeiro tutor será o principal.
          </p>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={primary}
              onChange={(event) => setPrimary(event.target.checked)}
            />
            Definir novo vínculo como principal
          </label>
          {searched &&
            candidates.filter((candidate) => !links.some((item) => item.tutor.id === candidate.id))
              .length === 0 && <p>Nenhum novo tutor encontrado para vincular.</p>}
          <ul className="link-list">
            {candidates
              .filter((candidate) => !links.some((item) => item.tutor.id === candidate.id))
              .map((candidate) => (
                <li key={candidate.id}>
                  <span>
                    {candidate.name} · {candidate.phone ?? 'Sem telefone'}
                  </span>
                  <button
                    className="secondary"
                    disabled={busy || loading}
                    onClick={() => {
                      void link(candidate, primary);
                    }}
                  >
                    Vincular {candidate.name}
                  </button>
                </li>
              ))}
          </ul>
        </>
      )}
    </section>
  );
}
