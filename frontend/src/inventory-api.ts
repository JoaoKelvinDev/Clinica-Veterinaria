export interface ProductSummary {
  id: string;
  name: string;
  unit: string;
  minimum_stock: string;
  track_expiry: boolean;
  version: number;
  deleted_at: string | null;
  physical_stock: string;
  available_stock: string;
  expired_stock: string;
  low_stock: boolean;
  expiring_lots: number;
  expired_lots: number;
}
export interface Lot {
  id: string;
  code: string;
  expires_on: string | null;
  balance: string;
  expired: boolean;
  expiring: boolean;
}
export interface Product extends ProductSummary {
  lots: Lot[];
}
export const movementKinds = {
  inbound: 'Entrada',
  outbound: 'Saída',
  adjustment: 'Ajuste',
} as const;
export interface Movement {
  id: string;
  lot_id: string;
  operation_id: string;
  kind: keyof typeof movementKinds;
  quantity: string;
  reason: string;
  author_name: string;
  product_name: string;
  unit: string;
  created_at: string;
  corrects_id: string | null;
}
function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function invalid(): never {
  throw new Error('O sistema retornou dados inválidos do estoque.');
}
function decimal(value: unknown, signed = false): value is string {
  return (
    typeof value === 'string' && (signed ? /^-?\d+(\.\d{1,3})?$/ : /^\d+(\.\d{1,3})?$/).test(value)
  );
}
function nullableText(value: unknown) {
  return value === null || typeof value === 'string';
}
function count(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}
export function parseProductSummary(value: unknown): ProductSummary {
  if (
    !object(value) ||
    !['id', 'name', 'unit'].every((key) => typeof value[key] === 'string') ||
    !['physical_stock', 'available_stock', 'expired_stock', 'minimum_stock'].every((key) =>
      decimal(value[key]),
    ) ||
    !['track_expiry', 'low_stock'].every((key) => typeof value[key] === 'boolean') ||
    !count(value.version) ||
    value.version < 1 ||
    !nullableText(value.deleted_at) ||
    !count(value.expiring_lots) ||
    !count(value.expired_lots)
  )
    invalid();
  return value as unknown as ProductSummary;
}
export function parseProduct(value: unknown): Product {
  const summary = parseProductSummary(value);
  if (!object(value) || !Array.isArray(value.lots)) invalid();
  const lots = value.lots.map((lot: unknown) => {
    if (
      !object(lot) ||
      typeof lot.id !== 'string' ||
      typeof lot.code !== 'string' ||
      !nullableText(lot.expires_on) ||
      !decimal(lot.balance) ||
      typeof lot.expired !== 'boolean' ||
      typeof lot.expiring !== 'boolean'
    )
      invalid();
    return lot as unknown as Lot;
  });
  return { ...summary, lots };
}
export function parseProducts(value: unknown) {
  if (!object(value) || !Array.isArray(value.items) || !count(value.total)) invalid();
  return { items: value.items.map(parseProductSummary), total: value.total };
}
export function parseMovements(value: unknown): { items: Movement[]; total: number } {
  if (!object(value) || !Array.isArray(value.items) || !count(value.total)) invalid();
  const items = value.items.map((row: unknown) => {
    if (
      !object(row) ||
      ![
        'id',
        'lot_id',
        'operation_id',
        'reason',
        'author_name',
        'product_name',
        'unit',
        'created_at',
      ].every((key) => typeof row[key] === 'string') ||
      typeof row.kind !== 'string' ||
      !Object.hasOwn(movementKinds, row.kind) ||
      !decimal(row.quantity, true) ||
      !nullableText(row.corrects_id)
    )
      invalid();
    return row as unknown as Movement;
  });
  return { items, total: value.total };
}

// Quantidades viajam como texto decimal; a interface não arredonda com ponto flutuante.
export function stockQuantity(
  text: string,
  mode: 'positive' | 'minimum' | 'adjustment' = 'positive',
): string {
  const normalized = text.trim().replace(',', '.');
  if (!/^-?\d+(\.\d{1,3})?$/.test(normalized))
    throw new Error('Informe a quantidade com até três casas decimais.');
  const negative = normalized.startsWith('-');
  const [whole = '0', fraction = ''] = normalized.replace('-', '').split('.');
  const thousandths = BigInt(whole) * 1000n + BigInt(fraction.padEnd(3, '0'));
  if (
    thousandths > 999999999n ||
    (negative && mode !== 'adjustment') ||
    (thousandths === 0n && mode !== 'minimum')
  )
    throw new Error('Quantidade fora do limite permitido.');
  return `${negative && thousandths > 0n ? '-' : ''}${BigInt(whole)}${fraction ? `.${fraction}` : ''}`;
}
export function stockDisplay(value: string): string {
  const [whole = '0', fraction = ''] = value.split('.');
  const decimals = fraction.replace(/0+$/, '');
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.')}${decimals ? `,${decimals}` : ''}`;
}
