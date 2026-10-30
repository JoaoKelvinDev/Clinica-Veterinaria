import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';

describe('Tela inicial', () => {
  it('mostra disponibilidade após confirmar a resposta da API', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'ok' })));
    vi.stubGlobal('fetch', fetchMock);
    render(<App auth={null} />);

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    expect(await screen.findByText('Sistema disponível')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/health',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it('informa quando não consegue alcançar a API', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    render(<App auth={null} />);

    expect(await screen.findByText('Não foi possível conectar ao sistema')).toBeInTheDocument();
    expect(screen.queryByText('Sistema disponível')).not.toBeInTheDocument();
  });

  it.each([
    new Response('erro', { status: 503 }),
    new Response(JSON.stringify({ status: 'error' })),
    new Response('JSON inválido'),
  ])('recusa resposta com erro ou conteúdo inválido (%#)', async (response) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
    render(<App auth={null} />);

    expect(await screen.findByText('Não foi possível conectar ao sistema')).toBeInTheDocument();
  });
});
