import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AiScribe } from './AiScribe';
import { parseDraft } from './ai-scribe-api';
import type { AiDraft } from './ai-scribe-api';
import type { UserProfile } from './api';

const vet: UserProfile = {
  id: 'vet-a',
  clinic_id: 'clinic-a',
  name: 'Veterinário fictício',
  role: 'veterinarian',
  active: true,
  crmv: '1234',
  crmv_state: 'PI',
};
const draft: AiDraft = {
  id: 'draft-1',
  patient_id: 'patient-a',
  encounter_id: 'encounter-a',
  source: 'text',
  transcript: 'Relato do responsável: Relato fictício original.',
  content: {
    complaint: 'Relato fictício original.',
    general_state: null,
    findings: null,
    presumptive_diagnosis: null,
    conclusive_diagnosis: null,
    procedures: null,
    prescription: null,
    follow_up: null,
    uncertainties: ['MOCK: revise os dados fornecidos.'],
  },
  requested_by: vet.id,
  llm_provider: 'mock',
  llm_model: 'mock-llm-v1',
  stt_provider: null,
  stt_model: null,
  prompt_version: 'scribe-pt-br-v1',
  status: 'pending',
  resolved_by: null,
  resolved_at: null,
  record_entry_id: null,
  created_at: '2030-01-01T12:00:00Z',
  simulated: true,
};
const encounters = [
  {
    id: 'encounter-a',
    started_at: '2030-01-01T12:00:00Z',
    completed_at: null,
    veterinarian_name: vet.name,
    appointment_id: null,
  },
];
const reviewLabel = 'Revisei a transcrição e todos os campos e assumo a autoria do registro.';

function mockApi({ empty = false, reject = false } = {}) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/patients/patient-a/ai-drafts')
      return new Response(JSON.stringify(empty ? [] : [draft]));
    if (url === '/api/encounters/encounter-a/ai-drafts')
      return new Response(JSON.stringify(draft), { status: 201 });
    if (url === '/api/ai-drafts/draft-1/approve')
      return new Response(
        JSON.stringify(
          reject
            ? { error: { message: 'Este rascunho já foi aprovado ou descartado.' } }
            : {
                ...draft,
                status: 'approved',
                resolved_by: vet.id,
                resolved_at: '2030-01-01T12:01:00Z',
                record_entry_id: 'entry-1',
              },
        ),
        { status: reject ? 409 : 200 },
      );
    if (url === '/api/ai-drafts/draft-1/discard' && init?.method === 'POST')
      return new Response(
        JSON.stringify({
          ...draft,
          status: 'discarded',
          resolved_by: vet.id,
          resolved_at: '2030-01-01T12:01:00Z',
        }),
      );
    return new Response('{}', { status: 404 });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function setup(user = vet) {
  const onApproved = vi.fn();
  render(
    <AiScribe
      token="mock"
      user={user}
      patientId="patient-a"
      encounters={encounters}
      onApproved={onApproved}
    />,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Abrir rascunhos' }));
  return onApproved;
}

async function editReview() {
  fireEvent.click(await screen.findByRole('button', { name: 'Revisar rascunho' }));
  fireEvent.change(screen.getByLabelText('Relato do responsável'), {
    target: { value: 'Relato revisado.' },
  });
  fireEvent.change(screen.getByLabelText('Estado geral e parâmetros'), {
    target: { value: 'Estado geral revisado.' },
  });
  fireEvent.change(screen.getByLabelText('Diagnóstico presuntivo'), {
    target: { value: 'Avaliação fictícia pelo veterinário.' },
  });
}

describe('Scribe simulado', () => {
  it('gera a partir de texto sem criar registro oficial', async () => {
    const fetchMock = mockApi({ empty: true });
    setup();
    expect(await screen.findByText('Nenhum rascunho para este paciente.')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Novo rascunho MOCK' }));
    fireEvent.change(screen.getByLabelText('Transcrição da consulta'), {
      target: { value: 'Relato do responsável: Relato fictício' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Gerar rascunho' }));
    expect(
      await screen.findByText('Rascunho MOCK gerado. Nenhum registro oficial foi criado.'),
    ).toBeVisible();
    const call = fetchMock.mock.calls.find(([url]) => url.endsWith('/encounter-a/ai-drafts'));
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      source: 'text',
      transcript: 'Relato do responsável: Relato fictício',
    });
    expect(
      fetchMock.mock.calls.some(
        ([url]) => url.includes('record-entries') || url.endsWith('/approve'),
      ),
    ).toBe(false);
  });

  it('oferece exemplo de transcrição sem entrada de arquivo de áudio', async () => {
    const fetchMock = mockApi({ empty: true });
    setup();
    await screen.findByText('Nenhum rascunho para este paciente.');
    fireEvent.click(screen.getByRole('button', { name: 'Novo rascunho MOCK' }));
    fireEvent.change(screen.getByLabelText('Entrada'), { target: { value: 'mock_audio' } });
    expect(screen.queryByLabelText('Transcrição da consulta')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Gerar rascunho' }));
    await screen.findByText('Rascunho MOCK gerado. Nenhum registro oficial foi criado.');
    const call = fetchMock.mock.calls.find(([url]) => url.endsWith('/encounter-a/ai-drafts'));
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      source: 'mock_audio',
      sample_id: 'consultation',
    });
  });

  it('exige confirmação da revisão e envia os valores editados antes de criar o registro', async () => {
    const fetchMock = mockApi();
    const onApproved = setup();
    await editReview();
    expect(screen.getByText(draft.transcript)).toBeVisible();
    expect(screen.getByText(/Diagnóstico presuntivo: não informado/)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Aprovar e registrar no prontuário' }));
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/approve'))).toBe(false);
    fireEvent.click(screen.getByLabelText(reviewLabel));
    fireEvent.click(screen.getByRole('button', { name: 'Aprovar e registrar no prontuário' }));
    expect(
      await screen.findByText('Rascunho aprovado. Registro oficial criado com sua autoria.'),
    ).toBeVisible();
    const call = fetchMock.mock.calls.find(([url]) => url.endsWith('/approve'));
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      review_confirmed: true,
      record: {
        complaint: 'Relato revisado.',
        general_state: 'Estado geral revisado.',
        presumptive_diagnosis: 'Avaliação fictícia pelo veterinário.',
      },
    });
    expect(onApproved).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: 'Aprovar e registrar no prontuário' })).toBeNull();
  });

  it('descarta sem exigir completar campos e sem aprovar', async () => {
    const fetchMock = mockApi();
    const onApproved = setup();
    fireEvent.click(await screen.findByRole('button', { name: 'Revisar rascunho' }));
    fireEvent.click(screen.getByRole('button', { name: 'Descartar rascunho' }));
    expect(
      await screen.findByText('Rascunho descartado. Nenhum registro oficial foi criado.'),
    ).toBeVisible();
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/approve'))).toBe(false);
    expect(onApproved).not.toHaveBeenCalled();
  });

  it('administrador consulta a transcrição e o original sem ações de escrita', async () => {
    mockApi();
    setup({ ...vet, role: 'admin' });
    fireEvent.click(await screen.findByRole('button', { name: 'Ver rascunho' }));
    expect(screen.getByText(draft.transcript)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Novo rascunho MOCK' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Aprovar e registrar no prontuário' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Descartar rascunho' })).toBeNull();
  });

  it('mostra conflito sem informar aprovação bem-sucedida', async () => {
    mockApi({ reject: true });
    const onApproved = setup();
    await editReview();
    fireEvent.click(screen.getByLabelText(reviewLabel));
    fireEvent.click(screen.getByRole('button', { name: 'Aprovar e registrar no prontuário' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('já foi aprovado ou descartado');
    expect(onApproved).not.toHaveBeenCalled();
  });

  it('recusa conteúdo inválido retornado pela API', () => {
    expect(() =>
      parseDraft({ ...draft, content: { ...draft.content, general_state: 10 } }),
    ).toThrow('dados inválidos');
  });
});
