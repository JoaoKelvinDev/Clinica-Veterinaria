export interface RecordEntry {
  id: string;
  patient_id: string;
  encounter_id: string;
  root_id: string;
  version: number;
  supersedes_id: string | null;
  correction_reason: string | null;
  author_id: string;
  author_name: string;
  author_crmv: string;
  created_at: string;
  location: string;
  complaint: string;
  general_state: string;
  findings: string | null;
  presumptive_diagnosis: string;
  conclusive_diagnosis: string | null;
  procedures: string | null;
  prescription: string | null;
  follow_up: string | null;
  follow_up_on: string | null;
}
export interface WeightRecord {
  id: string;
  weight_grams: number;
  supersedes_id: string | null;
  correction_reason: string | null;
  author_id: string;
  author_name: string;
  created_at: string;
}
export interface VaccineRecord {
  id: string;
  encounter_id: string;
  vaccine_name: string;
  batch: string;
  manufacturer: string;
  dose: string;
  manufactured_on: string;
  expires_on: string;
  next_dose_on: string | null;
  supersedes_id: string | null;
  correction_reason: string | null;
  author_id: string;
  author_name: string;
  author_crmv: string;
  created_at: string;
}
export interface TimelineEncounter {
  id: string;
  started_at: string;
  completed_at: string | null;
  veterinarian_name: string;
  appointment_id: string | null;
}
export interface PatientRecord {
  patient_id: string;
  clinical_access: boolean;
  encounters: TimelineEncounter[];
  entries: RecordEntry[];
  weights: WeightRecord[];
  vaccines: VaccineRecord[];
  documents: PatientDocument[];
}

/** Campos de texto do registro, na ordem do art. 9º da Resolução CFMV 1321/2020. */
export const entryFields = [
  ['complaint', 'Relato do responsável', true],
  ['general_state', 'Estado geral e parâmetros', true],
  ['findings', 'Achados do histórico e dos exames', false],
  ['presumptive_diagnosis', 'Diagnóstico presuntivo', true],
  ['conclusive_diagnosis', 'Diagnóstico conclusivo', false],
  ['procedures', 'Procedimentos realizados', false],
  ['prescription', 'Prescrição', false],
  ['follow_up', 'Retorno sugerido', false],
] as const;
export type EntryField = (typeof entryFields)[number][0];

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object';
}
function invalid(): never {
  throw new Error('O sistema retornou dados inválidos do prontuário.');
}
function strings(value: Record<string, unknown>, keys: string[], nullable: string[] = []) {
  if (!keys.every((key) => typeof value[key] === 'string')) invalid();
  if (!nullable.every((key) => value[key] === null || typeof value[key] === 'string')) invalid();
}
function list<T>(value: unknown, parse: (item: unknown) => T): T[] {
  if (!Array.isArray(value)) invalid();
  return value.map(parse);
}
const correction = ['supersedes_id', 'correction_reason'];

export function parseEntry(value: unknown): RecordEntry {
  if (!object(value) || typeof value.version !== 'number') invalid();
  strings(
    value,
    [
      'id',
      'patient_id',
      'encounter_id',
      'root_id',
      'author_id',
      'author_name',
      'author_crmv',
      'created_at',
      'location',
      'complaint',
      'general_state',
      'presumptive_diagnosis',
    ],
    [
      ...correction,
      'findings',
      'conclusive_diagnosis',
      'procedures',
      'prescription',
      'follow_up',
      'follow_up_on',
    ],
  );
  return value as unknown as RecordEntry;
}
export function parseWeight(value: unknown): WeightRecord {
  if (!object(value) || typeof value.weight_grams !== 'number') invalid();
  strings(value, ['id', 'author_id', 'author_name', 'created_at'], correction);
  return value as unknown as WeightRecord;
}
export function parseVaccine(value: unknown): VaccineRecord {
  if (!object(value)) invalid();
  strings(
    value,
    [
      'id',
      'encounter_id',
      'vaccine_name',
      'batch',
      'manufacturer',
      'dose',
      'manufactured_on',
      'expires_on',
      'author_id',
      'author_name',
      'author_crmv',
      'created_at',
    ],
    [...correction, 'next_dose_on'],
  );
  return value as unknown as VaccineRecord;
}
function parseEncounter(value: unknown): TimelineEncounter {
  if (!object(value)) invalid();
  strings(value, ['id', 'started_at', 'veterinarian_name'], ['completed_at', 'appointment_id']);
  return value as unknown as TimelineEncounter;
}
export function parseRecord(value: unknown): PatientRecord {
  if (
    !object(value) ||
    typeof value.patient_id !== 'string' ||
    typeof value.clinical_access !== 'boolean'
  )
    invalid();
  return {
    patient_id: value.patient_id,
    clinical_access: value.clinical_access,
    encounters: list(value.encounters, parseEncounter),
    entries: list(value.entries, parseEntry),
    weights: list(value.weights, parseWeight),
    vaccines: list(value.vaccines, parseVaccine),
    documents: list(value.documents, parseDocument),
  };
}
export function parseEntries(value: unknown): RecordEntry[] {
  return list(value, parseEntry);
}

export function displayWeight(grams: number): string {
  return `${(grams / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 3 })} kg`;
}
export function displayDate(value: string): string {
  const [year, month, day] = value.split('-');
  return `${day}/${month}/${year}`;
}

export const documentKinds = {
  lab_report: 'Laudo de exame',
  external_history: 'Histórico de outro veterinário ou clínica',
  prescription: 'Receita',
  other: 'Outro documento',
} as const;
export type DocumentKind = keyof typeof documentKinds;
export const documentTypes = ['application/pdf', 'image/jpeg', 'image/png'];
export const maxDocumentBytes = 10 * 1024 * 1024;

export interface PatientDocument {
  id: string;
  patient_id: string;
  encounter_id: string | null;
  root_id: string;
  version: number;
  supersedes_id: string | null;
  correction_reason: string | null;
  kind: DocumentKind;
  origin_name: string;
  origin_crmv: string | null;
  document_date: string;
  summary: string | null;
  file_name: string | null;
  content_type: string | null;
  size_bytes: number | null;
  sha256: string | null;
  author_id: string;
  author_name: string;
  author_crmv: string | null;
  created_at: string;
}
export function parseDocument(value: unknown): PatientDocument {
  if (
    !object(value) ||
    typeof value.version !== 'number' ||
    !(value.size_bytes === null || typeof value.size_bytes === 'number') ||
    !Object.hasOwn(documentKinds, String(value.kind))
  )
    invalid();
  strings(
    value,
    [
      'id',
      'patient_id',
      'root_id',
      'origin_name',
      'document_date',
      'author_id',
      'author_name',
      'created_at',
    ],
    [
      ...correction,
      'encounter_id',
      'origin_crmv',
      'summary',
      'file_name',
      'content_type',
      'sha256',
      'author_crmv',
    ],
  );
  return value as unknown as PatientDocument;
}
export function parseDocuments(value: unknown): PatientDocument[] {
  return list(value, parseDocument);
}
export function displaySize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB`;
}

async function failure(response: Response): Promise<never> {
  const body: unknown = await response.json().catch(() => null);
  if (object(body) && object(body.error) && typeof body.error.message === 'string')
    throw new Error(body.error.message);
  throw new Error('Não foi possível concluir a operação.');
}

/** Envio multipart: o arquivo vai junto com os campos, numa única requisição. */
export async function uploadDocument(
  token: string,
  patientId: string,
  form: FormData,
): Promise<PatientDocument> {
  const response = await fetch(`/api/patients/${patientId}/documents`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
    signal: AbortSignal.timeout(60000),
  });
  if (!response.ok) return failure(response);
  return parseDocument(await response.json());
}

export async function fetchDocumentFile(token: string, documentId: string): Promise<Blob> {
  const response = await fetch(`/api/documents/${documentId}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(60000),
  });
  if (!response.ok) return failure(response);
  const type = response.headers.get('Content-Type') ?? '';
  // Só tipos conferidos pelo backend viram conteúdo exibível no navegador.
  if (!documentTypes.includes(type)) throw new Error('Tipo de arquivo inesperado.');
  return new Blob([await response.arrayBuffer()], { type });
}
