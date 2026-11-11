import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { LoginScreen } from './LoginScreen';

vi.mock('./environment', () => ({
  isDemonstration: true,
  environmentLabel: 'Demonstração — dados fictícios',
}));

function loginScreen(configured = true) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'ok' }))));
  return render(
    <LoginScreen
      configured={configured}
      loading={false}
      busy={false}
      hasSession={false}
      error=""
      sessionAction={null}
      onSubmit={vi.fn()}
    />,
  );
}

describe('Entrada da demonstração', () => {
  it('identifica os dados fictícios e os serviços simulados antes do login', async () => {
    loginScreen();
    expect(screen.getByRole('note')).toHaveTextContent('Demonstração — dados fictícios');
    expect(screen.getByRole('note')).toHaveTextContent('IA e WhatsApp são simulados');
    expect(await screen.findByText('Sistema disponível')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeEnabled();
  });

  it('orienta sobre configuração ausente e impede o envio das credenciais', () => {
    loginScreen(false);
    expect(screen.getByRole('alert')).toHaveTextContent('O acesso ainda não está configurado');
    expect(screen.getByLabelText('E-mail')).toBeDisabled();
    expect(screen.getByLabelText('Senha')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeDisabled();
  });
});
