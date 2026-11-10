export const paymentMethods = {
  cash: 'Dinheiro',
  pix: 'Pix',
  debit_card: 'Cartão de débito',
  credit_card: 'Cartão de crédito',
  bank_transfer: 'Transferência bancária',
  other: 'Outro',
} as const;
export const financialKinds = { income: 'Recebimento', expense: 'Despesa' } as const;
export interface FinancialEntry {
  id: string;
  kind: keyof typeof financialKinds;
  description: string;
  category: string;
  amount_cents: number;
  occurred_on: string;
  payment_method: keyof typeof paymentMethods;
  author_id: string;
  author_name: string;
  created_at: string;
  tutor_id: string | null;
  tutor_name: string | null;
  patient_id: string | null;
  patient_name: string | null;
  status: 'posted' | 'reversed';
  reversal: {
    id: string;
    author_id: string;
    author_name: string;
    created_at: string;
    reversal_reason: string;
  } | null;
}
export interface FinancialPage {
  items: FinancialEntry[];
  total: number;
  summary: { income_cents: string; expense_cents: string | null; difference_cents: string | null };
}
const MAX_CENTS = 1_000_000_000_000n;
function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function invalid(): never {
  throw new Error('O sistema retornou dados financeiros inválidos.');
}
function integerText(value: unknown): value is string {
  return typeof value === 'string' && /^(0|-?[1-9]\d*)$/.test(value);
}
export function financialCents(input: string): number {
  const value = input.trim();
  if (!/^\d{1,11}(,\d{1,2})?$/.test(value))
    throw new Error('Informe o valor em reais, por exemplo 123,45, sem pontos.');
  const [whole = '', fraction = ''] = value.split(',');
  const cents = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  if (cents <= 0n || cents > MAX_CENTS)
    throw new Error('O valor deve ser positivo e de até R$ 10.000.000.000,00.');
  return Number(cents);
}
export function financialMoney(value: string | number): string {
  const cents = BigInt(value);
  const absolute = cents < 0n ? -cents : cents;
  const whole = (absolute / 100n).toLocaleString('pt-BR');
  return `${cents < 0n ? '-' : ''}R$ ${whole},${String(absolute % 100n).padStart(2, '0')}`;
}
export function financialToday(): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Fortaleza',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? '';
  return `${part('year')}-${part('month')}-${part('day')}`;
}
export function parseFinancialEntry(value: unknown): FinancialEntry {
  if (
    !object(value) ||
    ![
      'id',
      'description',
      'category',
      'occurred_on',
      'author_id',
      'author_name',
      'created_at',
    ].every((key) => typeof value[key] === 'string')
  )
    invalid();
  if (
    !['tutor_id', 'tutor_name', 'patient_id', 'patient_name'].every(
      (key) => value[key] === null || typeof value[key] === 'string',
    )
  )
    invalid();
  if (
    !Object.hasOwn(financialKinds, String(value.kind)) ||
    !Object.hasOwn(paymentMethods, String(value.payment_method)) ||
    typeof value.amount_cents !== 'number' ||
    !Number.isSafeInteger(value.amount_cents) ||
    value.amount_cents <= 0 ||
    BigInt(value.amount_cents) > MAX_CENTS ||
    !/^\d{4}-\d{2}-\d{2}$/.test(String(value.occurred_on))
  )
    invalid();
  if (value.status !== 'posted' && value.status !== 'reversed') invalid();
  if ((value.status === 'posted') !== (value.reversal === null)) invalid();
  if (
    value.reversal !== null &&
    (!object(value.reversal) ||
      !['id', 'author_id', 'author_name', 'created_at', 'reversal_reason'].every(
        (key) => typeof (value.reversal as Record<string, unknown>)[key] === 'string',
      ))
  )
    invalid();
  return value as unknown as FinancialEntry;
}
export function parseFinancialPage(value: unknown): FinancialPage {
  if (
    !object(value) ||
    !Array.isArray(value.items) ||
    !Number.isSafeInteger(value.total) ||
    Number(value.total) < 0 ||
    !object(value.summary)
  )
    invalid();
  const summary = value.summary;
  if (
    !integerText(summary.income_cents) ||
    BigInt(summary.income_cents) < 0n ||
    !(
      summary.expense_cents === null ||
      (integerText(summary.expense_cents) && BigInt(summary.expense_cents) >= 0n)
    ) ||
    !(summary.difference_cents === null || integerText(summary.difference_cents))
  )
    invalid();
  if ((summary.expense_cents === null) !== (summary.difference_cents === null)) invalid();
  if (
    summary.expense_cents !== null &&
    BigInt(summary.income_cents) - BigInt(summary.expense_cents) !==
      BigInt(summary.difference_cents as string)
  )
    invalid();
  return {
    items: value.items.map(parseFinancialEntry),
    total: Number(value.total),
    summary: summary as unknown as FinancialPage['summary'],
  };
}
