import { createClient } from '@supabase/supabase-js';

export interface AuthSession {
  access_token: string;
}

export interface AuthGateway {
  getSession(): Promise<AuthSession | null>;
  signIn(email: string, password: string): Promise<AuthSession>;
  signOut(): Promise<void>;
  subscribe(callback: (session: AuthSession | null) => void): () => void;
}

function configureAuth(): AuthGateway | null {
  const url: unknown = import.meta.env.VITE_SUPABASE_URL;
  const key: unknown = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
  if (typeof url !== 'string' || !url || typeof key !== 'string' || !key) return null;
  const client = createClient(url, key);
  return {
    async getSession() {
      const { data, error } = await client.auth.getSession();
      if (error) throw new Error('Não foi possível recuperar a sessão.');
      return data.session;
    },
    async signIn(email, password) {
      const { data, error } = await client.auth.signInWithPassword({ email, password });
      if (error || !data.session)
        throw new Error('Não foi possível entrar. Confira o e-mail e a senha.');
      return data.session;
    },
    async signOut() {
      const { error } = await client.auth.signOut();
      if (error) throw new Error('Não foi possível encerrar a sessão. Tente novamente.');
    },
    subscribe(callback) {
      const { data } = client.auth.onAuthStateChange((_event, session) => {
        // A chamada de rede ocorre fora do callback de Auth, evitando bloquear o SDK.
        queueMicrotask(() => callback(session));
      });
      return () => data.subscription.unsubscribe();
    },
  };
}

export const defaultAuth = configureAuth();
