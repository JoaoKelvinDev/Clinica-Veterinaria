import {
  createContext,
  useCallback,
  useContext,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';

type Entry = { id: string; depth: number };
type Navigation = {
  host: HTMLDivElement | null;
  active: string | null;
  register: (entry: Entry) => () => void;
};
const NavigationContext = createContext<Navigation | null>(null);
const DepthContext = createContext(0);

/** Mantém a tela de origem montada: voltar não perde filtros ou campos da lista. */
export function ScreenArea({ children }: { children: ReactNode }) {
  const parent = useContext(NavigationContext);
  return parent ? children : <ScreenProvider>{children}</ScreenProvider>;
}

function ScreenProvider({ children }: { children: ReactNode }) {
  const [host, setHost] = useState<HTMLDivElement | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const origin = useRef<{ node: HTMLElement | null; top: number; left: number } | null>(null);
  const background = useRef<HTMLDivElement>(null);
  const register = useCallback((entry: Entry) => {
    if (origin.current === null)
      origin.current = {
        node: document.activeElement instanceof HTMLElement ? document.activeElement : null,
        top: window.scrollY,
        left: window.scrollX,
      };
    setEntries((current) => [...current.filter((item) => item.id !== entry.id), entry]);
    return () => setEntries((current) => current.filter((item) => item.id !== entry.id));
  }, []);
  const active =
    entries.reduce<Entry | null>(
      (current, item) => (!current || item.depth >= current.depth ? item : current),
      null,
    )?.id ?? null;
  useLayoutEffect(() => {
    if (active !== null || origin.current === null) return;
    const previous = origin.current;
    origin.current = null;
    const target =
      previous.node?.isConnected && previous.node !== document.body
        ? previous.node
        : background.current?.querySelector<HTMLElement>('h2, h3');
    if (target) {
      if (!target.matches('button, input, select, textarea, a[href]'))
        target.setAttribute('tabindex', '-1');
      target.focus({ preventScroll: true });
    }
    window.scrollTo({ top: previous.top, left: previous.left, behavior: 'instant' });
  }, [active]);
  return (
    <NavigationContext.Provider value={{ host, active, register }}>
      <div
        ref={background}
        className="screen-background"
        hidden={active !== null}
        inert={active !== null}
      >
        {children}
      </div>
      <div ref={setHost} className="screen-outlet" />
    </NavigationContext.Provider>
  );
}

export function ScreenFeedback({
  error,
  notice,
}: {
  error?: string | undefined;
  notice?: string | undefined;
}) {
  const navigation = useContext(NavigationContext);
  const owner = useContext(OwnerContext);
  if (navigation && navigation.active !== owner) return null;
  return (
    <>
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
    </>
  );
}
const OwnerContext = createContext<string | null>(null);

export function ActionScreen({
  title,
  onBack,
  busy = false,
  error,
  notice,
  children,
  layer = 0,
}: {
  title: ReactNode;
  onBack: () => void;
  busy?: boolean;
  error?: string | undefined;
  notice?: string | undefined;
  children: ReactNode;
  layer?: number;
}) {
  const navigation = useContext(NavigationContext);
  const depth = useContext(DepthContext);
  const id = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  const register = navigation?.register;
  useLayoutEffect(() => register?.({ id, depth: depth + layer }), [register, id, depth, layer]);
  const active = navigation?.active === id;
  useLayoutEffect(() => {
    if (!active) return;
    heading.current?.focus({ preventScroll: true });
    heading.current?.scrollIntoView?.({ block: 'start', behavior: 'instant' });
  }, [active]);
  if (!navigation?.host) return null;
  return createPortal(
    <OwnerContext.Provider value={id}>
      <DepthContext.Provider value={depth + layer + 1}>
        <section
          className="action-screen"
          hidden={!active}
          inert={!active}
          aria-labelledby={`${id}-title`}
        >
          <header className="action-screen-header">
            <button
              type="button"
              className="secondary back-button"
              onClick={onBack}
              disabled={busy}
            >
              <span aria-hidden="true">←</span> Voltar
            </button>
            <div>
              <p className="screen-eyebrow">Área de trabalho</p>
              <h2 ref={heading} id={`${id}-title`} tabIndex={-1}>
                {title}
              </h2>
            </div>
          </header>
          <ScreenFeedback error={error} notice={notice} />
          <div className="action-screen-body">{children}</div>
        </section>
      </DepthContext.Provider>
    </OwnerContext.Provider>,
    navigation.host,
  );
}
