export const clinicTimezone = 'America/Fortaleza';
export const statusLabels = {
  scheduled: 'Agendado',
  confirmed: 'Confirmado',
  in_progress: 'Em atendimento',
  completed: 'Concluído',
  cancelled: 'Cancelado',
  no_show: 'Faltou',
} as const;
export type AppointmentStatus = keyof typeof statusLabels;
export interface Appointment {
  id: string;
  clinic_id: string;
  patient_id: string;
  patient_name: string;
  veterinarian_id: string;
  veterinarian_name: string;
  starts_at: string;
  ends_at: string;
  kind: string;
  status: AppointmentStatus;
  encounter_id: string | null;
}
export interface Encounter {
  id: string;
  clinic_id: string;
  patient_id: string;
  patient_name: string;
  veterinarian_id: string;
  veterinarian_name: string;
  appointment_id: string | null;
  started_at: string;
  completed_at: string | null;
}
function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object';
}
function date(value: unknown): value is string {
  return typeof value === 'string' && Number.isFinite(Date.parse(value));
}
function nullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string';
}
function invalid(): never {
  throw new Error('O sistema retornou dados inválidos da agenda.');
}
function hasIdentity(value: Record<string, unknown>) {
  return [
    'id',
    'clinic_id',
    'patient_id',
    'patient_name',
    'veterinarian_id',
    'veterinarian_name',
  ].every((key) => typeof value[key] === 'string');
}
export function parseAppointment(value: unknown): Appointment {
  if (
    !record(value) ||
    !hasIdentity(value) ||
    !date(value.starts_at) ||
    !date(value.ends_at) ||
    typeof value.kind !== 'string' ||
    typeof value.status !== 'string' ||
    !Object.hasOwn(statusLabels, value.status) ||
    !nullableString(value.encounter_id)
  )
    return invalid();
  return value as unknown as Appointment;
}
export function parseEncounter(value: unknown): Encounter {
  if (
    !record(value) ||
    !hasIdentity(value) ||
    !date(value.started_at) ||
    !(value.completed_at === null || date(value.completed_at)) ||
    !nullableString(value.appointment_id)
  )
    return invalid();
  return value as unknown as Encounter;
}
export function localDateTime(value: string | Date): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: clinicTimezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(value));
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? '';
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}`;
}
export function utcDateTime(value: string): string {
  const target = Date.parse(`${value}:00Z`);
  if (!Number.isFinite(target)) throw new Error('Informe uma data e um horário válidos.');
  let result = target;
  for (let attempt = 0; attempt < 2; attempt++)
    result += target - Date.parse(`${localDateTime(new Date(result))}:00Z`);
  return new Date(result).toISOString();
}
export function displayDateTime(value: string): string {
  return new Intl.DateTimeFormat('pt-BR', {
    timeZone: clinicTimezone,
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(value));
}
