import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest, parseIdentity, roleLabels } from './api';
import type { Identity } from './api';
import { defaultAuth } from './auth';
import type { AuthGateway, AuthSession } from './auth';
import { HealthStatus } from './HealthStatus';
import { UserAdministration } from './UserAdministration';

export function App({ auth = defaultAuth }: { auth?: AuthGateway | null }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
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

  return (
    <div className="page">
      <header className="header">
        <a className="brand" href="/" aria-label="Sistema Veterinário — início">
          <span className="brand-mark" aria-hidden="true">
            +
          </span>
          Sistema Veterinário
        </a>
        <div className="header-actions">
          <span className="environment">Desenvolvimento local</span>
          {session && (
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
          )}
        </div>
      </header>
      <main className={identity ? 'workspace' : 'login-layout'}>
        {error && (
          <p role="alert" className="form-error full-width">
            {error}
          </p>
        )}
        {loading ? (
          <section className="panel full-width">
            <h1>Preparando seu acesso</h1>
            <p role="status">Carregando sua clínica…</p>
          </section>
        ) : identity && session ? (
          <>
            <section className="workspace-heading">
              <p className="eyebrow">SUA CLÍNICA</p>
              <h1>{identity.clinic.name}</h1>
              <p>
                Olá, {identity.user.name}.{' '}
                <span className="role-tag">{roleLabels[identity.user.role]}</span>
              </p>
            </section>
            {identity.user.role === 'admin' ? (
              <>
                <section className="panel">
                  <h2>Dados da clínica</h2>
                  <form
                    className="clinic-form"
                    key={identity.clinic.name}
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
                        defaultValue={identity.clinic.name}
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
            )}
          </>
        ) : !session ? (
          <>
            <section className="welcome">
              <p className="eyebrow">MAIS TEMPO PARA CUIDAR</p>
              <h1>O cuidado começa com uma rotina mais simples.</h1>
              <p className="intro">Acesse o espaço da sua clínica para organizar a equipe.</p>
            </section>
            <section className="panel login-panel">
              <h2>Entre na sua clínica</h2>
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
          </>
        ) : (
          <section className="panel full-width">
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
