export type Role = 'admin' | 'veterinarian' | 'assistant' | 'reception';
export const roleLabels: Record<Role, string> = {
  admin: 'Administrador',
  veterinarian: 'Veterinário',
  assistant: 'Auxiliar',
  reception: 'Recepção',
};
export interface UserProfile {
  id: string;
  clinic_id: string;
  name: string;
  role: Role;
  active: boolean;
  crmv: string | null;
  crmv_state: string | null;
}
export interface ClinicProfile {
  id: string;
  name: string;
}
export interface Identity {
  user: UserProfile;
  clinic: ClinicProfile;
}

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object';
}
export function parseUser(value: unknown): UserProfile {
  if (
    !object(value) ||
    typeof value.id !== 'string' ||
    typeof value.clinic_id !== 'string' ||
    typeof value.name !== 'string' ||
    typeof value.active !== 'boolean' ||
    typeof value.role !== 'string' ||
    !Object.hasOwn(roleLabels, value.role) ||
    !(value.crmv === null || typeof value.crmv === 'string') ||
    !(value.crmv_state === null || typeof value.crmv_state === 'string')
  ) {
    throw new Error('O sistema retornou dados inválidos.');
  }
  return {
    id: value.id,
    clinic_id: value.clinic_id,
    name: value.name,
    role: value.role as Role,
    active: value.active,
    crmv: value.crmv,
    crmv_state: value.crmv_state,
  };
}
export function parseIdentity(value: unknown): Identity {
  if (
    !object(value) ||
    !object(value.clinic) ||
    typeof value.clinic.id !== 'string' ||
    typeof value.clinic.name !== 'string'
  ) {
    throw new Error('O sistema retornou dados inválidos.');
  }
  const user = parseUser(value.user);
  if (user.clinic_id !== value.clinic.id || !user.active)
    throw new Error('Seu acesso não está ativo.');
  return { user, clinic: { id: value.clinic.id, name: value.clinic.name } };
}

export async function apiRequest(token: string, path: string, changes?: unknown): Promise<unknown> {
  const response = await fetch(`/api${path}`, {
    method: changes === undefined ? 'GET' : 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      ...(changes === undefined ? {} : { 'Content-Type': 'application/json' }),
    },
    ...(changes === undefined ? {} : { body: JSON.stringify(changes) }),
    signal: AbortSignal.timeout(10000),
  });
  const body: unknown = await response.json();
  if (!response.ok) {
    if (object(body) && object(body.error) && typeof body.error.message === 'string')
      throw new Error(body.error.message);
    throw new Error('Não foi possível acessar os dados da clínica.');
  }
  return body;
}
