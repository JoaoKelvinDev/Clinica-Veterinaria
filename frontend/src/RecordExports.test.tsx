import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { RecordExports } from './RecordExports';
import type { UserProfile } from './api';
import { downloadRecordExport, parseExport } from './record-exports-api';

const user: UserProfile = {
  id: 'vet-a',
  clinic_id: 'clinic-a',
  name: 'Veterinário fictício',
  role: 'veterinarian',
  active: true,
  crmv: '1234',
  crmv_state: 'PI',
};
const exported = {
  id: 'export-a',
  patient_id: 'patient-a',
  author_name: user.name,
  author_crmv: 'CRMV-PI 1234',
  tutor_name: 'Tutor fictício',
  created_at: '2030-01-01T12:00:00Z',
  sha256: 'a'.repeat(64),
  size_bytes: 5000,
  attachment_count: 1,
  missing_file_count: 1,
};
const responsible = {
  id: 'tutor-a',
  clinic_id: 'clinic-a',
  name: 'Tutor fictício',
  document: '12345678909',
  address: 'Rua Fictícia, 10',
  phone: null,
  whatsapp_opt_in: false,
  whatsapp_opt_in_at: null,
  whatsapp_opt_in_source: null,
  whatsapp_opt_out_at: null,
  deleted_at: null,
};
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function mockApi({ reject = false, incomplete = false, total = 1 } = {}) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/options'))
      return json({
        clinic_name: 'Clínica fictícia',
        patient_name: 'Paciente fictício',
        tutors: [
          {
            id: 'link-a',
            is_primary: true,
            tutor: { ...responsible, ...(incomplete ? { address: null } : {}) },
          },
        ],
      });
    if (init?.method === 'POST')
      return reject
        ? json({ error: { message: 'Complete os dados do responsável.' } }, 422)
        : json(exported, 201);
    if (url.endsWith('/file'))
      return new Response('%PDF-1.7 fictício', { headers: { 'Content-Type': 'application/pdf' } });
    if (url.endsWith('/package'))
      return new Response('ZIP fictício', { headers: { 'Content-Type': 'application/zip' } });
    return json({ items: [exported], total });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}
async function open(role = user.role) {
  render(<RecordExports token="mock" user={{ ...user, role }} patientId="patient-a" />);
  fireEvent.click(screen.getByRole('button', { name: 'Ver exportações em PDF' }));
  await screen.findByText('Responsável: Tutor fictício · 1 arquivo(s) original(is)');
}
async function prepare() {
  fireEvent.click(screen.getByRole('button', { name: 'Preparar novo PDF' }));
  await screen.findByRole('heading', { name: 'Preparar cópia do prontuário' });
}
function fill() {
  const fields: [string, string][] = [
    ['Endereço profissional', 'Rua Fictícia, 100'],
    ['Telefone profissional', '(86) 99999-1234'],
    ['E-mail profissional', 'vet@example.test'],
    ['Razão social', 'Clínica fictícia LTDA'],
    ['CNPJ', '12345678000190'],
    ['Registro do estabelecimento no CRMV', 'CRMV-PI PJ 123'],
  ];
  for (const [label, value] of fields)
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  fireEvent.click(
    screen.getByLabelText(
      'Conferi os dados e estou ciente de que a cópia precisa de assinatura e entrega manuais.',
    ),
  );
}
afterEach(() => vi.restoreAllMocks());

describe('Exportações do prontuário', () => {
  it('carrega ao abrir e informa assinatura manual e originais ausentes', async () => {
    const fetchMock = mockApi();
    render(<RecordExports token="mock" user={user} patientId="patient-a" />);
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Ver exportações em PDF' }));
    expect(
      await screen.findByText('1 documento(s) registrado(s) sem arquivo original.'),
    ).toBeVisible();
    expect(
      screen.getByText(/Os PDFs são gerados sem assinatura digital incorporada/),
    ).toBeVisible();
  });
  it('prepara a emissão com dados profissionais e ciência explícita', async () => {
    const fetchMock = mockApi();
    await open();
    await prepare();
    fill();
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar preparação do PDF' }));
    expect(await screen.findByText(/Cópia preparada e preservada/)).toBeVisible();
    const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      tutor_id: responsible.id,
      professional_address: 'Rua Fictícia, 100',
      professional_phone: '(86) 99999-1234',
      professional_email: 'vet@example.test',
      establishment_legal_name: 'Clínica fictícia LTDA',
      establishment_cnpj: '12345678000190',
      establishment_crmv: 'CRMV-PI PJ 123',
      acknowledge_unsigned: true,
    });
    expect(screen.queryByRole('button', { name: 'Confirmar preparação do PDF' })).toBeNull();
  });
  it('permite emissão sem pessoa jurídica e remove os campos correspondentes', async () => {
    const fetchMock = mockApi();
    await open();
    await prepare();
    fill();
    fireEvent.click(screen.getByLabelText('Identificar estabelecimento (pessoa jurídica)'));
    expect(screen.queryByLabelText('CNPJ')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar preparação do PDF' }));
    await screen.findByText(/Cópia preparada e preservada/);
    const body = JSON.parse(
      String(fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')?.[1]?.body),
    );
    expect(body.establishment_cnpj).toBeNull();
    expect(body.establishment_legal_name).toBeNull();
  });
  it('cadastro incompleto bloqueia preparação', async () => {
    mockApi({ incomplete: true });
    await open();
    await prepare();
    expect(screen.getByText(/Complete CPF e endereço no cadastro/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Confirmar preparação do PDF' })).toBeDisabled();
  });
  it('falha preserva formulário sem anunciar emissão concluída', async () => {
    mockApi({ reject: true });
    await open();
    await prepare();
    fill();
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar preparação do PDF' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Complete os dados do responsável.');
    expect(screen.getByLabelText('Endereço profissional')).toHaveValue('Rua Fictícia, 100');
    expect(screen.queryByText(/Cópia preparada e preservada/)).toBeNull();
  });
  it.each(['admin', 'assistant'] as const)('%s baixa cópias, sem emitir', async (role) => {
    mockApi();
    await open(role);
    expect(screen.queryByRole('button', { name: 'Preparar novo PDF' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Baixar PDF' })).toBeVisible();
  });
  it('recepção não recebe acesso à exportação', () => {
    const fetchMock = mockApi();
    render(
      <RecordExports token="mock" user={{ ...user, role: 'reception' }} patientId="patient-a" />,
    );
    expect(screen.queryByRole('button')).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it.each([
    ['Baixar PDF', 'application/pdf'],
    ['Baixar PDF e anexos (ZIP)', 'application/zip'],
  ])('baixa %s sem afirmar recebimento', async (name, type) => {
    mockApi();
    const create = vi.fn((blob: Blob) => `blob:${blob.type}`);
    vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: vi.fn() });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    await open();
    fireEvent.click(screen.getByRole('button', { name }));
    expect(await screen.findByText(/Download solicitado/)).toBeVisible();
    expect(click).toHaveBeenCalledOnce();
    const blob = create.mock.calls[0]?.[0];
    expect(blob?.type).toBe(type);
  });
  it('pagina as emissões e oferece atualização', async () => {
    const fetchMock = mockApi({ total: 25 });
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Mais exportações' }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => url.includes('offset=20'))).toBe(true),
    );
    expect(screen.getByRole('button', { name: 'Atualizar exportações' })).toBeVisible();
  });
  it('rejeita arquivo com tipo inesperado e resposta inválida', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('<html/>', { headers: { 'Content-Type': 'text/html' } })),
    );
    await expect(downloadRecordExport('mock', exported.id, 'file')).rejects.toThrow(
      'Tipo de arquivo inesperado',
    );
    expect(() => parseExport({ ...exported, sha256: 'invalido' })).toThrow('dados inválidos');
  });
});
