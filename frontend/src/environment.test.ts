import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe('Configuração da demonstração', () => {
  it.each([
    ['true', 'Demonstração — dados fictícios', 4],
    ['false', 'Desenvolvimento local', 10],
    [undefined, 'Desenvolvimento local', 10],
  ] as const)('aplica o limite de anexos ao modo %s', async (value, label, megabytes) => {
    vi.resetModules();
    vi.stubEnv('VITE_DEMO_MODE', value);
    const environment = await import('./environment');
    const records = await import('./records-api');
    expect(environment.environmentLabel).toBe(label);
    expect(records.maxDocumentBytes).toBe(megabytes * 1024 * 1024);
  });
});
