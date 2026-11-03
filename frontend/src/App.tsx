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

type View = 'clinic' | 'tutors' | 'patients' | 'scheduling';
const navItems: [View, string][] = [
  ['scheduling', 'Agenda'],
  ['tutors', 'Tutores'],
  ['patients', 'Animais'],
  ['clinic', 'Clínica e equipe'],
];

export function App({ auth = defaultAuth }: { auth?: AuthGateway | null }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [view, setView] = useState<View>('clinic');
  const revision = useRef(0);
  const invalidateRequests = useCallback(() => {
    revision.current++;
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
      setView('clinic');
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
    try {
      await apiRequest(session.access_token, '/clinic', { name });
      await applySession(session);
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
            {navItems.map(([key, label]) => (
              <button
                key={key}
                className="nav-item"
                aria-current={view === key ? 'page' : undefined}
                onClick={() => setView(key)}
              >
                {label}
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
          {errorMessage}
          {view === 'scheduling' && <Scheduling token={session.access_token} user={user} />}
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
            />
          )}
          {view === 'clinic' &&
            (user.role === 'admin' ? (
              <>
                <section className="panel">
                  <h2>Dados da clínica</h2>
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
                </section>
                <UserAdministration
                  token={session.access_token}
                  onIdentityChanged={() => {
                    void applySession(session);
                  }}
                />
              </>
            ) : (
              <section className="panel">
                <h2>Bem-vindo à sua clínica</h2>
                <p>
                  Seu acesso está ativo. As funcionalidades de atendimento serão disponibilizadas
                  nas próximas etapas.
                </p>
              </section>
            ))}
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
