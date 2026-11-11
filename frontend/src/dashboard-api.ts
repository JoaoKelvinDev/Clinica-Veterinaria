import type { Role } from './api';

export type DashboardDestination = 'scheduling' | 'messaging' | 'inventory' | 'financial';
export interface DashboardData {
  generated_at: string;
  day: string;
  month_start: string;
  month_end: string;
  timezone: 'America/Fortaleza';
  scheduling: {
    appointments_total: number;
    scheduled: number;
    confirmed: number;
    in_progress: number;
    completed: number;
    cancelled: number;
    no_show: number;
    open_encounters: number;
  };
  messaging: { needs_attention: number; simulated: boolean };
  inventory: { low_stock_products: number; expired_lots: number; expiring_lots: number };
  financial: {
    income_cents: string;
    expense_cents: string | null;
    difference_cents: string | null;
  } | null;
}
function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function invalid(): never {
  throw new Error('O sistema retornou dados inválidos da visão geral.');
}
function date(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T12:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}
function counts(value: unknown, keys: string[]): value is Record<string, number> {
  return (
    object(value) &&
    keys.every(
      (key) =>
        typeof value[key] === 'number' &&
        Number.isSafeInteger(value[key]) &&
        Number(value[key]) >= 0,
    )
  );
}
function cents(value: unknown): value is string {
  return typeof value === 'string' && /^(0|-?[1-9]\d*)$/.test(value);
}
export function parseDashboard(value: unknown, role: Role): DashboardData {
  if (
    !object(value) ||
    typeof value.generated_at !== 'string' ||
    !Number.isFinite(Date.parse(value.generated_at)) ||
    !date(value.day) ||
    !date(value.month_start) ||
    !date(value.month_end) ||
    value.timezone !== 'America/Fortaleza' ||
    value.month_start !== `${value.day.slice(0, 7)}-01` ||
    value.month_end < value.day ||
    value.month_end.slice(0, 7) !== value.day.slice(0, 7)
  )
    invalid();
  const statuses = ['scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show'];
  if (
    !counts(value.scheduling, [...statuses, 'appointments_total', 'open_encounters']) ||
    statuses.reduce(
      (total, key) => total + (value.scheduling as Record<string, number>)[key]!,
      0,
    ) !== value.scheduling.appointments_total ||
    !counts(value.inventory, ['low_stock_products', 'expired_lots', 'expiring_lots']) ||
    !counts(value.messaging, ['needs_attention']) ||
    typeof value.messaging.simulated !== 'boolean'
  )
    invalid();
  const financial = value.financial;
  if (role === 'admin' || role === 'reception') {
    if (!object(financial) || !cents(financial.income_cents) || BigInt(financial.income_cents) < 0n)
      invalid();
    if (role === 'reception') {
      if (financial.expense_cents !== null || financial.difference_cents !== null) invalid();
    } else if (
      !cents(financial.expense_cents) ||
      BigInt(financial.expense_cents) < 0n ||
      !cents(financial.difference_cents) ||
      BigInt(financial.income_cents) - BigInt(financial.expense_cents) !==
        BigInt(financial.difference_cents)
    )
      invalid();
  } else if (financial !== null) invalid();
  return value as unknown as DashboardData;
}

export function dashboardDate(value: string): string {
  return value.split('-').reverse().join('/');
}
