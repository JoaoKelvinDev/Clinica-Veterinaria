import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { UserProfile } from './api';
import { Messaging } from './Messaging';
import type { MessagingOverview } from './messaging-api';

const reception: UserProfile = {
  id: 'reception-a',
  clinic_id: 'clinic-a',
  name: 'Recepção fictícia',
  role: 'reception',
  active: true,
  crmv: null,
  crmv_state: null,
};
const vet: UserProfile = { ...reception, id: 'vet-a', role: 'veterinarian', crmv: '1' };
const overview: MessagingOverview = {
  provider: 'mock',
  simulated: true,
  attention: [
    {
      id: 'msg-in',
      direction: 'inbound',
      status: 'received',
      phone: '+5586999990000',
      body: 'Posso levar a ração dele?',
      tutor_id: 'tutor-a',
      tutor_name: 'Maria Fictícia',
      patient_id: null,
      appointment_id: null,
      intent: 'unknown',
      needs_attention: true,
      handled_at: null,
      created_at: '2030-01-09T15:00:00Z',
    },
  ],
  upcoming: [
    {
      id: 'job-1',
      kind: 'appointment_reminder',
      status: 'pending',
      due_at: '2030-01-10T11:00:00Z',
      event_at: '2030-01-10T12:00:00Z',
      patient_id: 'patient-a',
      patient_name: 'Thor fictício',
      outcome: null,
      sent_at: null,
    },
  ],
  recent_reminders: [],
  messages: [],
};

function mockApi() {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/messaging') return new Response(JSON.stringify(overview));
    if (url === '/api/messaging/mock-inbound' && init?.method === 'POST')
      return new Response(
        JSON.stringify({
          ...overview.attention[0],
          id: 'msg-2',
          intent: 'confirm',
          needs_attention: false,
        }),
        { status: 201 },
      );
    return new Response('{}', { status: 404 });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('Mensagens', () => {
  it('mostra respostas para a equipe e próximos lembretes, avisando o modo MOCK', async () => {
    mockApi();
    render(<Messaging token="mock" user={reception} />);
    expect(await screen.findByText('Posso levar a ração dele?')).toBeInTheDocument();
    expect(screen.getByText(/Modo de testes \(MOCK\)/)).toBeInTheDocument();
    expect(screen.getByText('Lembrete de consulta')).toBeInTheDocument();
    expect(screen.getByText('Thor fictício')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Marcar como resolvida' })).toBeInTheDocument();
  });

  it('simula a resposta do tutor', async () => {
    const fetchMock = mockApi();
    render(<Messaging token="mock" user={reception} />);
    fireEvent.click(
      await screen.findByRole('button', { name: 'Simular resposta do tutor (MOCK)' }),
    );
    fireEvent.change(await screen.findByLabelText('Telefone do tutor'), {
      target: { value: '(86) 99999-0000' },
    });
    fireEvent.change(screen.getByLabelText('Resposta'), { target: { value: 'Confirmo' } });
    fireEvent.click(screen.getByRole('button', { name: 'Registrar resposta' }));
    expect(await screen.findByText('Resposta processada: Confirmou.')).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([url]) => url === '/api/messaging/mock-inbound');
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      phone: '(86) 99999-0000',
      body: 'Confirmo',
    });
  });

  it('veterinário só consulta', async () => {
    mockApi();
    render(<Messaging token="mock" user={vet} />);
    expect(await screen.findByText('Thor fictício')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Marcar como resolvida' })).toBeNull();
    expect(screen.queryByLabelText('Telefone do tutor')).toBeNull();
  });
});
