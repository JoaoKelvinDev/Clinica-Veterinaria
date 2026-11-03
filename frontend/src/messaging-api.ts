export interface MessageItem {
  id: string;
  direction: 'outbound' | 'inbound';
  status: string;
  phone: string;
  body: string;
  tutor_id: string | null;
  tutor_name: string | null;
  patient_id: string | null;
  appointment_id: string | null;
  intent: 'confirm' | 'cancel' | 'opt_out' | 'unknown' | null;
  needs_attention: boolean;
  handled_at: string | null;
  created_at: string;
}
export interface ReminderItem {
  id: string;
  kind: keyof typeof reminderKinds;
  status: keyof typeof reminderStatuses;
  due_at: string;
  event_at: string;
  patient_id: string;
  patient_name: string;
  outcome: string | null;
  sent_at: string | null;
}
export interface MessagingOverview {
  provider: string;
  simulated: boolean;
  attention: MessageItem[];
  upcoming: ReminderItem[];
  recent_reminders: ReminderItem[];
  messages: MessageItem[];
}

export const reminderKinds = {
  appointment_confirmation: 'Pedido de confirmação',
  appointment_reminder: 'Lembrete de consulta',
  vaccine: 'Reforço de vacina',
  follow_up: 'Retorno',
} as const;
export const reminderStatuses = {
  pending: 'Agendado',
  sent: 'Enviado',
  skipped: 'Não enviado',
  cancelled: 'Cancelado',
  failed: 'Falhou',
} as const;
export const intents = {
  confirm: 'Confirmou',
  cancel: 'Cancelou',
  opt_out: 'Pediu para sair',
  unknown: 'Não reconhecida',
} as const;

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object';
}
function invalid(): never {
  throw new Error('O sistema retornou dados inválidos das mensagens.');
}
function strings(value: Record<string, unknown>, keys: string[], nullable: string[]) {
  if (!keys.every((key) => typeof value[key] === 'string')) invalid();
  if (!nullable.every((key) => value[key] === null || typeof value[key] === 'string')) invalid();
}
export function parseMessage(value: unknown): MessageItem {
  if (!object(value) || typeof value.needs_attention !== 'boolean') invalid();
  if (value.direction !== 'outbound' && value.direction !== 'inbound') invalid();
  if (value.intent !== null && !Object.hasOwn(intents, String(value.intent))) invalid();
  strings(
    value,
    ['id', 'status', 'phone', 'body', 'created_at'],
    ['tutor_id', 'tutor_name', 'patient_id', 'appointment_id', 'handled_at'],
  );
  return value as unknown as MessageItem;
}
function parseReminder(value: unknown): ReminderItem {
  if (
    !object(value) ||
    !Object.hasOwn(reminderKinds, String(value.kind)) ||
    !Object.hasOwn(reminderStatuses, String(value.status))
  )
    invalid();
  strings(
    value,
    ['id', 'due_at', 'event_at', 'patient_id', 'patient_name'],
    ['outcome', 'sent_at'],
  );
  return value as unknown as ReminderItem;
}
function list<T>(value: unknown, parse: (item: unknown) => T): T[] {
  if (!Array.isArray(value)) invalid();
  return value.map(parse);
}
export function parseOverview(value: unknown): MessagingOverview {
  if (!object(value) || typeof value.provider !== 'string' || typeof value.simulated !== 'boolean')
    invalid();
  return {
    provider: value.provider,
    simulated: value.simulated,
    attention: list(value.attention, parseMessage),
    upcoming: list(value.upcoming, parseReminder),
    recent_reminders: list(value.recent_reminders, parseReminder),
    messages: list(value.messages, parseMessage),
  };
}
export function parseDispatch(value: unknown): { sent: number; skipped: number; failed: number } {
  if (
    !object(value) ||
    typeof value.sent !== 'number' ||
    typeof value.skipped !== 'number' ||
    typeof value.failed !== 'number'
  )
    invalid();
  return { sent: value.sent, skipped: value.skipped, failed: value.failed };
}
