import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest, parseUser, roleLabels } from './api';
import type { Role, UserProfile } from './api';

export function UserAdministration({
  token,
  onIdentityChanged,
}: {
  token: string;
  onIdentityChanged: () => void;
}) {
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [editing, setEditing] = useState<UserProfile | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    let active = true;
    void apiRequest(token, '/users')
      .then((body) => {
        if (!Array.isArray(body)) throw new Error('Lista de usuários inválida.');
        const parsed = body.map(parseUser);
        if (active) setUsers(parsed);
      })
      .catch(() => {
        if (active) setError('Não foi possível carregar os usuários.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const updated = parseUser(
        await apiRequest(token, `/users/${editing.id}`, {
          name: editing.name,
          role: editing.role,
          active: editing.active,
          crmv: editing.crmv?.trim() || null,
          crmv_state: editing.crmv_state?.trim() || null,
        }),
      );
      setUsers((current) => current.map((user) => (user.id === updated.id ? updated : user)));
      setEditing(null);
      setNotice(`Alterações de ${updated.name} salvas.`);
      onIdentityChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Não foi possível salvar.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="users-title">
      <h2 id="users-title">Equipe da clínica</h2>
      {loading && <p role="status">Carregando usuários…</p>}
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
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Nome</th>
              <th>Função</th>
              <th>CRMV</th>
              <th>Status</th>
              <th>Ação</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.name}</td>
                <td>{roleLabels[user.role]}</td>
                <td>{user.crmv ? `CRMV-${user.crmv_state ?? ''} ${user.crmv}` : '—'}</td>
                <td>{user.active ? 'Ativo' : 'Inativo'}</td>
                <td>
                  <button
                    type="button"
                    className="secondary"
                    aria-label={`Editar ${user.name}`}
                    onClick={() => {
                      setEditing({ ...user });
                      setError('');
                      setNotice('');
                    }}
                  >
                    Editar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && (
        <form
          className="edit-form"
          onSubmit={(event) => {
            void save(event);
          }}
        >
          <h3>Editar usuário</h3>
          <label>
            Nome
            <input
              required
              maxLength={200}
              value={editing.name}
              onChange={(e) => setEditing({ ...editing, name: e.target.value })}
            />
          </label>
          <label>
            Função
            <select
              value={editing.role}
              onChange={(e) => setEditing({ ...editing, role: e.target.value as Role })}
            >
              {Object.entries(roleLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <div className="field-pair">
            <label>
              CRMV
              <input
                maxLength={30}
                required={editing.role === 'veterinarian'}
                value={editing.crmv ?? ''}
                onChange={(e) => setEditing({ ...editing, crmv: e.target.value })}
              />
            </label>
            <label>
              UF do CRMV
              <input
                maxLength={2}
                required={editing.role === 'veterinarian'}
                value={editing.crmv_state ?? ''}
                onChange={(e) =>
                  setEditing({ ...editing, crmv_state: e.target.value.toUpperCase() })
                }
              />
            </label>
          </div>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={editing.active}
              onChange={(e) => setEditing({ ...editing, active: e.target.checked })}
            />
            Usuário ativo
          </label>
          <div className="actions">
            <button disabled={saving}>{saving ? 'Salvando…' : 'Salvar alterações'}</button>
            <button
              disabled={saving}
              type="button"
              className="secondary"
              onClick={() => setEditing(null)}
            >
              Cancelar
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
