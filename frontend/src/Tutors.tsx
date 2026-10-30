import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest } from './api';
import { errorMessage, parsePage, parseTutor } from './registry-api';
import type { Page, Tutor } from './registry-api';

interface Draft {
  id: string | null;
  name: string;
  phone: string;
  document: string;
  address: string;
  granted: boolean;
  source: string;
}
const empty: Draft = {
  id: null,
  name: '',
  phone: '',
  document: '',
  address: '',
  granted: false,
  source: '',
};

export function Tutors({ token, canWrite }: { token: string; canWrite: boolean }) {
  const [page, setPage] = useState<Page<Tutor>>({ items: [], total: 0 });
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('');
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [archive, setArchive] = useState<Tutor | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  useEffect(() => {
    let active = true;
    void apiRequest(token, `/tutors?q=${encodeURIComponent(filter)}&limit=20&offset=${offset}`)
      .then((body) => {
        const result = parsePage(body, parseTutor);
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
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft) return;
    setSaving(true);
    setError('');
    setNotice('');
    let persisted = false;
    try {
      const values = {
        name: draft.name.trim(),
        phone: draft.phone.trim() || null,
        document: draft.document.trim() || null,
        address: draft.address.trim() || null,
      };
      if (draft.id) {
        const updated = parseTutor(await apiRequest(token, `/tutors/${draft.id}`, values));
        persisted = true;
        if (
          draft.granted !== updated.whatsapp_opt_in ||
          (draft.granted && draft.source.trim() !== updated.whatsapp_opt_in_source)
        ) {
          await apiRequest(
            token,
            `/tutors/${draft.id}/whatsapp-consent`,
            { granted: draft.granted, source: draft.granted ? draft.source.trim() : null },
            'PUT',
          );
        }
      } else {
        await apiRequest(
          token,
          '/tutors',
          {
            ...values,
            ...(draft.granted
              ? { whatsapp_consent: { granted: true, source: draft.source.trim() } }
              : {}),
          },
          'POST',
        );
      }
      setDraft(null);
      setNotice('Cadastro do tutor salvo.');
      refresh();
    } catch (reason) {
      setError(
        `${errorMessage(reason)}${persisted ? ' O cadastro foi salvo, mas a autorização não foi atualizada.' : ''}`,
      );
    } finally {
      setSaving(false);
    }
  }
  async function confirmArchive() {
    if (!archive) return;
    setSaving(true);
    setError('');
    try {
      await apiRequest(token, `/tutors/${archive.id}`, undefined, 'DELETE');
      setArchive(null);
      setNotice('Tutor arquivado.');
      refresh();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel registry" aria-labelledby="tutors-title">
      <div className="section-heading">
        <div>
          <h2 id="tutors-title">Tutores</h2>
          <p className="muted">Pessoas responsáveis pelos pacientes da clínica.</p>
        </div>
        {canWrite && (
          <button
            onClick={() => {
              setDraft({ ...empty });
              setArchive(null);
              setError('');
              setNotice('');
            }}
          >
            Novo tutor
          </button>
        )}
      </div>
      <form className="search-form" onSubmit={search}>
        <label>
          Buscar tutor
          <input
            maxLength={100}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Nome ou telefone"
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
        <p role="status">Carregando tutores…</p>
      ) : page.items.length === 0 ? (
        <p>Nenhum tutor encontrado.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Telefone</th>
                <th>WhatsApp</th>
                {canWrite && <th>Ações</th>}
              </tr>
            </thead>
            <tbody>
              {page.items.map((item) => (
                <tr key={item.id}>
                  <td>{item.name}</td>
                  <td>{item.phone ?? 'Não informado'}</td>
                  <td>{item.whatsapp_opt_in ? 'Autorizado' : 'Sem autorização'}</td>
                  {canWrite && (
                    <td>
                      <div className="actions">
                        <button
                          className="secondary"
                          aria-label={`Editar tutor ${item.name}`}
                          onClick={() => {
                            setDraft({
                              id: item.id,
                              name: item.name,
                              phone: item.phone ?? '',
                              document: item.document ?? '',
                              address: item.address ?? '',
                              granted: item.whatsapp_opt_in,
                              source: item.whatsapp_opt_in_source ?? '',
                            });
                            setArchive(null);
                            setError('');
                          }}
                        >
                          Editar
                        </button>
                        <button
                          className="secondary"
                          aria-label={`Arquivar tutor ${item.name}`}
                          onClick={() => {
                            setArchive(item);
                            setDraft(null);
                            setError('');
                          }}
                        >
                          Arquivar
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="pagination">
        <span>{page.total} tutor(es)</span>
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
            Arquivar <strong>{archive.name}</strong>? O cadastro e os vínculos serão preservados, e
            a autorização de WhatsApp será revogada.
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
          <h3>{draft.id ? 'Editar tutor' : 'Cadastrar tutor'}</h3>
          <div className="field-pair">
            <label>
              Nome do tutor
              <input
                required
                maxLength={200}
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
            </label>
            <label>
              Telefone com DDD
              <input
                type="tel"
                required={draft.granted}
                maxLength={40}
                value={draft.phone}
                onChange={(e) =>
                  setDraft({ ...draft, phone: e.target.value, granted: false, source: '' })
                }
              />
            </label>
          </div>
          <label>
            Documento (opcional)
            <input
              maxLength={30}
              value={draft.document}
              onChange={(e) => setDraft({ ...draft, document: e.target.value })}
            />
          </label>
          <label>
            Endereço (opcional)
            <textarea
              maxLength={500}
              rows={2}
              value={draft.address}
              onChange={(e) => setDraft({ ...draft, address: e.target.value })}
            />
          </label>
          <fieldset>
            <legend>Comunicação por WhatsApp</legend>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={draft.granted}
                onChange={(e) => setDraft({ ...draft, granted: e.target.checked })}
              />
              O tutor autorizou receber mensagens
            </label>
            <p className="muted">
              Registre apenas uma autorização recebida do tutor. Trocar o telefone exige nova
              autorização.
            </p>
            {draft.granted && (
              <label>
                Origem da autorização
                <input
                  required
                  maxLength={200}
                  placeholder="Ex.: autorização presencial"
                  value={draft.source}
                  onChange={(e) => setDraft({ ...draft, source: e.target.value })}
                />
              </label>
            )}
          </fieldset>
          <div className="actions">
            <button disabled={saving}>{saving ? 'Salvando…' : 'Salvar tutor'}</button>
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
    </section>
  );
}
