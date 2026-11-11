import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest, parseIdentity, roleLabels } from './api';
import type { Identity } from './api';
import { defaultAuth } from './auth';
import type { AuthGateway, AuthSession } from './auth';
import { HealthStatus } from './HealthStatus';
import { UserAdministration } from './UserAdministration';
import { Tutors } from './Tutors';
import { Patients } from './Patients';
import { Scheduling } from './Scheduling';
import { Messaging } from './Messaging';
import { Quotes } from './Quotes';
import { Inventory } from './Inventory';
import { Financial } from './Financial';
import { ActionScreen, ScreenArea, ScreenFeedback } from './Screen';
import { focusArea } from './screen-focus';
import { Records } from './Records';
import type { RecordTarget } from './Records';

type View =
  | 'clinic'
  | 'tutors'
  | 'patients'
  | 'scheduling'
  | 'messaging'
  | 'quotes'
  | 'inventory'
  | 'financial';
const navItems: [View, string][] = [
  ['scheduling', 'Agenda'],
  ['tutors', 'Tutores'],
  ['patients', 'Animais'],
  ['messaging', 'Mensagens'],
  ['quotes', 'Orçamentos'],
  ['inventory', 'Estoque'],
  ['financial', 'Financeiro'],
  ['clinic', 'Clínica e equipe'],
];
const navPaths: Record<View, string> = {
  scheduling: 'M5 5h14v15H5z M8 2v6 M16 2v6 M5 11h14',
  tutors:
    'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M17 4a4 4 0 0 1 0 7 M22 21v-2a4 4 0 0 0-3-4',
  patients: 'M12 21s-8-5-8-11a4 4 0 0 1 8-2 4 4 0 0 1 8 2c0 6-8 11-8 11z',
  messaging: 'M4 4h16v12H9l-5 4z M8 8h8 M8 12h5',
  quotes: 'M6 3h12v18l-3-2-3 2-3-2-3 2z M9 7h6 M9 11h6 M9 15h3',
  inventory: 'M3 7l9-4 9 4v10l-9 4-9-4z M3 7l9 4 9-4 M12 11v10',
  financial: 'M4 20h16 M7 16v-5 M12 16V5 M17 16V8',
  clinic: 'M4 21V5h16v16 M2 21h20 M9 21v-6h6v6 M9 8h6 M12 5v6',
};

export function App({ auth = defaultAuth }: { auth?: AuthGateway | null }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [clinicNotice, setClinicNotice] = useState('');
  const [editingClinic, setEditingClinic] = useState(false);
  // A agenda é a rotina diária de todos os papéis; por isso é a tela inicial.
  const [view, setView] = useState<View>('scheduling');
  const [recordTarget, setRecordTarget] = useState<RecordTarget | null>(null);
  const revision = useRef(0);
  const invalidateRequests = useCallback(() => {
    revision.current++;
  }, []);

  // Atualiza nome da clínica e perfil sem desmontar a tela atual (e suas mensagens).
  const refreshIdentity = useCallback(async (current: AuthSession) => {
    const request = revision.current;
    try {
      const profile = parseIdentity(await apiRequest(current.access_token, '/me'));
      if (request === revision.current) setIdentity(profile);
    } catch (reason) {
      if (request === revision.current) {
        setIdentity(null);
        setError(
          reason instanceof Error ? reason.message : 'Não foi possível carregar seu acesso.',
        );
      }
    }
  }, []);

  const applySession = useCallback(async (next: AuthSession | null) => {
    const current = ++revision.current;
    setSession(next);
    setIdentity(null);
    setLoading(true);
    setError('');
    try {
      if (next) {
        const profile = parseIdentity(await apiRequest(next.access_token, '/me'));
        if (current === revision.current) setIdentity(profile);
      }
    } catch (reason) {
      if (current === revision.current)
        setError(
          reason instanceof Error ? reason.message : 'Não foi possível carregar seu acesso.',
        );
    } finally {
      if (current === revision.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const unsubscribe = auth?.subscribe((next) => {
      if (active) void applySession(next);
    });
    void (auth?.getSession() ?? Promise.resolve(null))
      .then((next) => {
        if (active) void applySession(next);
      })
      .catch(() => {
        if (active) {
          setError('Não foi possível recuperar a sessão.');
          setLoading(false);
        }
      });
    return () => {
      active = false;
      invalidateRequests();
      unsubscribe?.();
    };
  }, [auth, applySession, invalidateRequests]);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!auth) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError('');
    try {
      const next = await auth.signIn(
        String(data.get('email')).trim(),
        String(data.get('password')),
      );
      form.reset();
      await applySession(next);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Não foi possível entrar.');
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    if (!auth) return;
    setBusy(true);
    setError('');
    try {
      await auth.signOut();
      setView('scheduling');
      setRecordTarget(null);
      await applySession(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Não foi possível sair.');
    } finally {
      setBusy(false);
    }
  }

  async function renameClinic(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) return;
    const name = String(new FormData(event.currentTarget).get('clinicName')).trim();
    setBusy(true);
    setError('');
    setClinicNotice('');
    try {
      await apiRequest(session.access_token, '/clinic', { name });
      await refreshIdentity(session);
      setClinicNotice('Nome da clínica salvo.');
      setEditingClinic(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Não foi possível salvar.');
    } finally {
      setBusy(false);
    }
  }

  const brand = (
    <a className="brand" href="/" aria-label="Sistema Veterinário — início">
      <span className="brand-mark" aria-hidden="true">
        +
      </span>
      Sistema Veterinário
    </a>
  );
  const logoutButton = session && (
    <button
      type="button"
      className="secondary"
      disabled={busy}
      onClick={() => {
        void logout();
      }}
    >
      Sair
    </button>
  );
  const errorMessage = error && (
    <p role="alert" className="form-error">
      {error}
    </p>
  );

  if (!loading && identity && session) {
    const { user, clinic } = identity;
    return (
      <div className="shell">
        <aside className="sidebar">
          {brand}
          <div className="identity">
            <h1>{clinic.name}</h1>
            <p>
              {user.name}
              <span className="role-tag">{roleLabels[user.role]}</span>
            </p>
            {user.crmv && (
              <span className="stamp crmv">
                CRMV-{user.crmv_state} {user.crmv}
              </span>
            )}
          </div>
          <nav className="workspace-nav" aria-label="Áreas da clínica">
            {navItems
              .filter(
                ([key]) =>
                  key !== 'financial' || user.role === 'admin' || user.role === 'reception',
              )
              .map(([key, label]) => (
                <button
                  key={key}
                  className="nav-item"
                  aria-current={view === key ? 'page' : undefined}
                  onClick={() => {
                    setView(key);
                    setRecordTarget(null);
                    setEditingClinic(false);
                  }}
                >
                  <svg
                    className="nav-icon"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.7"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d={navPaths[key]} />
                  </svg>
                  {key === 'clinic' && user.role !== 'admin' ? 'Meu acesso' : label}
                </button>
              ))}
          </nav>
          <div className="sidebar-foot">
            {logoutButton}
            <span className="environment">Desenvolvimento local</span>
            <HealthStatus />
          </div>
        </aside>
        <main className="workspace">
          <ScreenArea>
            <div className="area-view" key={view} ref={focusArea}>
              {errorMessage}
              {recordTarget && (
                <Records
                  token={session.access_token}
                  user={user}
                  target={recordTarget}
                  onClose={() => setRecordTarget(null)}
                />
              )}
              {view === 'scheduling' && (
                <Scheduling
                  token={session.access_token}
                  user={user}
                  onOpenRecord={setRecordTarget}
                />
              )}
              {view === 'messaging' && <Messaging token={session.access_token} user={user} />}
              {view === 'quotes' && <Quotes token={session.access_token} user={user} />}
              {view === 'tutors' && (
                <Tutors
                  token={session.access_token}
                  canWrite={user.role === 'admin' || user.role === 'reception'}
                />
              )}
              {view === 'patients' && (
                <Patients
                  token={session.access_token}
                  canWrite={user.role === 'admin' || user.role === 'reception'}
                  onOpenRecord={setRecordTarget}
                />
              )}
              {view === 'inventory' && <Inventory token={session.access_token} user={user} />}
              {view === 'financial' && <Financial token={session.access_token} user={user} />}
              {view === 'clinic' &&
                (user.role === 'admin' ? (
                  <>
                    <section className="panel">
                      <div className="section-heading">
                        <div>
                          <h2>Dados da clínica</h2>
                          <p className="muted">{clinic.name}</p>
                        </div>
                        <button onClick={() => setEditingClinic(true)}>
                          Editar dados da clínica
                        </button>
                      </div>
                      {editingClinic && (
                        <ActionScreen
                          title="Editar dados da clínica"
                          onBack={() => setEditingClinic(false)}
                          busy={busy}
                          error={error}
                          notice={clinicNotice}
                        >
                          <form
                            className="clinic-form"
                            key={clinic.name}
                            onSubmit={(event) => {
                              void renameClinic(event);
                            }}
                          >
                            <label>
                              Nome da clínica
                              <input
                                name="clinicName"
                                required
                                maxLength={200}
                                defaultValue={clinic.name}
                              />
                            </label>
                            <button disabled={busy}>Salvar nome</button>
                          </form>
                        </ActionScreen>
                      )}
                      <ScreenFeedback notice={clinicNotice} />
                    </section>
                    <UserAdministration
                      token={session.access_token}
                      onIdentityChanged={() => {
                        void refreshIdentity(session);
                      }}
                    />
                  </>
                ) : (
                  <section className="panel">
                    <h2>Seu acesso</h2>
                    <dl className="profile">
                      <div>
                        <dt>Clínica</dt>
                        <dd>{clinic.name}</dd>
                      </div>
                      <div>
                        <dt>Nome</dt>
                        <dd>{user.name}</dd>
                      </div>
                      <div>
                        <dt>Papel</dt>
                        <dd>{roleLabels[user.role]}</dd>
                      </div>
                      {user.crmv && (
                        <div>
                          <dt>CRMV</dt>
                          <dd>
                            {user.crmv_state} {user.crmv}
                          </dd>
                        </div>
                      )}
                    </dl>
                    <p className="muted">
                      Para corrigir esses dados ou o acesso de outra pessoa, fale com o
                      administrador da clínica.
                    </p>
                  </section>
                ))}
            </div>
          </ScreenArea>
        </main>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="header">
        {brand}
        <div className="header-actions">
          <span className="environment">Desenvolvimento local</span>
          {logoutButton}
        </div>
      </header>
      <main className="entry">
        {errorMessage}
        {loading ? (
          <section className="panel">
            <h1>Preparando seu acesso</h1>
            <p role="status">Carregando sua clínica…</p>
          </section>
        ) : !session ? (
          <section className="panel login-panel">
            <h1>Entre na sua clínica</h1>
            <p className="intro">Agenda, tutores e pacientes da sua equipe em um só lugar.</p>
            {!auth && <p role="alert">O acesso ainda não está configurado neste ambiente.</p>}
            <form
              onSubmit={(event) => {
                void login(event);
              }}
            >
              <label>
                E-mail
                <input
                  name="email"
                  type="email"
                  autoComplete="username"
                  required
                  disabled={!auth || busy}
                />
              </label>
              <label>
                Senha
                <input
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  disabled={!auth || busy}
                />
              </label>
              <button disabled={!auth || busy}>{busy ? 'Entrando…' : 'Entrar'}</button>
            </form>
            <p className="muted">Acesso exclusivo à equipe da clínica.</p>
          </section>
        ) : (
          <section className="panel">
            <h1>Acesso indisponível</h1>
            <p>Consulte o administrador da sua clínica para verificar seu cadastro.</p>
          </section>
        )}
      </main>
      <footer>
        <span>Feito para clínicas veterinárias no Brasil.</span>
        <HealthStatus />
      </footer>
    </div>
  );
}
