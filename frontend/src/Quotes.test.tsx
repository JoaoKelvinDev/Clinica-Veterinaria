import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Quotes } from './Quotes';
import { App } from './App';
import type { UserProfile } from './api';
import { money, parseQuote, preview, toCents } from './quotes-api';
import type { Quote } from './quotes-api';

const user: UserProfile = {
  id: 'user-a',
  clinic_id: 'clinic-a',
  name: 'Recepção fictícia',
  role: 'reception',
  active: true,
  crmv: null,
  crmv_state: null,
};
const quote: Quote = {
  id: 'quote-a',
  patient_id: 'patient-a',
  tutor_id: 'tutor-a',
  patient_name: 'Paciente fictício',
  tutor_name: 'Tutor fictício',
  encounter_id: null,
  source_quote_id: null,
  status: 'draft',
  version: 1,
  valid_until: null,
  subtotal_cents: 1875,
  discount_cents: 100,
  total_cents: 1775,
  created_at: '2030-01-01T12:00:00Z',
  created_by: user.id,
  updated_at: '2030-01-01T12:00:00Z',
  updated_by: user.id,
  presented_at: null,
  presented_by: null,
  decision_at: null,
  decision_by: null,
  decision_source: null,
  decision_note: null,
  items: [
    {
      id: 'item-a',
      position: 1,
      kind: 'service',
      description: 'Serviço fictício',
      quantity: '1.500',
      unit_price_cents: 1250,
      line_total_cents: 1875,
    },
  ],
};
const patient = {
  id: quote.patient_id,
  clinic_id: user.clinic_id,
  name: quote.patient_name,
  species: 'Canina',
  sex: 'unknown',
  breed: null,
  coat: null,
  microchip: null,
  notes: null,
  birth_date: null,
  neutered: null,
  estimated_age_months: null,
};
function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}
function mockApi(initial = quote, reject = false) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/me')
      return json({ user, clinic: { id: user.clinic_id, name: 'Clínica fictícia' } });
    if (url === '/api/health') return json({ status: 'ok' });
    if (url.startsWith('/api/quotes?')) return json({ items: [initial], total: 1 });
    if (url.startsWith('/api/patients?')) return json({ items: [patient], total: 1 });
    if (url === '/api/quotes/options/patient-a')
      return json({
        tutors: [{ id: 'tutor-a', name: quote.tutor_name, is_primary: true }],
        encounters: [],
      });
    if (url === '/api/quotes/quote-a' && (!init?.method || init.method === 'GET'))
      return json(initial);
    if (url === '/api/quotes' && init?.method === 'POST') return json(quote, 201);
    if (url === '/api/quotes/quote-a/present')
      return json({
        ...initial,
        status: 'sent',
        version: 2,
        presented_at: '2030-01-01T12:01:00Z',
        presented_by: user.id,
      });
    if (url === '/api/quotes/quote-a/approve')
      return reject
        ? json(
            { error: { message: 'O orçamento mudou. Atualize a tela antes de continuar.' } },
            409,
          )
        : json({
            ...initial,
            status: 'approved',
            version: 3,
            decision_at: '2030-01-01T12:02:00Z',
            decision_by: user.id,
            decision_source: 'phone',
          });
    if (url === '/api/quotes/quote-a/revise')
      return json({ ...quote, id: 'quote-b', source_quote_id: 'quote-a' }, 201);
    return json({ items: [], total: 0 });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}
async function open() {
  fireEvent.click(
    await screen.findByRole('button', { name: 'Abrir orçamento de Paciente fictício' }),
  );
  await screen.findByRole('heading', { name: 'Orçamento de Paciente fictício' });
}
const sent: Quote = {
  ...quote,
  status: 'sent',
  version: 2,
  presented_at: '2030-01-01T12:01:00Z',
  presented_by: user.id,
};

describe('Orçamentos', () => {
  it('cadastra com quantidade decimal exata e envia apenas preços e desconto em centavos', async () => {
    const fetchMock = mockApi();
    render(<Quotes token="mock" user={user} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Novo orçamento' }));
    fireEvent.click(screen.getByRole('button', { name: 'Buscar pacientes' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Selecionar Paciente fictício' }));
    await screen.findByRole('option', { name: 'Tutor fictício (principal)' });
    fireEvent.change(screen.getByLabelText('Descrição do item 1'), {
      target: { value: 'Serviço fictício' },
    });
    fireEvent.change(screen.getByLabelText('Quantidade do item 1'), { target: { value: '1,5' } });
    fireEvent.change(screen.getByLabelText('Preço unitário do item 1 (R$)'), {
      target: { value: '12,50' },
    });
    fireEvent.change(screen.getByLabelText('Desconto do orçamento (R$)'), {
      target: { value: '1,00' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar rascunho' }));
    expect(await screen.findByText('Rascunho do orçamento salvo.')).toBeVisible();
    const call = fetchMock.mock.calls.find(
      ([url, init]) => url === '/api/quotes' && init?.method === 'POST',
    );
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      patient_id: 'patient-a',
      tutor_id: 'tutor-a',
      encounter_id: null,
      valid_until: null,
      discount_cents: 100,
      items: [
        {
          kind: 'service',
          description: 'Serviço fictício',
          quantity: '1.5',
          unit_price_cents: 1250,
        },
      ],
    });
  });

  it('registra apresentação manual com controle de versão e sem envio de mensagem', async () => {
    const fetchMock = mockApi();
    render(<Quotes token="mock" user={user} />);
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Marcar como apresentado' }));
    expect(
      await screen.findByText('Apresentação registrada. Itens e valores preservados.'),
    ).toBeVisible();
    const call = fetchMock.mock.calls.find(([url]) => url.endsWith('/present'));
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ expected_version: 1 });
    expect(fetchMock.mock.calls.some(([url]) => url.includes('/messaging'))).toBe(false);
    expect(screen.queryByRole('button', { name: 'Editar rascunho' })).toBeNull();
  });

  it('registra decisão comunicada pelo tutor com sua origem', async () => {
    const fetchMock = mockApi(sent);
    render(<Quotes token="mock" user={user} />);
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Registrar aprovação' }));
    fireEvent.change(screen.getByLabelText('Origem da decisão'), { target: { value: 'phone' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar registro de aprovação' }));
    expect(await screen.findByText('Decisão do tutor registrada.')).toBeVisible();
    const call = fetchMock.mock.calls.find(([url]) => url.endsWith('/approve'));
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      expected_version: 2,
      source: 'phone',
      note: null,
    });
  });

  it('orçamento expirado oferece revisão e não aprovação', async () => {
    mockApi({ ...sent, status: 'expired' });
    render(<Quotes token="mock" user={user} />);
    await open();
    expect(screen.queryByRole('button', { name: 'Registrar aprovação' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Criar revisão' }));
    expect(
      await screen.findByText(
        'Nova revisão criada em rascunho. O orçamento anterior foi preservado.',
      ),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: 'Ver orçamento anterior' })).toBeVisible();
  });

  it('auxiliar consulta sem ações de escrita', async () => {
    mockApi();
    render(<Quotes token="mock" user={{ ...user, role: 'assistant' }} />);
    await open();
    expect(screen.queryByRole('button', { name: 'Novo orçamento' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Editar rascunho' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Marcar como apresentado' })).toBeNull();
  });

  it('conflito mantém erro visível sem anunciar sucesso', async () => {
    mockApi(sent, true);
    render(<Quotes token="mock" user={user} />);
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Registrar aprovação' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar registro de aprovação' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('O orçamento mudou');
    expect(screen.queryByText('Decisão do tutor registrada.')).toBeNull();
  });

  it('abre pela navegação da aplicação', async () => {
    mockApi();
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
    fireEvent.click(await screen.findByRole('button', { name: 'Orçamentos' }));
    expect(await screen.findByRole('heading', { name: 'Orçamentos' })).toBeVisible();
  });

  it('arredonda cada item antes de somar e permite desconto integral', () => {
    const item = {
      kind: 'product' as const,
      description: 'Fictício',
      quantity: '0,5',
      price: '0,01',
    };
    expect(preview([item, item], '0,02')).toEqual({ subtotal: 2, discount: 2, total: 0 });
    expect(money(1234567)).toBe('R$ 12.345,67');
    expect(() => toCents('1.000,00')).toThrow();
    expect(() => preview([item], '0,02')).toThrow('desconto');
    expect(() => parseQuote({ ...quote, total_cents: 0.5 })).toThrow('dados inválidos');
  });
});
