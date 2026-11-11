import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { Dashboard } from './Dashboard';
import type { Role, UserProfile } from './api';
import { parseDashboard } from './dashboard-api';
import { dashboardFixture } from './test/dashboard-fixture';

const user: UserProfile = {
  id: 'user-a',
  clinic_id: 'clinic-a',
  name: 'Pessoa fictícia',
  role: 'admin',
  active: true,
  crmv: null,
  crmv_state: null,
};
function mockApi(role: Role = 'admin') {
  const fetchMock = vi.fn(async (input: string) => {
    if (input === '/api/dashboard') return new Response(JSON.stringify(dashboardFixture(role)));
    if (input === '/api/me')
      return new Response(
        JSON.stringify({
          user: { ...user, role },
          clinic: { id: 'clinic-a', name: 'Clínica fictícia' },
        }),
      );
    if (input === '/api/health') return new Response(JSON.stringify({ status: 'ok' }));
    if (input === '/api/scheduling/veterinarians') return new Response('[]');
    return new Response(JSON.stringify({ items: [], total: 0, limit: 20, offset: 0 }));
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}
function show(role: Role = 'admin', onNavigate = vi.fn()) {
  return render(
    <Dashboard token="fictitious-token" user={{ ...user, role }} onNavigate={onNavigate} />,
  );
}

describe('Visão geral', () => {
  it('apresenta os quatro resumos, a data da clínica e o modo simulado', async () => {
    mockApi();
    show();
    await screen.findByRole('heading', { name: 'Financeiro do mês' });
    expect(screen.getByText(/Dia 11\/11\/2026/)).toBeVisible();
    expect(screen.getByText(/Horário de Fortaleza/)).toBeVisible();
    expect(screen.getByText(/MOCK/)).toBeVisible();
    expect(screen.getByText('R$ 123,45', { exact: false })).toBeVisible();
    expect(screen.getByText('Agendamentos no dia')).toBeVisible();
    expect(screen.getByText('Lotes que vencem em até 30 dias')).toBeVisible();
  });

  it.each<Role>(['admin', 'reception', 'veterinarian', 'assistant'])(
    'respeita o acesso de %s',
    async (role) => {
      mockApi(role);
      show(role);
      await screen.findByRole('button', { name: 'Ver agenda' });
      expect(screen.queryByRole('heading', { name: 'Financeiro do mês' }) !== null).toBe(
        role === 'admin' || role === 'reception',
      );
      expect(screen.queryByText('Despesas vigentes') !== null).toBe(role === 'admin');
      expect(screen.queryByText('Diferença do mês') !== null).toBe(role === 'admin');
    },
  );

  it('abre cada área sem recarregar ou escrever dados', async () => {
    const fetchMock = mockApi();
    const navigate = vi.fn();
    show('admin', navigate);
    await screen.findByRole('button', { name: 'Ver agenda' });
    for (const [name, destination] of [
      ['Ver agenda', 'scheduling'],
      ['Ver mensagens', 'messaging'],
      ['Ver estoque', 'inventory'],
      ['Ver financeiro', 'financial'],
    ] as const) {
      fireEvent.click(screen.getByRole('button', { name }));
      expect(navigate).toHaveBeenLastCalledWith(destination);
    }
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/dashboard',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer fictitious-token' }),
      }),
    );
  });

  it('usa a visão geral como início e mantém a navegação da agenda', async () => {
    mockApi();
    render(
      <App
        auth={{
          getSession: vi.fn().mockResolvedValue({ access_token: 'fictitious-token' }),
          signIn: vi.fn(),
          signOut: vi.fn(),
          subscribe: vi.fn(() => vi.fn()),
        }}
      />,
    );
    await screen.findByRole('button', { name: 'Ver agenda' });
    fireEvent.click(screen.getByRole('button', { name: 'Ver agenda' }));
    await screen.findByRole('heading', { name: 'Agenda e atendimentos' });
    fireEvent.click(screen.getByRole('button', { name: 'Visão geral' }));
    await screen.findByRole('button', { name: 'Ver agenda' });
  });

  it('mostra zero quando a consulta retorna uma clínica sem registros', async () => {
    const data = dashboardFixture();
    Object.keys(data.scheduling).forEach((key) => {
      data.scheduling[key as keyof typeof data.scheduling] = 0;
    });
    data.messaging.needs_attention = 0;
    data.inventory = { low_stock_products: 0, expired_lots: 0, expiring_lots: 0 };
    data.financial = { income_cents: '0', expense_cents: '0', difference_cents: '0' };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(data))));
    show();
    expect(await screen.findByText('Nenhuma mensagem aguardando a equipe.')).toBeVisible();
    expect(screen.getAllByText(/R\$\s*0,00/)).toHaveLength(3);
  });

  it('remove os totais antigos se a atualização falhar e permite tentar novamente', async () => {
    const fetchMock = mockApi();
    show();
    await screen.findByRole('button', { name: 'Ver financeiro' });
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: { message: 'Serviço indisponível.' } }), {
        status: 503,
      }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Atualizar visão geral' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Serviço indisponível.');
    expect(screen.queryByRole('button', { name: 'Ver financeiro' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Atualizar visão geral' }));
    await screen.findByRole('button', { name: 'Ver financeiro' });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it('ignora a resposta da sessão anterior após trocar usuário e papel', async () => {
    let resolveOld: ((response: Response) => void) | undefined;
    const old = new Promise<Response>((resolve) => {
      resolveOld = resolve;
    });
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockReturnValueOnce(old)
        .mockResolvedValueOnce(new Response(JSON.stringify(dashboardFixture('reception')))),
    );
    const view = show();
    expect(screen.getByRole('button', { name: 'Atualizar visão geral' })).toBeDisabled();
    view.rerender(
      <Dashboard
        token="another-token"
        user={{ ...user, id: 'another-user', role: 'reception' }}
        onNavigate={vi.fn()}
      />,
    );
    await screen.findByRole('button', { name: 'Ver financeiro' });
    await act(async () => {
      resolveOld?.(new Response(JSON.stringify(dashboardFixture())));
      await old;
    });
    expect(screen.queryByText('Despesas vigentes')).toBeNull();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Atualizar visão geral' })).toBeEnabled(),
    );
  });

  it('preserva centavos maiores que o inteiro seguro de JavaScript', async () => {
    const data = dashboardFixture();
    data.financial = {
      income_cents: '9007199254740993',
      expense_cents: '1',
      difference_cents: '9007199254740992',
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(data))));
    show();
    expect(await screen.findByText(/90\.071\.992\.547\.409,93/)).toBeVisible();
    expect(screen.getByText(/90\.071\.992\.547\.409,92/)).toBeVisible();
  });

  it('rejeita respostas inválidas e dados financeiros incompatíveis com o perfil', () => {
    const base = dashboardFixture();
    for (const data of [
      { ...base, day: '2026-02-30' },
      { ...base, timezone: 'UTC' },
      { ...base, scheduling: { ...base.scheduling, appointments_total: 13 } },
      { ...base, inventory: { ...base.inventory, expired_lots: -1 } },
      { ...base, financial: { ...base.financial, income_cents: 12345 } },
      { ...base, financial: { ...base.financial, difference_cents: '0' } },
    ])
      expect(() => parseDashboard(data, 'admin')).toThrow('dados inválidos');
    expect(() => parseDashboard(base, 'reception')).toThrow('dados inválidos');
    expect(() => parseDashboard(base, 'veterinarian')).toThrow('dados inválidos');
  });
});
