import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { UserProfile } from './api';
import { PatientDocuments } from './PatientDocuments';
import type { PatientDocument } from './records-api';

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
const existing: PatientDocument = {
  id: 'doc-1',
  patient_id: 'patient-a',
  encounter_id: null,
  root_id: 'doc-1',
  version: 1,
  supersedes_id: null,
  correction_reason: null,
  kind: 'external_history',
  origin_name: 'Clínica anterior fictícia',
  origin_crmv: 'CRMV-CE 9999',
  document_date: '2026-10-01',
  summary: 'Castrado em 2025 (fictício)',
  file_name: 'historico.pdf',
  content_type: 'application/pdf',
  size_bytes: 204800,
  sha256: 'a'.repeat(64),
  author_id: vet.id,
  author_name: vet.name,
  author_crmv: 'CRMV-PI 1234',
  created_at: '2026-11-03T12:00:00Z',
};

function mockUpload() {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    const form = init?.body as FormData;
    return new Response(
      JSON.stringify({
        ...existing,
        id: 'doc-2',
        summary: form.get('summary'),
        file_name: null,
        content_type: null,
        size_bytes: null,
        sha256: null,
      }),
      { status: 201 },
    );
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}
function renderDocs(user = vet, documents = [existing], onSaved = vi.fn()) {
  render(
    <PatientDocuments
      token="mock"
      user={user}
      patientId="patient-a"
      documents={documents}
      encounters={[]}
      onSaved={onSaved}
    />,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Ver documentos e laudos' }));
  return onSaved;
}

describe('Documentos do paciente', () => {
  it('abre as versões em tela própria e volta à lista de documentos', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify([existing]))),
    );
    renderDocs(vet, [{ ...existing, version: 2 }]);
    fireEvent.click(screen.getByRole('button', { name: 'Ver versões anteriores' }));
    expect(await screen.findByRole('heading', { name: 'Versões do documento' })).toHaveFocus();
    expect(screen.queryByRole('button', { name: 'Adicionar documento' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Voltar' }));
    expect(screen.getByRole('button', { name: 'Adicionar documento' })).toBeVisible();
  });
  it('mostra origem, resumo e arquivo do documento', () => {
    renderDocs();
    expect(screen.getByText('Histórico de outro veterinário ou clínica')).toBeInTheDocument();
    expect(screen.getByText('Castrado em 2025 (fictício)')).toBeInTheDocument();
    expect(screen.getByText(/arquivo historico\.pdf \(200 KB\)/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Abrir arquivo' })).toBeInTheDocument();
  });

  it('salva só com resumo escrito, sem arquivo', async () => {
    const fetchMock = mockUpload();
    const onSaved = renderDocs(vet, []);
    fireEvent.click(screen.getByRole('button', { name: 'Adicionar documento' }));
    fireEvent.change(screen.getByLabelText('Origem (profissional, clínica ou laboratório)'), {
      target: { value: 'Laboratório fictício' },
    });
    fireEvent.change(screen.getByLabelText('Data do documento'), {
      target: { value: '2026-10-20' },
    });
    fireEvent.change(screen.getByLabelText('Resumo (opcional)'), {
      target: { value: 'Hemograma sem alterações' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar documento' }));
    expect(await screen.findByText('Documento adicionado.')).toBeInTheDocument();
    expect(onSaved).toHaveBeenCalled();
    const form = fetchMock.mock.calls[0]?.[1]?.body as FormData;
    expect(form.get('file')).toBeNull();
    expect(form.get('origin_crmv')).toBeNull();
    expect(form.get('summary')).toBe('Hemograma sem alterações');
  });

  it('pede arquivo ou resumo antes de enviar', () => {
    const fetchMock = mockUpload();
    renderDocs(vet, []);
    fireEvent.click(screen.getByRole('button', { name: 'Adicionar documento' }));
    fireEvent.change(screen.getByLabelText('Origem (profissional, clínica ou laboratório)'), {
      target: { value: 'Laboratório fictício' },
    });
    fireEvent.change(screen.getByLabelText('Data do documento'), {
      target: { value: '2026-10-20' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar documento' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Anexe um arquivo ou escreva um resumo');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('na correção, oferece manter o arquivo atual', () => {
    renderDocs();
    fireEvent.click(screen.getByRole('button', { name: 'Corrigir documento' }));
    expect(screen.getByLabelText(/Manter o arquivo atual \(historico\.pdf\)/)).toBeChecked();
    expect(screen.getByLabelText('Motivo da correção')).toBeRequired();
  });

  it('recepção não adiciona documentos', () => {
    renderDocs(reception, []);
    expect(screen.queryByRole('button', { name: 'Adicionar documento' })).toBeNull();
  });
});
