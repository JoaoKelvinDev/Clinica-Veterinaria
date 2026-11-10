import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Inventory } from './Inventory';
import { App } from './App';
import type { UserProfile } from './api';
import { parseMovements, parseProduct, stockDisplay, stockQuantity } from './inventory-api';
import type { Movement, Product } from './inventory-api';

const user: UserProfile = {
  id: 'user-a',
  clinic_id: 'clinic-a',
  name: 'Administrador fictício',
  role: 'admin',
  active: true,
  crmv: null,
  crmv_state: null,
};
const product: Product = {
  id: 'product-a',
  name: 'Insumo fictício',
  unit: 'mL',
  minimum_stock: '5.000',
  track_expiry: true,
  version: 3,
  deleted_at: null,
  physical_stock: '4.500',
  available_stock: '3.500',
  expired_stock: '1.000',
  low_stock: true,
  expiring_lots: 1,
  expired_lots: 1,
  lots: [
    {
      id: 'lot-a',
      code: 'VALID',
      expires_on: '2030-01-01',
      balance: '3.500',
      expired: false,
      expiring: true,
    },
    {
      id: 'lot-b',
      code: 'EXPIRED',
      expires_on: '2020-01-01',
      balance: '1.000',
      expired: true,
      expiring: false,
    },
  ],
};
const movement: Movement = {
  id: 'movement-a',
  lot_id: 'lot-a',
  operation_id: 'op-a',
  kind: 'inbound',
  quantity: '3.500',
  reason: 'Entrada fictícia',
  author_name: user.name,
  product_name: product.name,
  unit: product.unit,
  created_at: '2029-12-01T12:00:00Z',
  corrects_id: null,
};
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function mockApi({ initial = product, reject = false, total = 1, failHistory = false } = {}) {
  let saved = initial;
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/me')
      return json({ user, clinic: { id: user.clinic_id, name: 'Clínica fictícia' } });
    if (url === '/api/health') return json({ status: 'ok' });
    if (url.startsWith('/api/inventory/products?')) return json({ items: [saved], total });
    if (url.includes('/movements?'))
      return failHistory && saved.version > initial.version
        ? json({ error: { message: 'Falha de leitura' } }, 503)
        : json({ items: [movement], total: 1 });
    if (url === '/api/inventory/products/product-a' && (!init?.method || init.method === 'GET'))
      return json(saved);
    if (init?.method && ['POST', 'PUT'].includes(init.method) && url.startsWith('/api/inventory')) {
      if (reject) return json({ error: { message: 'O estoque mudou. Atualize o produto.' } }, 409);
      saved = {
        ...saved,
        version: saved.version + 1,
        ...(url.endsWith('/archive') ? { deleted_at: '2030-01-01T12:00:00Z' } : {}),
      };
      return json(saved, 201);
    }
    return json({ items: [], total: 0 });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}
async function open() {
  fireEvent.click(await screen.findByRole('button', { name: product.name }));
  await screen.findByRole('button', { name: 'Atualizar produto' });
}
function submit(quantity = '1,125') {
  fireEvent.change(screen.getByLabelText('Quantidade'), { target: { value: quantity } });
  fireEvent.change(screen.getByLabelText('Motivo'), { target: { value: 'Consumo fictício' } });
  fireEvent.click(screen.getByRole('button', { name: 'Confirmar movimentação' }));
}

describe('Estoque', () => {
  it('mostra saldo disponível, vencido e alertas separados', async () => {
    mockApi();
    render(<Inventory token="mock" user={user} />);
    await open();
    expect(screen.getByText('Físico (inclui vencidos)')).toBeVisible();
    expect(screen.getAllByText(/Abaixo do mínimo/).length).toBe(2);
    expect(screen.getByRole('cell', { name: 'Vencido' })).toBeVisible();
    expect(screen.getByRole('table', { name: 'Lotes e saldos' })).toBeVisible();
  });
  it('envia saída decimal com versão e deixa a alocação para o FEFO', async () => {
    const fetchMock = mockApi();
    render(<Inventory token="mock" user={user} />);
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Registrar saída FEFO' }));
    submit();
    expect(
      await screen.findByText('Saída registrada por FEFO. Confira os lotes no histórico.'),
    ).toBeVisible();
    const call = fetchMock.mock.calls.find(([url]) => url.endsWith('/issues'));
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      expected_version: 3,
      quantity: '1.125',
      reason: 'Consumo fictício',
    });
  });
  it('entrada seleciona lote e impede escolher vencido', async () => {
    const fetchMock = mockApi();
    render(<Inventory token="mock" user={user} />);
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Registrar entrada' }));
    expect(screen.getByRole('option', { name: /EXPIRED/ })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Lote'), { target: { value: 'lot-a' } });
    submit('0,001');
    await screen.findByText('Movimentação registrada.');
    expect(
      JSON.parse(
        String(fetchMock.mock.calls.find(([url]) => url.endsWith('/receipts'))?.[1]?.body),
      ),
    ).toEqual({
      expected_version: 3,
      quantity: '0.001',
      lot_id: 'lot-a',
      reason: 'Consumo fictício',
    });
  });
  it('corrige por ajuste vinculado preservando o lançamento original', async () => {
    const fetchMock = mockApi();
    render(<Inventory token="mock" user={user} />);
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Corrigir lançamento' }));
    fireEvent.change(screen.getByLabelText('Variação do saldo (use − para reduzir)'), {
      target: { value: '-0,125' },
    });
    fireEvent.change(screen.getByLabelText('Motivo'), { target: { value: 'Correção fictícia' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar movimentação' }));
    await screen.findByText('Movimentação registrada.');
    expect(
      JSON.parse(
        String(fetchMock.mock.calls.find(([url]) => url.endsWith('/adjustments'))?.[1]?.body),
      ),
    ).toEqual({
      expected_version: 3,
      quantity: '-0.125',
      lot_id: 'lot-a',
      reason: 'Correção fictícia',
      corrects_id: movement.id,
    });
  });
  it('recepção consulta sem controles de escrita', async () => {
    mockApi();
    render(<Inventory token="mock" user={{ ...user, role: 'reception' }} />);
    await open();
    for (const name of [
      'Novo produto',
      'Registrar entrada',
      'Registrar saída FEFO',
      'Ajustar inventário',
      'Editar produto',
      'Arquivar produto',
      'Corrigir lançamento',
    ])
      expect(screen.queryByRole('button', { name })).toBeNull();
  });
  it.each(['assistant', 'veterinarian'] as const)(
    '%s faz entradas e saídas, sem ajuste administrativo',
    async (role) => {
      mockApi();
      render(<Inventory token="mock" user={{ ...user, role }} />);
      await open();
      expect(screen.getByRole('button', { name: 'Registrar entrada' })).toBeVisible();
      expect(screen.getByRole('button', { name: 'Registrar saída FEFO' })).toBeVisible();
      expect(screen.queryByRole('button', { name: 'Ajustar inventário' })).toBeNull();
      expect(screen.queryByRole('button', { name: 'Novo produto' })).toBeNull();
    },
  );
  it('conflito preserva formulário e não anuncia sucesso', async () => {
    mockApi({ reject: true });
    render(<Inventory token="mock" user={user} />);
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Registrar saída FEFO' }));
    submit();
    expect(await screen.findByRole('alert')).toHaveTextContent('O estoque mudou');
    expect(screen.getByLabelText('Quantidade')).toHaveValue('1,125');
    expect(screen.queryByText(/Saída registrada por FEFO/)).toBeNull();
  });
  it('erro ao reler histórico informa que a operação já foi registrada', async () => {
    mockApi({ failHistory: true });
    render(<Inventory token="mock" user={user} />);
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Registrar saída FEFO' }));
    submit();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Operação registrada, mas não foi possível atualizar o histórico',
    );
    expect(screen.queryByRole('button', { name: 'Confirmar movimentação' })).toBeNull();
  });
  it('cadastra produto com mínimo decimal exato', async () => {
    const fetchMock = mockApi();
    render(<Inventory token="mock" user={user} />);
    fireEvent.click(screen.getByRole('button', { name: 'Novo produto' }));
    fireEvent.change(screen.getByLabelText('Nome do produto'), {
      target: { value: 'Produto fictício' },
    });
    fireEvent.change(screen.getByLabelText('Estoque mínimo'), { target: { value: '0,125' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar produto' }));
    await screen.findByText('Produto salvo.');
    expect(
      JSON.parse(
        String(
          fetchMock.mock.calls.find(
            ([url, init]) => url === '/api/inventory/products' && init?.method === 'POST',
          )?.[1]?.body,
        ),
      ),
    ).toEqual({ name: 'Produto fictício', unit: 'un', minimum_stock: '0.125', track_expiry: true });
  });
  it('cadastra lote e explica que ainda não existe saldo', async () => {
    const fetchMock = mockApi();
    render(<Inventory token="mock" user={user} />);
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Cadastrar lote' }));
    fireEvent.change(screen.getByLabelText('Código do lote'), { target: { value: 'NOVO' } });
    fireEvent.change(screen.getByLabelText('Validade'), { target: { value: '2030-01-01' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar lote' }));
    expect(await screen.findByText(/Lote cadastrado com saldo zero/)).toBeVisible();
    expect(
      JSON.parse(String(fetchMock.mock.calls.find(([url]) => url.endsWith('/lots'))?.[1]?.body)),
    ).toEqual({ expected_version: 3, code: 'NOVO', expires_on: '2030-01-01' });
  });
  it('arquivado mantém histórico sem novas operações', async () => {
    mockApi({ initial: { ...product, deleted_at: '2030-01-01T12:00:00Z' } });
    render(<Inventory token="mock" user={user} />);
    await open();
    expect(screen.getByRole('heading', { name: /Arquivado/ })).toBeVisible();
    expect(screen.getByRole('table', { name: 'Histórico de movimentações' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Registrar entrada' })).toBeNull();
  });
  it('busca, pagina e filtra arquivados', async () => {
    const fetchMock = mockApi({ total: 25 });
    render(<Inventory token="mock" user={user} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Próximos' }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => url.includes('offset=20'))).toBe(true),
    );
    fireEvent.change(screen.getByLabelText('Buscar produto'), { target: { value: 'fictício' } });
    fireEvent.click(screen.getByRole('button', { name: 'Buscar' }));
    fireEvent.change(screen.getByLabelText('Situação'), { target: { value: 'archived' } });
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url]) => url.includes('archived=true') && url.includes('offset=0'),
        ),
      ).toBe(true),
    );
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
    fireEvent.click(await screen.findByRole('button', { name: 'Estoque' }));
    expect(await screen.findByRole('heading', { name: 'Estoque' })).toBeVisible();
  });
  it('valida casas decimais sem arredondamento e rejeita resposta inválida', () => {
    expect(stockQuantity('0001,001')).toBe('1.001');
    expect(stockQuantity('-0,125', 'adjustment')).toBe('-0.125');
    expect(stockQuantity('0', 'minimum')).toBe('0');
    expect(stockDisplay('1234567.125')).toBe('1.234.567,125');
    for (const value of ['1.0001', 'NaN', '1e3', '0', '-1', '1000000'])
      expect(() => stockQuantity(value)).toThrow();
    expect(() => parseProduct({ ...product, available_stock: 1.5 })).toThrow('dados inválidos');
    expect(() => parseMovements({ items: [{ ...movement, kind: 'delete' }], total: 1 })).toThrow(
      'dados inválidos',
    );
  });
});
