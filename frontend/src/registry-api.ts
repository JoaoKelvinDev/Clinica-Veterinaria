export interface Tutor {
  id: string;
  clinic_id: string;
  name: string;
  phone: string | null;
  document: string | null;
  address: string | null;
  whatsapp_opt_in: boolean;
  whatsapp_opt_in_at: string | null;
  whatsapp_opt_in_source: string | null;
  whatsapp_opt_out_at: string | null;
  deleted_at: string | null;
}
export interface Patient {
  id: string;
  clinic_id: string;
  name: string;
  species: string;
  breed: string | null;
  sex: 'male' | 'female' | 'unknown';
  neutered: boolean | null;
  birth_date: string | null;
  estimated_age_months: number | null;
  coat: string | null;
  microchip: string | null;
  notes: string | null;
}
export interface TutorLink {
  id: string;
  is_primary: boolean;
  tutor: Tutor;
}
export interface Page<T> {
  items: T[];
  total: number;
}
function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object';
}
function text(value: unknown): value is string | null {
  return value === null || typeof value === 'string';
}
function invalid(): never {
  throw new Error('O sistema retornou dados inválidos do cadastro.');
}
export function parseTutor(value: unknown): Tutor {
  if (
    !object(value) ||
    typeof value.id !== 'string' ||
    typeof value.clinic_id !== 'string' ||
    typeof value.name !== 'string' ||
    !text(value.phone) ||
    !text(value.document) ||
    !text(value.address) ||
    typeof value.whatsapp_opt_in !== 'boolean' ||
    !text(value.whatsapp_opt_in_at) ||
    !text(value.whatsapp_opt_in_source) ||
    !text(value.whatsapp_opt_out_at) ||
    !text(value.deleted_at)
  )
    return invalid();
  return {
    id: value.id,
    clinic_id: value.clinic_id,
    name: value.name,
    phone: value.phone,
    document: value.document,
    address: value.address,
    whatsapp_opt_in: value.whatsapp_opt_in,
    whatsapp_opt_in_at: value.whatsapp_opt_in_at,
    whatsapp_opt_in_source: value.whatsapp_opt_in_source,
    whatsapp_opt_out_at: value.whatsapp_opt_out_at,
    deleted_at: value.deleted_at,
  };
}
export function parsePatient(value: unknown): Patient {
  if (
    !object(value) ||
    typeof value.id !== 'string' ||
    typeof value.clinic_id !== 'string' ||
    typeof value.name !== 'string' ||
    typeof value.species !== 'string' ||
    !text(value.breed) ||
    !text(value.coat) ||
    !text(value.microchip) ||
    !text(value.notes) ||
    !text(value.birth_date) ||
    !(value.neutered === null || typeof value.neutered === 'boolean') ||
    !(
      value.estimated_age_months === null ||
      (typeof value.estimated_age_months === 'number' &&
        Number.isInteger(value.estimated_age_months) &&
        value.estimated_age_months >= 0)
    ) ||
    !(value.sex === 'male' || value.sex === 'female' || value.sex === 'unknown')
  )
    return invalid();
  return {
    id: value.id,
    clinic_id: value.clinic_id,
    name: value.name,
    species: value.species,
    breed: value.breed,
    sex: value.sex,
    neutered: value.neutered,
    birth_date: value.birth_date,
    estimated_age_months: value.estimated_age_months,
    coat: value.coat,
    microchip: value.microchip,
    notes: value.notes,
  };
}
export function parsePage<T>(value: unknown, parse: (item: unknown) => T): Page<T> {
  if (
    !object(value) ||
    !Array.isArray(value.items) ||
    typeof value.total !== 'number' ||
    !Number.isInteger(value.total) ||
    value.total < 0
  )
    return invalid();
  return { items: value.items.map(parse), total: value.total };
}
export function parseLinks(value: unknown): TutorLink[] {
  if (!Array.isArray(value)) return invalid();
  return value.map((item: unknown) => {
    if (!object(item) || typeof item.id !== 'string' || typeof item.is_primary !== 'boolean')
      return invalid();
    return { id: item.id, is_primary: item.is_primary, tutor: parseTutor(item.tutor) };
  });
}
export function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : 'Não foi possível concluir a operação.';
}
