import { entryFields } from './records-api';
import type { EntryField } from './records-api';

export type DraftContent = Record<EntryField, string | null> & { uncertainties: string[] };
export interface AiDraft {
  id: string;
  patient_id: string;
  encounter_id: string;
  source: 'text' | 'mock_audio';
  transcript: string;
  content: DraftContent;
  requested_by: string;
  llm_provider: string;
  llm_model: string;
  stt_provider: string | null;
  stt_model: string | null;
  prompt_version: string;
  status: 'pending' | 'approved' | 'discarded';
  resolved_by: string | null;
  resolved_at: string | null;
  record_entry_id: string | null;
  created_at: string;
  simulated: boolean;
}

export const draftStatuses = {
  pending: 'Pendente',
  approved: 'Aprovado',
  discarded: 'Descartado',
} as const;
export const soapGroups: { title: string; fields: EntryField[] }[] = [
  { title: 'S — Subjetivo', fields: ['complaint'] },
  { title: 'O — Objetivo', fields: ['general_state', 'findings'] },
  {
    title: 'A — Avaliação informada pelo veterinário',
    fields: ['presumptive_diagnosis', 'conclusive_diagnosis'],
  },
  {
    title: 'P — Plano informado pelo veterinário',
    fields: ['procedures', 'prescription', 'follow_up'],
  },
];

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function invalid(): never {
  throw new Error('O sistema retornou dados inválidos do rascunho.');
}

export function parseDraft(value: unknown): AiDraft {
  if (!object(value) || !object(value.content)) invalid();
  const required = [
    'id',
    'patient_id',
    'encounter_id',
    'transcript',
    'requested_by',
    'llm_provider',
    'llm_model',
    'prompt_version',
    'created_at',
  ];
  const nullable = ['stt_provider', 'stt_model', 'resolved_by', 'resolved_at', 'record_entry_id'];
  if (!required.every((key) => typeof value[key] === 'string')) invalid();
  if (!nullable.every((key) => value[key] === null || typeof value[key] === 'string')) invalid();
  if (typeof value.simulated !== 'boolean' || !Object.hasOwn(draftStatuses, String(value.status)))
    invalid();
  if (value.source !== 'text' && value.source !== 'mock_audio') invalid();
  const content = value.content;
  if (!entryFields.every(([key]) => content[key] === null || typeof content[key] === 'string'))
    invalid();
  if (
    !Array.isArray(content.uncertainties) ||
    !content.uncertainties.every((item) => typeof item === 'string')
  )
    invalid();
  return value as unknown as AiDraft;
}
export function parseDrafts(value: unknown): AiDraft[] {
  if (!Array.isArray(value)) invalid();
  return value.map(parseDraft);
}
