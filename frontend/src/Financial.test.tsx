import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { Financial } from './Financial';
import type { UserProfile } from './api';
import {
  financialCents,
  financialMoney,
  parseFinancialEntry,
  parseFinancialPage,
} from './financial-api';
import type { FinancialEntry, FinancialPage } from './financial-api';
import type { Patient, Tutor } from './registry-api';

const tutor: Tutor = {
  id: 'tutor-a',
  clinic_id: 'clinic-a',
  name: 'Tutor fictício',
  phone: null,
  document: null,
  address: null,
  whatsapp_opt_in: false,
  whatsapp_opt_in_at: null,
  whatsapp_opt_in_source: null,
  whatsapp_opt_out_at: null,
  deleted_at: null,
};
const patient: Patient = {
  id: 'patient-a',
  clinic_id: 'clinic-a',
  name: 'Animal fictício',
  species: 'Canina',
  breed: null,
  sex: 'unknown',
  neutered: null,
  birth_date: null,
  estimated_age_months: null,
  coat: null,
  microchip: null,
  notes: null,
};

const user: UserProfile = {
  id: 'admin-a',
  clinic_id: 'clinic-a',
  name: 'Admin fictício',
  role: 'admin',
  active: true,
  crmv: null,
  crmv_state: null,
};
const income: FinancialEntry = {
  id: 'income-a',
  kind: 'income',
  description: 'Consulta fictícia',
  category: 'Consultas',
  amount_cents: 12345,
  occurred_on: '2026-11-09',
  payment_method: 'pix',
  author_id: 'reception-a',
  author_name: 'Recepção fictícia',
  created_at: '2026-11-09T12:00:00Z',
  tutor_id: null,
  tutor_name: null,
  patient_id: null,
  patient_name: null,
  status: 'posted',
  reversal: null,
};
const summary = { income_cents: '12345', expense_cents: '123', difference_cents: '12222' };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

function mockApi({
  role = 'admin',
  failWrite = false,
  failRead = false,
  total = 1,
  empty = false,
  failRefresh = false,
}: {
  role?: UserProfile['role'];
  failWrite?: boolean;
  failRead?: boolean;
  total?: number;
  empty?: boolean;
  failRefresh?: boolean;
} = {}) {
  let saved = income;
  let wrote = false;
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/me')
      return json({
        user: { ...user, role },
        clinic: { id: user.clinic_id, name: 'Clínica fictícia' },
      });
    if (url === '/api/health') return json({ status: 'ok' });
    if (url.startsWith('/api/tutors?')) return json({ items: [tutor], total: 1 });
    if (url.startsWith('/api/patients?')) return json({ items: [patient], total: 1 });
    if (url.startsWith('/api/financial/entries?')) {
      if (failRead || (wrote && failRefresh))
        return json({ error: { message: 'Falha de leitura' } }, 503);
      return json({
        items: empty ? [] : [saved],
        total: empty ? 0 : total,
        summary:
          role === 'reception'
            ? { ...summary, expense_cents: null, difference_cents: null }
            : summary,
      });
    }
    if (init?.method === 'POST' && url.startsWith('/api/financial/entries')) {
      if (failWrite)
        return json({ error: { message: 'Conflito financeiro. Atualize os lançamentos.' } }, 409);
      wrote = true;
      const body = JSON.parse(String(init.body)) as Record<string, unknown>;
      saved = url.endsWith('/reverse')
        ? {
            ...income,
            status: 'reversed',
            reversal: {
              id: 'reverse-a',
              author_id: user.id,
              author_name: user.name,
              created_at: '2026-11-10T13:00:00Z',
              reversal_reason: String(body.reason),
            },
          }
        : { ...income, ...body };
      return json(saved, 201);
    }
    return json({ items: [], total: 0 });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}
function fill(amount = '0,10') {
  if (!screen.queryByLabelText('Descrição'))
    fireEvent.click(screen.getByRole('button', { name: /^Novo (lançamento|recebimento)$/ }));
  fireEvent.change(screen.getByLabelText('Descrição'), {
    target: { value: 'Recebimento fictício' },
  });
  fireEvent.change(screen.getByLabelText('Categoria'), { target: { value: 'Consultas' } });
  fireEvent.change(screen.getByLabelText('Valor em reais'), { target: { value: amount } });
  fireEvent.change(screen.getByLabelText('Forma de pagamento'), { target: { value: 'pix' } });
}

describe('Financeiro manual', () => {
  it('busca e seleciona tutor e animal para o lançamento', async () => {
    const fetchMock = mockApi();
    render(<Financial token="mock" user={user} />);
    fireEvent.click(screen.getByRole('button', { name: 'Novo lançamento' }));
    fireEvent.change(screen.getByLabelText('Buscar tutor por nome'), {
      target: { value: 'Tutor' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Buscar tutor' }));
    await screen.findByRole('option', { name: tutor.name });
    fireEvent.change(screen.getByLabelText('Tutor vinculado'), { target: { value: tutor.id } });
    fireEvent.change(screen.getByLabelText('Buscar animal por nome'), {
      target: { value: 'Animal' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Buscar animal' }));
    await screen.findByRole('option', { name: patient.name });
    fireEvent.change(screen.getByLabelText('Animal vinculado'), { target: { value: patient.id } });
    fill();
    fireEvent.click(screen.getByRole('button', { name: 'Registrar lançamento' }));
    await screen.findByText(/Recebimento registrado/);
    const sent = fetchMock.mock.calls.find(
      ([url, init]) => url === '/api/financial/entries' && init?.method === 'POST',
    );
    expect(JSON.parse(String(sent?.[1]?.body))).toEqual(
      expect.objectContaining({ tutor_id: tutor.id, patient_id: patient.id }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Novo lançamento' }));
    expect(screen.getByLabelText('Tutor vinculado')).toHaveValue('');
    expect(screen.getByLabelText('Animal vinculado')).toHaveValue('');
  });
  it('mostra os totais, a autoria e as limitações financeiras', async () => {
    mockApi();
    render(<Financial token="mock" user={user} />);
    expect(await screen.findByRole('table', { name: 'Lançamentos financeiros' })).toBeVisible();
    expect(screen.getByText('Recebimentos vigentes')).toBeVisible();
    expect(screen.getByText('R$ 122,22')).toBeVisible();
    expect(screen.getByText('Recepção fictícia')).toBeVisible();
    expect(screen.getByText(/não representa lucro contábil nem saldo bancário/)).toBeVisible();
  });
  it('envia centavos exatos e vínculos opcionais, sem cobrança real', async () => {
    const fetchMock = mockApi();
    render(<Financial token="mock" user={user} />);
    fill();
    fireEvent.click(screen.getByRole('button', { name: 'Registrar lançamento' }));
    expect(await screen.findByText(/Recebimento registrado/)).toBeVisible();
    const call = fetchMock.mock.calls.find(
      ([url, init]) => url === '/api/financial/entries' && init?.method === 'POST',
    );
    expect(JSON.parse(String(call?.[1]?.body))).toEqual(
      expect.objectContaining({
        kind: 'income',
        amount_cents: 10,
        payment_method: 'pix',
        tutor_id: null,
        patient_id: null,
      }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Novo lançamento' }));
    expect(screen.getByLabelText('Descrição')).toHaveValue('');
  });
  it('permite ao administrador registrar uma despesa', async () => {
    const fetchMock = mockApi();
    render(<Financial token="mock" user={user} />);
    fill('1,25');
    fireEvent.change(screen.getByLabelText('Tipo'), { target: { value: 'expense' } });
    fireEvent.click(screen.getByRole('button', { name: 'Registrar lançamento' }));
    expect(await screen.findByText(/Despesa registrada/)).toBeVisible();
    expect(
      fetchMock.mock.calls.some(
        ([, init]) => init?.body && JSON.parse(String(init.body)).kind === 'expense',
      ),
    ).toBe(true);
  });
  it('preserva o formulário e não declara sucesso em conflito', async () => {
    mockApi({ failWrite: true });
    render(<Financial token="mock" user={user} />);
    fill();
    fireEvent.click(screen.getByRole('button', { name: 'Registrar lançamento' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Conflito financeiro');
    expect(screen.getByLabelText('Descrição')).toHaveValue('Recebimento fictício');
    expect(screen.queryByText(/Recebimento registrado/)).toBeNull();
  });
  it('rejeita valor ambíguo antes do envio', async () => {
    const fetchMock = mockApi();
    render(<Financial token="mock" user={user} />);
    fill('1.000,00');
    fireEvent.click(screen.getByRole('button', { name: 'Registrar lançamento' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('sem pontos');
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });
  it('recepção não vê despesas, diferença, tipo ou estorno', async () => {
    mockApi({ role: 'reception' });
    render(<Financial token="mock" user={{ ...user, role: 'reception' }} />);
    await screen.findByRole('table');
    expect(screen.queryByText('Despesas vigentes')).toBeNull();
    expect(screen.queryByText('Diferença do período')).toBeNull();
    expect(screen.queryByLabelText('Tipo')).toBeNull();
    expect(screen.queryByRole('button', { name: /Estornar/ })).toBeNull();
  });
  it.each(['veterinarian', 'assistant'] as const)('não abre para %s', (role) => {
    const fetchMock = mockApi();
    const { container } = render(<Financial token="mock" user={{ ...user, role }} />);
    expect(container).toBeEmptyDOMElement();
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it('explica o estorno administrativo, exige motivo e preserva autoria original', async () => {
    const fetchMock = mockApi();
    render(<Financial token="mock" user={user} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Estornar Consulta fictícia' }));
    expect(screen.getByText(/uma devolução real deve ser registrada como despesa/)).toBeVisible();
    fireEvent.change(screen.getByLabelText('Motivo do estorno'), {
      target: { value: 'Erro de digitação' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar estorno' }));
    expect(
      await screen.findByText('Estorno registrado na data financeira original.'),
    ).toBeVisible();
    expect(await screen.findByText('Erro de digitação')).toBeVisible();
    expect(screen.getByText('Recepção fictícia')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Estornar Consulta fictícia' })).toBeNull();
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          url.endsWith('/income-a/reverse') &&
          init?.body === JSON.stringify({ reason: 'Erro de digitação' }),
      ),
    ).toBe(true);
  });
  it('cancela o estorno sem escrever e mantém motivo em conflito', async () => {
    mockApi({ failWrite: true });
    render(<Financial token="mock" user={user} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Estornar Consulta fictícia' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(screen.getByRole('button', { name: 'Novo lançamento' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Estornar Consulta fictícia' }));
    fireEvent.change(screen.getByLabelText('Motivo do estorno'), {
      target: { value: 'Correção fictícia' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar estorno' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Conflito financeiro');
    expect(screen.getByLabelText('Motivo do estorno')).toHaveValue('Correção fictícia');
  });
  it('filtra e pagina com totais de todo o resultado', async () => {
    const fetchMock = mockApi({ total: 25 });
    render(<Financial token="mock" user={user} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Próxima' }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => url.includes('offset=20'))).toBe(true),
    );
    fireEvent.change(screen.getByLabelText('Categoria do filtro'), {
      target: { value: 'Consultas' },
    });
    fireEvent.change(screen.getByLabelText('Situação'), { target: { value: 'posted' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar filtros' }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url]) =>
            url.includes('category=Consultas') &&
            url.includes('status=posted') &&
            url.includes('offset=0'),
        ),
      ).toBe(true),
    );
  });
  it('informa falha de leitura sem inventar totais', async () => {
    mockApi({ failRead: true });
    render(<Financial token="mock" user={user} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Falha de leitura');
    expect(screen.queryByText('Recebimentos vigentes')).toBeNull();
  });
  it('mantém confirmação de gravação quando só a atualização da lista falha', async () => {
    mockApi({ failRefresh: true });
    render(<Financial token="mock" user={user} />);
    fill();
    fireEvent.click(screen.getByRole('button', { name: 'Registrar lançamento' }));
    expect(await screen.findByText(/Recebimento registrado/)).toBeVisible();
    expect(await screen.findByRole('alert')).toHaveTextContent('Falha de leitura');
    expect(screen.queryByText('Recebimentos vigentes')).toBeNull();
  });
  it('informa uma consulta vazia', async () => {
    mockApi({ empty: true });
    render(<Financial token="mock" user={user} />);
    expect(await screen.findByText('Nenhum lançamento neste filtro.')).toBeVisible();
  });
  it.each(['admin', 'reception', 'veterinarian', 'assistant'] as const)(
    'navegação para %s',
    async (role) => {
      mockApi({ role });
      render(
        <App
          auth={{
            getSession: async () => ({ access_token: 'mock' }),
            signIn: vi.fn(),
            signOut: vi.fn(),
            subscribe: () => vi.fn(),
          }}
        />,
      );
      await screen.findByRole('button', { name: 'Agenda' });
      if (role === 'admin' || role === 'reception') {
        fireEvent.click(screen.getByRole('button', { name: 'Financeiro' }));
        expect(await screen.findByRole('heading', { name: 'Financeiro' })).toBeVisible();
      } else expect(screen.queryByRole('button', { name: 'Financeiro' })).toBeNull();
    },
  );
  it('converte e formata valores grandes sem arredondar e valida contratos', () => {
    expect(financialCents('0001,01')).toBe(101);
    expect(financialCents('10000000000,00')).toBe(1_000_000_000_000);
    for (const bad of ['0', '-1', '1e3', '1.23', '1,234', '10000000000,01', 'NaN'])
      expect(() => financialCents(bad)).toThrow();
    expect(financialMoney('9007199254740993')).toBe('R$ 90.071.992.547.409,93');
    expect(financialMoney('-1')).toBe('-R$ 0,01');
    const valid: FinancialPage = { items: [income], total: 1, summary };
    expect(parseFinancialPage(valid)).toEqual(valid);
    expect(() =>
      parseFinancialPage({ ...valid, summary: { ...summary, income_cents: 12345 } }),
    ).toThrow();
    expect(() =>
      parseFinancialPage({ ...valid, summary: { ...summary, difference_cents: '1' } }),
    ).toThrow();
    expect(() => parseFinancialEntry({ ...income, amount_cents: 1.5 })).toThrow();
    expect(() => parseFinancialEntry({ ...income, status: 'reversed' })).toThrow();
  });
});
