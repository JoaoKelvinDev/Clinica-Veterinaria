import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { UserProfile } from './api';
import { Scheduling } from './Scheduling';
import { localDateTime, utcDateTime } from './scheduling-api';
import type { Appointment, Encounter } from './scheduling-api';

const admin: UserProfile = {
  id: 'admin-a',
  clinic_id: 'clinic-a',
  name: 'Administrador fictício',
  role: 'admin',
  active: true,
  crmv: null,
  crmv_state: null,
};
const vet: UserProfile = {
  ...admin,
  id: 'vet-a',
  name: 'Veterinário fictício',
  role: 'veterinarian',
  crmv: '1234',
  crmv_state: 'PI',
};
const booking: Appointment = {
  id: 'booking-a',
  clinic_id: 'clinic-a',
  patient_id: 'patient-a',
  patient_name: 'Paciente fictício',
  veterinarian_id: vet.id,
  veterinarian_name: vet.name,
  starts_at: '2030-01-01T12:00:00Z',
  ends_at: '2030-01-01T13:00:00Z',
  kind: 'Consulta',
  status: 'scheduled',
  encounter_id: null,
};
const encounter: Encounter = {
  id: 'encounter-a',
  clinic_id: 'clinic-a',
  patient_id: booking.patient_id,
  patient_name: booking.patient_name,
  veterinarian_id: vet.id,
  veterinarian_name: vet.name,
  appointment_id: booking.id,
  started_at: '2030-01-01T12:00:00Z',
  completed_at: null,
};
function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status });
}
function change(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}
function mockApi(overrides?: (url: string, init?: RequestInit) => Response | undefined) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const override = overrides?.(url, init);
    if (override) return override;
    if (url === '/api/veterinarians') return json([vet]);
    if (url.startsWith('/api/appointments?'))
      return json({ items: [booking], total: 1, timezone: 'America/Fortaleza' });
    if (url.startsWith('/api/encounters?'))
      return json({ items: [encounter], total: 1, timezone: 'America/Fortaleza' });
    if (url.startsWith('/api/patients?'))
      return json({
        items: [
          {
            id: booking.patient_id,
            clinic_id: booking.clinic_id,
            name: booking.patient_name,
            species: 'Canina',
            breed: null,
            sex: 'unknown',
            neutered: null,
            birth_date: null,
            estimated_age_months: null,
            coat: null,
            microchip: null,
            notes: null,
          },
        ],
        total: 1,
      });
    if (url.endsWith('/start')) return json(encounter);
    if (url.endsWith('/complete'))
      return json({ ...encounter, completed_at: '2030-01-01T13:00:00Z' });
    if (url === '/api/appointments') return json(booking, 201);
    if (url.endsWith('/status')) return json({ ...booking, status: 'cancelled' });
    if (url === '/api/encounters') return json(encounter, 201);
    return json({ error: { message: 'Rota inesperada no teste.' } }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('Agenda e atendimentos', () => {
  it('converte horários no fuso da clínica independentemente do fuso do navegador', () => {
    expect(utcDateTime('2030-01-01T09:00')).toBe('2030-01-01T12:00:00.000Z');
    expect(localDateTime('2030-01-02T02:30:00Z')).toBe('2030-01-01T23:30');
  });

  it('filtra por dia e veterinário', async () => {
    const fetchMock = mockApi();
    render(<Scheduling token="mock" user={admin} />);
    await screen.findByRole('button', { name: `Reagendar ${booking.patient_name}` });
    change('Dia da agenda', '2030-01-01');
    change('Filtrar por veterinário', vet.id);
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/appointments?day=2030-01-01&veterinarian_id=vet-a&limit=20&offset=0',
        expect.anything(),
      ),
    );
  });

  it('agenda com paciente pesquisado e envia horários UTC', async () => {
    const fetchMock = mockApi();
    render(<Scheduling token="mock" user={admin} />);
    await screen.findByRole('button', { name: `Reagendar ${booking.patient_name}` });
    fireEvent.click(screen.getByRole('button', { name: 'Novo agendamento' }));
    change('Buscar paciente por nome ou microchip', 'Paciente');
    fireEvent.click(screen.getByRole('button', { name: 'Buscar pacientes' }));
    await screen.findByRole('option', { name: 'Paciente fictício · Canina' });
    change('Paciente', booking.patient_id);
    change('Veterinário responsável', vet.id);
    change('Início', '2030-01-01T09:00');
    change('Fim', '2030-01-01T10:00');
    fireEvent.click(screen.getByRole('button', { name: 'Salvar agendamento' }));
    expect(await screen.findByText(/Agendamento salvo/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/appointments',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          patient_id: booking.patient_id,
          veterinarian_id: vet.id,
          starts_at: '2030-01-01T12:00:00.000Z',
          ends_at: '2030-01-01T13:00:00.000Z',
          kind: 'Consulta',
        }),
      }),
    );
  });

  it('mantém edição e informa conflito devolvido pelo backend', async () => {
    mockApi((url, init) =>
      url === `/api/appointments/${booking.id}` && init?.method === 'PATCH'
        ? json(
            { error: { message: 'O veterinário já possui um agendamento nesse intervalo.' } },
            409,
          )
        : undefined,
    );
    render(<Scheduling token="mock" user={admin} />);
    fireEvent.click(
      await screen.findByRole('button', { name: `Reagendar ${booking.patient_name}` }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Salvar agendamento' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('já possui um agendamento');
    expect(screen.getByRole('heading', { name: 'Reagendar consulta' })).toBeInTheDocument();
    expect(screen.queryByText(/Agendamento salvo/)).not.toBeInTheDocument();
  });

  it('só cancela depois de confirmação explícita', async () => {
    const fetchMock = mockApi();
    render(<Scheduling token="mock" user={admin} />);
    fireEvent.click(
      await screen.findByRole('button', { name: `Cancelar ${booking.patient_name}` }),
    );
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining('/status'),
      expect.anything(),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar operação' }));
    expect(await screen.findByText('Cancelar consulta: operação concluída.')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/appointments/${booking.id}/status`,
      expect.objectContaining({ method: 'PUT', body: '{"status":"cancelled"}' }),
    );
  });

  it('oferece início e conclusão apenas ao veterinário responsável', async () => {
    const fetchMock = mockApi();
    render(<Scheduling token="mock" user={vet} />);
    expect(
      await screen.findByRole('button', { name: `Iniciar ${booking.patient_name}` }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Novo agendamento' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: `Concluir ${booking.patient_name}` }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar operação' }));
    expect(
      await screen.findByText('Concluir atendimento: operação concluída.'),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/encounters/encounter-a/complete',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it.each([
    { ...admin, role: 'assistant' as const },
    { ...vet, id: 'outro-vet' },
  ])('restringe ações de atendimento para $id / $role', async (user) => {
    mockApi();
    render(<Scheduling token="mock" user={user} />);
    await screen.findByText('Consultas agendadas');
    await screen.findByText('Agendado', { selector: '.status-tag' });
    expect(
      screen.queryByRole('button', { name: `Iniciar ${booking.patient_name}` }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: `Concluir ${booking.patient_name}` }),
    ).not.toBeInTheDocument();
  });

  it('remove dados do dia anterior quando falha ao carregar o novo filtro', async () => {
    mockApi((url) =>
      url.startsWith('/api/appointments?day=2030-02-01')
        ? json({ error: { message: 'Falha ao carregar a agenda.' } }, 503)
        : undefined,
    );
    render(<Scheduling token="mock" user={admin} />);
    await screen.findByRole('button', { name: `Reagendar ${booking.patient_name}` });
    change('Dia da agenda', '2030-02-01');
    expect(await screen.findByRole('alert')).toHaveTextContent('Falha ao carregar a agenda.');
    expect(
      screen.queryByRole('button', { name: `Reagendar ${booking.patient_name}` }),
    ).not.toBeInTheDocument();
  });
});
