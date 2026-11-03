import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Tutors } from './Tutors';
import { Patients } from './Patients';
import { PatientTutors } from './PatientTutors';
import { App } from './App';
import type { Patient, Tutor } from './registry-api';

const tutor: Tutor = {
  id: 't-a',
  clinic_id: 'c-a',
  name: 'Tutor fictício',
  phone: '+5586999999999',
  document: null,
  address: null,
  whatsapp_opt_in: false,
  whatsapp_opt_in_at: null,
  whatsapp_opt_in_source: null,
  whatsapp_opt_out_at: null,
  deleted_at: null,
};
const patient: Patient = {
  id: 'p-a',
  clinic_id: 'c-a',
  name: 'Paciente fictício',
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
function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status });
}
function change(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe('Cadastros de tutores e animais', () => {
  it('cadastra tutor com autorização explícita e origem', async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) =>
      init?.method === 'POST' ? json(tutor, 201) : json({ items: [], total: 0 }),
    );
    vi.stubGlobal('fetch', fetchMock);
    render(<Tutors token="mock" canWrite />);
    await screen.findByText('Nenhum tutor encontrado.');
    fireEvent.click(screen.getByRole('button', { name: 'Novo tutor' }));
    change('Nome do tutor', 'Tutor fictício');
    change('Telefone com DDD', '(86) 99999-9999');
    fireEvent.click(screen.getByLabelText('O tutor autorizou receber mensagens'));
    change('Origem da autorização', 'Autorização presencial fictícia');
    fireEvent.click(screen.getByRole('button', { name: 'Salvar tutor' }));
    expect(await screen.findByText('Cadastro do tutor salvo.')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tutors',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          name: tutor.name,
          phone: '(86) 99999-9999',
          document: null,
          address: null,
          whatsapp_consent: { granted: true, source: 'Autorização presencial fictícia' },
        }),
      }),
    );
  });

  it('exige nova autorização ao trocar telefone e informa falha parcial no consentimento', async () => {
    const opted = {
      ...tutor,
      whatsapp_opt_in: true,
      whatsapp_opt_in_source: 'Presencial',
      whatsapp_opt_in_at: '2026-01-01T00:00:00Z',
    };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        if (init?.method === 'PATCH')
          return json({ ...opted, phone: '+5511961234567', whatsapp_opt_in: false });
        if (init?.method === 'PUT')
          return json({ error: { message: 'Falha ao registrar autorização.' } }, 503);
        return json({ items: [opted], total: 1 });
      }),
    );
    render(<Tutors token="mock" canWrite />);
    fireEvent.click(await screen.findByRole('button', { name: `Editar tutor ${tutor.name}` }));
    change('Telefone com DDD', '+5511961234567');
    expect(screen.getByLabelText('O tutor autorizou receber mensagens')).not.toBeChecked();
    fireEvent.click(screen.getByLabelText('O tutor autorizou receber mensagens'));
    change('Origem da autorização', 'Nova autorização presencial');
    fireEvent.click(screen.getByRole('button', { name: 'Salvar tutor' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'O cadastro foi salvo, mas a autorização não foi atualizada.',
    );
    expect(screen.queryByText('Cadastro do tutor salvo.')).not.toBeInTheDocument();
  });

  it('permite consulta sem disponibilizar escrita a perfis de leitura', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json({ items: [tutor], total: 1 })),
    );
    render(<Tutors token="mock" canWrite={false} />);
    expect(await screen.findByText(tutor.name)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Novo tutor' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Editar tutor/ })).not.toBeInTheDocument();
  });

  it('mantém formulário aberto e não anuncia sucesso quando o backend rejeita cadastro', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) =>
        init?.method === 'POST'
          ? json({ error: { message: 'Telefone inválido.' } }, 422)
          : json({ items: [], total: 0 }),
      ),
    );
    render(<Tutors token="mock" canWrite />);
    await screen.findByText('Nenhum tutor encontrado.');
    fireEvent.click(screen.getByRole('button', { name: 'Novo tutor' }));
    change('Nome do tutor', tutor.name);
    change('Telefone com DDD', '123');
    fireEvent.click(screen.getByRole('button', { name: 'Salvar tutor' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Telefone inválido.');
    expect(screen.getByLabelText('Nome do tutor')).toHaveValue(tutor.name);
  });

  it('cadastra paciente com idade estimada e abre seus vínculos', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/tutors')) return json([]);
      if (init?.method === 'POST')
        return json({ ...patient, estimated_age_months: 12, neutered: true }, 201);
      return json({ items: [], total: 0 });
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<Patients token="mock" canWrite onOpenRecord={() => {}} />);
    await screen.findByText('Nenhum paciente encontrado.');
    fireEvent.click(screen.getByRole('button', { name: 'Novo paciente' }));
    change('Nome do paciente', patient.name);
    change('Espécie', patient.species);
    change('Castrado', 'yes');
    change('Idade estimada (meses)', '12');
    fireEvent.click(screen.getByRole('button', { name: 'Salvar paciente' }));
    expect(
      await screen.findByRole('heading', { name: `Tutores de ${patient.name}` }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/patients',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"estimated_age_months":12'),
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/patients',
      expect.objectContaining({ body: expect.stringContaining('"neutered":true') }),
    );
  });

  it('vincula outro tutor como principal sem duplicar o primeiro', async () => {
    const another = { ...tutor, id: 't-b', name: 'Outro tutor fictício' };
    const first = { id: 'link-a', is_primary: true, tutor };
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.startsWith('/api/tutors?')) return json({ items: [tutor, another], total: 2 });
      if (init?.method === 'POST')
        return json([
          { ...first, is_primary: false },
          { id: 'link-b', is_primary: true, tutor: another },
        ]);
      return json([first]);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<PatientTutors patient={patient} token="mock" canWrite onClose={vi.fn()} />);
    await screen.findByText(tutor.name);
    fireEvent.click(screen.getByRole('button', { name: 'Buscar tutores' }));
    fireEvent.click(
      await screen.findByRole('checkbox', { name: 'Definir novo vínculo como principal' }),
    );
    fireEvent.click(await screen.findByRole('button', { name: `Vincular ${another.name}` }));
    expect(await screen.findByText('Vínculo salvo.')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/patients/${patient.id}/tutors`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ tutor_id: 't-b', is_primary: true }),
      }),
    );
    expect(screen.getAllByText('Principal')).toHaveLength(1);
  });

  it('exibe tutor arquivado nos vínculos e só remove após confirmação', async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) =>
      init?.method === 'DELETE'
        ? new Response(null, { status: 204 })
        : json([
            {
              id: 'link-a',
              is_primary: true,
              tutor: { ...tutor, deleted_at: '2026-01-01T00:00:00Z' },
            },
          ]),
    );
    vi.stubGlobal('fetch', fetchMock);
    render(<PatientTutors patient={patient} token="mock" canWrite onClose={vi.fn()} />);
    expect(await screen.findByText('Arquivado')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: `Remover vínculo com ${tutor.name}` }));
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ method: 'DELETE' }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar remoção do vínculo' }));
    expect(await screen.findByText('Vínculo removido.')).toBeInTheDocument();
  });

  it('abre cadastros pela navegação de recepção', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url === '/api/health') return json({ status: 'ok' });
        if (url === '/api/me')
          return json({
            user: {
              id: 'u-a',
              clinic_id: 'c-a',
              name: 'Recepção fictícia',
              role: 'reception',
              active: true,
              crmv: null,
              crmv_state: null,
            },
            clinic: { id: 'c-a', name: 'Clínica fictícia' },
          });
        return json({ items: [], total: 0 });
      }),
    );
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
    fireEvent.click(await screen.findByRole('button', { name: 'Tutores' }));
    expect(await screen.findByRole('button', { name: 'Novo tutor' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Animais' }));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Novo paciente' })).toBeInTheDocument(),
    );
  });
});
