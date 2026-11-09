export const quoteStatuses = {
  draft: 'Rascunho',
  sent: 'Enviado',
  approved: 'Aprovado',
  rejected: 'Recusado',
  expired: 'Expirado',
} as const;
export const decisionSources = {
  in_person: 'Presencial',
  phone: 'Telefone',
  other: 'Outro',
} as const;
export interface QuoteSummary {
  id: string;
  patient_id: string;
  tutor_id: string;
  patient_name: string;
  tutor_name: string;
  encounter_id: string | null;
  source_quote_id: string | null;
  status: keyof typeof quoteStatuses;
  version: number;
  valid_until: string | null;
  subtotal_cents: number;
  discount_cents: number;
  total_cents: number;
  created_at: string;
  created_by: string;
  updated_at: string;
  updated_by: string;
  presented_at: string | null;
  presented_by: string | null;
  decision_at: string | null;
  decision_by: string | null;
  decision_source: keyof typeof decisionSources | null;
  decision_note: string | null;
}
export interface QuoteItem {
  id: string;
  position: number;
  kind: 'service' | 'product';
  description: string;
  quantity: string;
  unit_price_cents: number;
  line_total_cents: number;
}
export interface Quote extends QuoteSummary {
  items: QuoteItem[];
}
export interface ItemDraft {
  kind: 'service' | 'product';
  description: string;
  quantity: string;
  price: string;
}
export interface QuoteOptions {
  tutors: { id: string; name: string; is_primary: boolean }[];
  encounters: { id: string; started_at: string; veterinarian_name: string }[];
}
const MAX_CENTS = 1_000_000_000_000;
function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function invalid(): never {
  throw new Error('O sistema retornou dados inválidos do orçamento.');
}
function moneyInteger(value: unknown): value is number {
  return (
    typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 && value <= MAX_CENTS
  );
}
export function parseQuoteSummary(value: unknown): QuoteSummary {
  if (!object(value)) invalid();
  if (
    ![
      'id',
      'patient_id',
      'tutor_id',
      'patient_name',
      'tutor_name',
      'created_at',
      'created_by',
      'updated_at',
      'updated_by',
    ].every((key) => typeof value[key] === 'string')
  )
    invalid();
  if (
    ![
      'encounter_id',
      'source_quote_id',
      'valid_until',
      'presented_at',
      'presented_by',
      'decision_at',
      'decision_by',
      'decision_note',
    ].every((key) => value[key] === null || typeof value[key] === 'string')
  )
    invalid();
  if (
    !Object.hasOwn(quoteStatuses, String(value.status)) ||
    !Number.isSafeInteger(value.version) ||
    Number(value.version) < 1
  )
    invalid();
  if (
    value.decision_source !== null &&
    !Object.hasOwn(decisionSources, String(value.decision_source))
  )
    invalid();
  if (
    !moneyInteger(value.subtotal_cents) ||
    !moneyInteger(value.discount_cents) ||
    !moneyInteger(value.total_cents) ||
    value.subtotal_cents - value.discount_cents !== value.total_cents
  )
    invalid();
  return value as unknown as QuoteSummary;
}
export function parseQuote(value: unknown): Quote {
  const quote = parseQuoteSummary(value);
  if (!object(value) || !Array.isArray(value.items) || value.items.length === 0) invalid();
  const items = value.items.map((item: unknown): QuoteItem => {
    if (
      !object(item) ||
      typeof item.id !== 'string' ||
      !Number.isSafeInteger(item.position) ||
      typeof item.description !== 'string' ||
      (item.kind !== 'service' && item.kind !== 'product') ||
      typeof item.quantity !== 'string' ||
      !moneyInteger(item.unit_price_cents) ||
      !moneyInteger(item.line_total_cents)
    )
      invalid();
    return item as unknown as QuoteItem;
  });
  return { ...quote, items };
}
export function parseQuotePage(value: unknown): { items: QuoteSummary[]; total: number } {
  if (!object(value) || !Array.isArray(value.items) || typeof value.total !== 'number') invalid();
  return { items: value.items.map(parseQuoteSummary), total: value.total };
}
export function parseQuoteOptions(value: unknown): QuoteOptions {
  if (!object(value) || !Array.isArray(value.tutors) || !Array.isArray(value.encounters)) invalid();
  if (
    !value.tutors.every(
      (item) =>
        object(item) &&
        typeof item.id === 'string' &&
        typeof item.name === 'string' &&
        typeof item.is_primary === 'boolean',
    )
  )
    invalid();
  if (
    !value.encounters.every(
      (item) =>
        object(item) &&
        typeof item.id === 'string' &&
        typeof item.started_at === 'string' &&
        typeof item.veterinarian_name === 'string',
    )
  )
    invalid();
  return value as unknown as QuoteOptions;
}
export function money(cents: number): string {
  const digits = String(cents).padStart(3, '0');
  return `R$ ${digits.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, '.')},${digits.slice(-2)}`;
}
export function moneyInput(cents: number): string {
  const digits = String(cents).padStart(3, '0');
  return `${digits.slice(0, -2)},${digits.slice(-2)}`;
}
export function toCents(value: string): number {
  if (!/^\d{1,11}([.,]\d{1,2})?$/.test(value.trim()))
    throw new Error('Informe valores com até duas casas decimais e sem separador de milhar.');
  const [whole, fraction = ''] = value.trim().replace(',', '.').split('.');
  const cents = BigInt(whole ?? '0') * 100n + BigInt(fraction.padEnd(2, '0'));
  if (cents > BigInt(MAX_CENTS)) throw new Error('O valor ultrapassa o limite permitido.');
  return Number(cents);
}
export function quantity(value: string): { text: string; thousandths: bigint } {
  const text = value.trim().replace(',', '.');
  if (!/^\d{1,6}(\.\d{1,3})?$/.test(text))
    throw new Error('Informe quantidade positiva com até três casas decimais.');
  const [whole, fraction = ''] = text.split('.');
  const thousandths = BigInt(whole ?? '0') * 1000n + BigInt(fraction.padEnd(3, '0'));
  if (thousandths <= 0n) throw new Error('A quantidade deve ser maior que zero.');
  return { text, thousandths };
}
export function preview(
  items: ItemDraft[],
  discount: string,
): { subtotal: number; total: number; discount: number } {
  let subtotal = 0n;
  for (const item of items) {
    const line = (quantity(item.quantity).thousandths * BigInt(toCents(item.price)) + 500n) / 1000n;
    if (line > BigInt(MAX_CENTS))
      throw new Error('O valor de um item ultrapassa o limite permitido.');
    subtotal += line;
  }
  if (subtotal > BigInt(MAX_CENTS)) throw new Error('O subtotal ultrapassa o limite permitido.');
  const discountCents = toCents(discount);
  if (BigInt(discountCents) > subtotal) throw new Error('O desconto não pode superar o subtotal.');
  return {
    subtotal: Number(subtotal),
    total: Number(subtotal - BigInt(discountCents)),
    discount: discountCents,
  };
}
