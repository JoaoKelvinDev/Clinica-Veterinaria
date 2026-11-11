import { useId, useState } from 'react';
import type { FormEventHandler, ReactNode } from 'react';
import { HealthStatus } from './HealthStatus';
import { environmentLabel, isDemonstration } from './environment';
import hero from './assets/vet-hero.jpg';
import './login-screen.css';

type IconName = 'paw' | 'mail' | 'lock' | 'eye' | 'eye-off' | 'calendar' | 'heart' | 'care';

const iconPaths: Record<IconName, string> = {
  paw: 'M8 14c-1 2-4 3-3 5s4 1 7 1 6 1 7-1-2-3-3-5c-2-3-6-3-8 0 M5 6a1.5 2.5 0 1 0 0 5 1.5 2.5 0 1 0 0-5 M10 2a1.5 2.5 0 1 0 0 5 1.5 2.5 0 1 0 0-5 M15 2a1.5 2.5 0 1 0 0 5 1.5 2.5 0 1 0 0-5 M20 6a1.5 2.5 0 1 0 0 5 1.5 2.5 0 1 0 0-5',
  mail: 'M3 5h18v14H3z M3 6l9 7 9-7',
  lock: 'M5 10h14v11H5z M8 10V6a4 4 0 0 1 8 0v4 M12 14v3',
  eye: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12 M15 12a3 3 0 1 1-6 0 3 3 0 1 1 6 0',
  'eye-off':
    'M3 3l18 18 M9 5a11 11 0 0 1 3 0c6 0 10 7 10 7a20 20 0 0 1-3 4 M6 6a22 22 0 0 0-4 6s4 7 10 7a12 12 0 0 0 5-1 M10 10a3 3 0 0 0 4 4',
  calendar: 'M4 5h16v16H4z M8 2v6 M16 2v6 M4 11h16 M8 15h2 M14 15h2',
  heart: 'M12 21S2 15 2 8a5 5 0 0 1 10-2 5 5 0 0 1 10 2c0 7-10 13-10 13z',
  care: 'M5 3v5a5 5 0 0 0 10 0V3 M3 3h4 M13 3h4 M10 13v3a5 5 0 0 0 10 0v-3 M22 11a2 2 0 1 1-4 0 2 2 0 1 1 4 0',
};

function LoginIcon({ name }: { name: IconName }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={iconPaths[name]} />
    </svg>
  );
}

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? 'Bom dia' : hour < 18 ? 'Boa tarde' : 'Boa noite';
}

interface LoginScreenProps {
  configured: boolean;
  loading: boolean;
  busy: boolean;
  hasSession: boolean;
  error: string;
  sessionAction: ReactNode;
  onSubmit: FormEventHandler<HTMLFormElement>;
}

export function LoginScreen({
  configured,
  loading,
  busy,
  hasSession,
  error,
  sessionAction,
  onSubmit,
}: LoginScreenProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [salutation] = useState(greeting);
  const id = useId();
  const message =
    error || (!configured ? 'O acesso ainda não está configurado neste ambiente.' : '');

  return (
    <div className="login-screen">
      <div className="login-main-panel">
        <div className="login-blob login-blob-peach" aria-hidden="true" />
        <div className="login-blob login-blob-mint" aria-hidden="true" />
        <div className="login-floating-paw" aria-hidden="true">
          <LoginIcon name="paw" />
        </div>
        <header className="login-header">
          <a href="/" className="login-brand" aria-label="Sistema Veterinário — início">
            <span className="login-brand-mark">
              <LoginIcon name="paw" />
            </span>
            <span>Sistema Veterinário</span>
          </a>
        </header>

        <div className="login-mobile-visual">
          <img
            src={hero}
            alt="Veterinária com um filhote e um gato"
            width={1024}
            height={1280}
            fetchPriority="high"
          />
          <div className="login-photo-overlay" />
          <p>Cuidar de quem cuida dos pets. 💚</p>
        </div>

        <main className="login-content">
          <p className="login-greeting">
            <span aria-hidden="true">🐾</span> {salutation}, equipe!
          </p>
          {loading ? (
            <section className="login-access-state" aria-labelledby={`${id}-title`}>
              <h1 id={`${id}-title`}>Preparando seu acesso</h1>
              <p role="status">Carregando sua clínica…</p>
            </section>
          ) : hasSession ? (
            <section className="login-access-state" aria-labelledby={`${id}-title`}>
              <h1 id={`${id}-title`}>Acesso indisponível</h1>
              <p>Consulte o administrador da sua clínica para verificar seu cadastro.</p>
              {message && (
                <p role="alert" className="login-error">
                  {message}
                </p>
              )}
              {sessionAction}
            </section>
          ) : (
            <section aria-labelledby={`${id}-title`}>
              <h1 id={`${id}-title`}>Entre na sua clínica</h1>
              <p className="login-intro">
                Cada patinha bem cuidada começa aqui. Agenda, tutores e pacientes em um só lugar.
              </p>
              {isDemonstration && (
                <p className="login-demo-notice" role="note">
                  Demonstração — dados fictícios. Os serviços de IA e WhatsApp são simulados.
                </p>
              )}
              <form className="login-form" onSubmit={onSubmit} aria-busy={busy}>
                <div className="login-field">
                  <label htmlFor={`${id}-email`}>E-mail</label>
                  <div className="login-input-wrap">
                    <LoginIcon name="mail" />
                    <input
                      id={`${id}-email`}
                      name="email"
                      type="email"
                      autoComplete="username"
                      autoCapitalize="none"
                      spellCheck={false}
                      placeholder="seuemail@clinica.com"
                      required
                      disabled={!configured || busy}
                      aria-describedby={message ? `${id}-error` : undefined}
                    />
                  </div>
                </div>
                <div className="login-field">
                  <label htmlFor={`${id}-password`}>Senha</label>
                  <div className="login-input-wrap">
                    <LoginIcon name="lock" />
                    <input
                      id={`${id}-password`}
                      className="login-password-input"
                      name="password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password"
                      placeholder="Digite sua senha"
                      required
                      disabled={!configured || busy}
                      aria-describedby={message ? `${id}-error` : undefined}
                    />
                    <button
                      className="login-password-toggle"
                      type="button"
                      disabled={!configured || busy}
                      aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                      aria-controls={`${id}-password`}
                      aria-pressed={showPassword}
                      onClick={() => setShowPassword((current) => !current)}
                    >
                      <LoginIcon name={showPassword ? 'eye-off' : 'eye'} />
                    </button>
                  </div>
                </div>
                {message && (
                  <p id={`${id}-error`} role="alert" className="login-error">
                    {message}
                  </p>
                )}
                <button className="login-submit" type="submit" disabled={!configured || busy}>
                  {busy && <span className="login-spinner" aria-hidden="true" />}
                  {busy ? 'Entrando…' : 'Entrar'}
                </button>
              </form>
              <div className="login-team-note">
                <span className="login-pet-icons" aria-hidden="true">
                  <span>🐶</span>
                  <span>🐱</span>
                  <span>🐰</span>
                  <span>🐦</span>
                </span>
                <p>
                  Uma rotina mais leve para <strong>sua equipe.</strong>
                </p>
              </div>
              <p className="login-exclusive">Acesso exclusivo à equipe da clínica.</p>
            </section>
          )}
        </main>

        <footer className="login-footer">
          <HealthStatus />
          <span>{environmentLabel}</span>
        </footer>
      </div>

      <aside className="login-visual" aria-label="Cuidado veterinário">
        <img
          src={hero}
          alt="Veterinária sorrindo com um filhote e um gato"
          width={1024}
          height={1280}
          fetchPriority="high"
        />
        <div className="login-photo-overlay" />
        <div className="login-photo-card login-routine-card">
          <span className="login-card-icon">
            <LoginIcon name="calendar" />
          </span>
          <div>
            <strong>Rotina organizada</strong>
            <p>Agenda, consultas e retornos</p>
          </div>
        </div>
        <div className="login-photo-card login-care-card">
          <LoginIcon name="heart" /> Mais tempo para cuidar
        </div>
        <div className="login-photo-caption">
          <h2>Cuidar de quem cuida dos pets. 💚</h2>
          <ul className="login-feature-list">
            <li>
              <LoginIcon name="calendar" /> Agenda do dia
            </li>
            <li>
              <LoginIcon name="care" /> Prontuário do paciente
            </li>
            <li>
              <LoginIcon name="paw" /> Lembretes da clínica
            </li>
          </ul>
        </div>
      </aside>
    </div>
  );
}
