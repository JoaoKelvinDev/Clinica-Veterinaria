import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';
import type { AuthGateway, AuthSession } from './auth';
import { parseUser } from './api';
import { dashboardFixture } from './test/dashboard-fixture';

const admin = {
  id: 'user-a',
  clinic_id: 'clinic-a',
  name: 'Administrador fictício',
  role: 'admin',
  active: true,
  crmv: null,
  crmv_state: null,
};
const reception = { ...admin, id: 'user-r', name: 'Recepção fictícia', role: 'reception' };
const clinic = { id: 'clinic-a', name: 'Clínica fictícia' };
const session = { access_token: 'fictitious-token' };

function gateway(initial: AuthSession | null = null) {
  return {
    getSession: vi.fn().mockResolvedValue(initial),
    signIn: vi.fn().mockResolvedValue(session),
    signOut: vi.fn().mockResolvedValue(undefined),
    subscribe: vi.fn<AuthGateway['subscribe']>(() => vi.fn()),
  } satisfies AuthGateway;
}
function mockApi(user = admin) {
  const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
    if (input === '/api/health') return new Response(JSON.stringify({ status: 'ok' }));
    if (input === '/api/me') return new Response(JSON.stringify({ user, clinic }));
    if (input === '/api/dashboard')
      return new Response(JSON.stringify(dashboardFixture(user.role as 'admin' | 'reception')));
    if (input === '/api/users') return new Response(JSON.stringify([admin, reception]));
    if (input === '/api/users/user-r' && init?.method === 'PATCH') {
      return new Response(JSON.stringify({ ...reception, active: false }));
    }
    return new Response('{}', { status: 404 });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}
async function enter() {
  fireEvent.change(await screen.findByLabelText('E-mail'), {
    target: { value: 'ficticio@example.test' },
  });
  fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'fictitious-password' } });
  fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));
}

describe('Autenticação e permissões', () => {
  it('abre os dados da clínica em tela própria e volta à equipe', async () => {
    mockApi();
    render(<App auth={gateway(session)} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Clínica e equipe' }));
    await screen.findByRole('heading', { name: 'Equipe da clínica' });
    fireEvent.click(screen.getByRole('button', { name: 'Editar dados da clínica' }));
    expect(screen.getByLabelText('Nome da clínica')).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Equipe da clínica' })).toBeNull();
    expect(screen.getByRole('heading', { name: 'Editar dados da clínica' })).toHaveFocus();
    fireEvent.click(screen.getByRole('button', { name: 'Voltar' }));
    expect(screen.getByRole('heading', { name: 'Equipe da clínica' })).toBeVisible();
  });
  it('entra, apresenta a clínica e encerra a sessão sem manter seus dados', async () => {
    const auth = gateway();
    mockApi();
    render(<App auth={auth} />);
    await enter();
    expect(await screen.findByRole('heading', { name: clinic.name })).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Visão geral' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Clínica e equipe' }));
    expect(await screen.findByRole('heading', { name: 'Equipe da clínica' })).toBeInTheDocument();
    expect(auth.signIn).toHaveBeenCalledWith('ficticio@example.test', 'fictitious-password');
    fireEvent.click(screen.getByRole('button', { name: 'Sair' }));
    expect(await screen.findByRole('button', { name: 'Entrar' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: clinic.name })).not.toBeInTheDocument();
    expect(auth.signOut).toHaveBeenCalledOnce();
  });

  it('exibe erro de credenciais sem abrir a clínica', async () => {
    const auth = gateway();
    auth.signIn.mockRejectedValue(new Error('Confira o e-mail e a senha.'));
    mockApi();
    render(<App auth={auth} />);
    await enter();
    expect(await screen.findByRole('alert')).toHaveTextContent('Confira o e-mail e a senha.');
    expect(screen.queryByRole('heading', { name: clinic.name })).not.toBeInTheDocument();
  });

  it('mostra e oculta a senha sem alterar seu valor ou enviar o formulário', async () => {
    const auth = gateway();
    mockApi();
    render(<App auth={auth} />);
    const password = await screen.findByLabelText('Senha');
    fireEvent.change(password, { target: { value: 'fictitious-password' } });
    expect(password).toHaveAttribute('type', 'password');
    fireEvent.click(screen.getByRole('button', { name: 'Mostrar senha' }));
    expect(password).toHaveAttribute('type', 'text');
    expect(password).toHaveValue('fictitious-password');
    expect(screen.getByRole('button', { name: 'Ocultar senha' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Ocultar senha' }));
    expect(password).toHaveAttribute('type', 'password');
    expect(password).toHaveValue('fictitious-password');
    expect(auth.signIn).not.toHaveBeenCalled();
  });

  it('bloqueia novo envio enquanto autentica e abre o dashboard ao concluir', async () => {
    const auth = gateway();
    let resolveLogin!: (value: AuthSession) => void;
    auth.signIn.mockReturnValue(
      new Promise<AuthSession>((resolve) => {
        resolveLogin = resolve;
      }),
    );
    mockApi();
    render(<App auth={auth} />);
    await enter();
    expect(screen.getByRole('button', { name: 'Entrando…' })).toBeDisabled();
    expect(screen.getByLabelText('E-mail')).toBeDisabled();
    expect(screen.getByLabelText('Senha')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Mostrar senha' })).toBeDisabled();
    expect(auth.signIn).toHaveBeenCalledOnce();
    await act(async () => resolveLogin(session));
    expect(await screen.findByRole('heading', { name: 'Visão geral' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Entre na sua clínica' })).not.toBeInTheDocument();
  });

  it('aguarda recuperar a sessão existente e entra sem solicitar credenciais novamente', async () => {
    const auth = gateway();
    let resolveSession!: (value: AuthSession) => void;
    auth.getSession.mockReturnValue(
      new Promise<AuthSession>((resolve) => {
        resolveSession = resolve;
      }),
    );
    mockApi();
    render(<App auth={auth} />);
    expect(screen.getByRole('heading', { name: 'Preparando seu acesso' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Entrar' })).not.toBeInTheDocument();
    await act(async () => resolveSession(session));
    expect(await screen.findByRole('heading', { name: 'Visão geral' })).toBeVisible();
    expect(auth.signIn).not.toHaveBeenCalled();
  });

  it('retorna à nova tela de login quando a sessão expira', async () => {
    const auth = gateway(session);
    let notify!: (value: AuthSession | null) => void;
    auth.subscribe.mockImplementation((callback) => {
      notify = callback;
      return vi.fn();
    });
    mockApi();
    render(<App auth={auth} />);
    await screen.findByRole('heading', { name: 'Visão geral' });
    await act(async () => notify(null));
    expect(await screen.findByRole('heading', { name: 'Entre na sua clínica' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: clinic.name })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Senha')).toHaveValue('');
  });

  it('não disponibiliza administração para recepção', async () => {
    mockApi(reception);
    render(<App auth={gateway(session)} />);
    expect(await screen.findByRole('heading', { name: clinic.name })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Meu acesso' }));
    expect(await screen.findByRole('heading', { name: 'Seu acesso' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Equipe da clínica' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Nome da clínica')).not.toBeInTheDocument();
    expect(screen.queryByText(/próximas etapas/)).not.toBeInTheDocument();
  });

  it('nega o acesso quando o backend bloqueia um usuário', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async (input: string) =>
          new Response(
            JSON.stringify(
              input === '/api/health'
                ? { status: 'ok' }
                : { error: { message: 'Usuário sem acesso ativo.' } },
            ),
            { status: input === '/api/health' ? 200 : 403 },
          ),
      ),
    );
    const auth = gateway(session);
    render(<App auth={auth} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Usuário sem acesso ativo.');
    expect(screen.queryByRole('heading', { name: clinic.name })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Sair' }));
    expect(await screen.findByRole('heading', { name: 'Entre na sua clínica' })).toBeVisible();
    expect(auth.signOut).toHaveBeenCalledOnce();
  });

  it('permite ao administrador desativar um usuário', async () => {
    const fetchMock = mockApi();
    render(<App auth={gateway(session)} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Clínica e equipe' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Editar Recepção fictícia' }));
    fireEvent.click(screen.getByLabelText('Usuário ativo'));
    fireEvent.click(screen.getByRole('button', { name: 'Salvar alterações' }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/users/user-r',
        expect.objectContaining({
          method: 'PATCH',
          headers: expect.objectContaining({ Authorization: 'Bearer fictitious-token' }),
          body: expect.stringContaining('"active":false'),
        }),
      ),
    );
    // A confirmação continua visível: salvar não recarrega a tela inteira.
    expect(await screen.findByText('Alterações de Recepção fictícia salvas.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Equipe da clínica' })).toBeInTheDocument();
  });

  it('rejeita papéis desconhecidos na resposta do backend', () => {
    expect(() => parseUser({ ...admin, role: '__proto__' })).toThrow('dados inválidos');
  });
});
