import { useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ActionScreen, ScreenArea, ScreenFeedback } from './Screen';

function Example() {
  const [detail, setDetail] = useState(false);
  const [edit, setEdit] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return (
    <ScreenArea>
      <h2>Lista de pacientes</h2>
      <label>
        Busca preservada
        <input defaultValue="Canina" />
      </label>
      <ScreenFeedback error={error} />
      <button onClick={() => setDetail(true)}>Ver paciente</button>
      {detail && (
        <ActionScreen title="Paciente fictício" onBack={() => setDetail(false)}>
          <p>Dados do paciente</p>
          <button onClick={() => setEdit(true)}>Editar paciente</button>
          {edit && (
            <ActionScreen
              title="Editar paciente"
              onBack={() => setEdit(false)}
              busy={busy}
              error={error}
            >
              <label>
                Nome editado
                <input defaultValue="Animal fictício" />
              </label>
              <button
                onClick={() => {
                  setError('Erro de validação');
                }}
              >
                Simular erro
              </button>
              <button onClick={() => setBusy(!busy)}>
                {busy ? 'Concluir' : 'Iniciar gravação'}
              </button>
            </ActionScreen>
          )}
        </ActionScreen>
      )}
    </ScreenArea>
  );
}

describe('Navegação interna compartilhada', () => {
  it('abre uma tela exclusiva sem desmontar ou perder os filtros da lista', () => {
    render(<Example />);
    const field = screen.getByLabelText('Busca preservada');
    fireEvent.change(field, { target: { value: 'Busca fictícia' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ver paciente' }));
    expect(screen.getByRole('heading', { name: 'Paciente fictício' })).toHaveFocus();
    expect(screen.queryByRole('heading', { name: 'Lista de pacientes' })).toBeNull();
    expect(field.isConnected).toBe(true);
    expect(field).not.toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Voltar' }));
    expect(screen.getByLabelText('Busca preservada')).toBe(field);
    expect(field).toHaveValue('Busca fictícia');
    expect(field).toBeVisible();
  });
  it('cada Voltar retorna à tela imediatamente anterior', () => {
    render(<Example />);
    fireEvent.click(screen.getByRole('button', { name: 'Ver paciente' }));
    fireEvent.click(screen.getByRole('button', { name: 'Editar paciente' }));
    expect(screen.getByRole('heading', { name: 'Editar paciente' })).toHaveFocus();
    expect(screen.queryByRole('heading', { name: 'Paciente fictício' })).toBeNull();
    expect(screen.getAllByRole('button', { name: 'Voltar' })).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Voltar' }));
    expect(screen.getByRole('heading', { name: 'Paciente fictício' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Voltar' }));
    expect(screen.getByRole('heading', { name: 'Lista de pacientes' })).toBeVisible();
  });
  it('erro permanece junto do formulário e preserva os campos', () => {
    render(<Example />);
    fireEvent.click(screen.getByRole('button', { name: 'Ver paciente' }));
    fireEvent.click(screen.getByRole('button', { name: 'Editar paciente' }));
    const input = screen.getByLabelText('Nome editado');
    fireEvent.change(input, { target: { value: 'Nome em revisão' } });
    fireEvent.click(screen.getByRole('button', { name: 'Simular erro' }));
    expect(screen.getAllByRole('alert')).toHaveLength(1);
    expect(screen.getByRole('alert')).toHaveTextContent('Erro de validação');
    expect(input).toHaveValue('Nome em revisão');
  });
  it('bloqueia Voltar enquanto a gravação está em andamento', () => {
    render(<Example />);
    fireEvent.click(screen.getByRole('button', { name: 'Ver paciente' }));
    fireEvent.click(screen.getByRole('button', { name: 'Editar paciente' }));
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar gravação' }));
    expect(screen.getByRole('button', { name: 'Voltar' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Voltar' }));
    expect(screen.getByRole('heading', { name: 'Editar paciente' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Concluir' }));
    expect(screen.getByRole('button', { name: 'Voltar' })).toBeEnabled();
  });
  it('restaura foco e posição da lista ao retornar', () => {
    render(<Example />);
    const trigger = screen.getByRole('button', { name: 'Ver paciente' });
    trigger.focus();
    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole('button', { name: 'Voltar' }));
    expect(trigger).toHaveFocus();
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'instant' });
  });
  it('remove telas ao trocar o contexto e não deixa saída bloqueada', async () => {
    const { rerender } = render(<Example />);
    fireEvent.click(screen.getByRole('button', { name: 'Ver paciente' }));
    rerender(
      <ScreenArea>
        <h2>Outra área</h2>
      </ScreenArea>,
    );
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Outra área' })).toBeVisible());
    expect(screen.queryByRole('button', { name: 'Voltar' })).toBeNull();
  });
  it('usa prioridade explícita para ações irmãs sobre um detalhe aberto', () => {
    render(
      <ScreenArea>
        <ActionScreen title="Editar produto" onBack={vi.fn()} layer={1}>
          <input aria-label="Nome do produto" />
        </ActionScreen>
        <ActionScreen title="Detalhe do produto" onBack={vi.fn()}>
          <p>Resumo</p>
        </ActionScreen>
      </ScreenArea>,
    );
    expect(screen.getByRole('heading', { name: 'Editar produto' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Detalhe do produto' })).toBeNull();
  });
});
