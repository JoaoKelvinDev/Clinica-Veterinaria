import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { UserProfile } from './api';
import { Records } from './Records';
import type { PatientRecord, RecordEntry } from './records-api';

const vet: UserProfile = {
  id: 'vet-a',
  clinic_id: 'clinic-a',
  name: 'Veterinário fictício',
  role: 'veterinarian',
  active: true,
  crmv: '1234',
  crmv_state: 'PI',
};
const reception: UserProfile = { ...vet, id: 'reception-a', role: 'reception', crmv: null };
const target = { patientId: 'patient-a', patientName: 'Paciente fictício' };
const entry: RecordEntry = {
  id: 'entry-1',
  patient_id: 'patient-a',
  encounter_id: 'encounter-a',
  root_id: 'entry-1',
  version: 1,
  supersedes_id: null,
  correction_reason: null,
  author_id: vet.id,
  author_name: vet.name,
  author_crmv: 'CRMV-PI 1234',
  created_at: '2030-01-01T12:10:00Z',
  location: 'Clínica fictícia',
  complaint: 'Relato fictício',
  general_state: 'Alerta',
  findings: null,
  presumptive_diagnosis: 'Suspeita fictícia',
  conclusive_diagnosis: null,
  procedures: null,
  prescription: null,
  follow_up: null,
  follow_up_on: null,
};
const full: PatientRecord = {
  patient_id: 'patient-a',
  clinical_access: true,
  encounters: [
    {
      id: 'encounter-a',
      started_at: '2030-01-01T12:00:00Z',
      completed_at: null,
      veterinarian_name: vet.name,
      appointment_id: null,
    },
  ],
  entries: [entry],
  weights: [
    {
      id: 'weight-1',
      weight_grams: 12500,
      supersedes_id: null,
      correction_reason: null,
      author_id: vet.id,
      author_name: vet.name,
      created_at: '2030-01-01T12:05:00Z',
    },
  ],
  vaccines: [],
  documents: [],
};
const tutorLink = {
  id: 'link-a',
  is_primary: true,
  tutor: {
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
  },
};
function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status });
}
function mockApi(record: PatientRecord) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/patients/patient-a/record') return json(record);
    if (url === '/api/patients/patient-a/tutors') return json([tutorLink]);
    if (url === '/api/encounters/encounter-a/record-entries' && init?.method === 'POST')
      return json({ ...entry, id: 'entry-2', version: 2 }, 201);
    return json({ error: { message: 'Rota inesperada no teste.' } }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('Prontuário', () => {
  it('mostra registros, autoria, peso e aviso de cadastro incompleto', async () => {
    mockApi(full);
    render(<Records token="mock" user={vet} target={target} onClose={() => {}} />);
    expect(await screen.findByText('Suspeita fictícia')).toBeInTheDocument();
    expect(screen.getByText(/registrada por Veterinário fictício \(CRMV-PI 1234\)/)).toBeVisible();
    expect(screen.getByText('12,5 kg')).toBeInTheDocument();
    expect(screen.getByText(/sem CPF ou endereço/)).toBeInTheDocument();
  });

  it('corrige criando uma nova versão com motivo', async () => {
    const fetchMock = mockApi(full);
    render(<Records token="mock" user={vet} target={target} onClose={() => {}} />);
    const scrolled = vi.fn();
    Element.prototype.scrollIntoView = scrolled;
    fireEvent.click(await screen.findByRole('button', { name: 'Corrigir registro' }));
    expect(screen.getByRole('heading', { name: 'Corrigir versão 1' })).toBeInTheDocument();
    // O formulário abre longe do botão: a tela rola até ele e foca o primeiro campo.
    expect(scrolled).toHaveBeenCalled();
    expect(screen.getByLabelText('Local do atendimento')).toHaveFocus();
    fireEvent.change(screen.getByLabelText('Diagnóstico presuntivo'), {
      target: { value: 'Suspeita corrigida' },
    });
    fireEvent.change(screen.getByLabelText('Motivo da correção'), {
      target: { value: 'Erro de digitação' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar registro' }));
    expect(await screen.findByText('Correção registrada como nova versão.')).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      supersedes_id: 'entry-1',
      correction_reason: 'Erro de digitação',
      presumptive_diagnosis: 'Suspeita corrigida',
    });
  });

  it('não oferece registro clínico à recepção', async () => {
    mockApi({ ...full, clinical_access: false, entries: [], weights: [] });
    render(<Records token="mock" user={reception} target={target} onClose={() => {}} />);
    expect(await screen.findByText(/vê somente as datas/)).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Novo registro clínico' })).toBeNull(),
    );
    expect(screen.queryByRole('heading', { name: 'Pesagens' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Abrir rascunhos' })).toBeNull();
  });
});
