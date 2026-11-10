import { parseLinks } from './registry-api';

export interface RecordExport {
  id: string;
  patient_id: string;
  author_name: string;
  author_crmv: string;
  tutor_name: string;
  created_at: string;
  sha256: string;
  size_bytes: number;
  attachment_count: number;
  missing_file_count: number;
}
function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function invalid(): never {
  throw new Error('O sistema retornou dados inválidos da exportação.');
}
function integer(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}
export function parseExport(value: unknown): RecordExport {
  if (
    !object(value) ||
    !['id', 'patient_id', 'author_name', 'author_crmv', 'tutor_name', 'created_at'].every(
      (key) => typeof value[key] === 'string',
    ) ||
    typeof value.sha256 !== 'string' ||
    !/^[a-f0-9]{64}$/.test(value.sha256) ||
    !['size_bytes', 'attachment_count', 'missing_file_count'].every((key) => integer(value[key]))
  )
    invalid();
  return value as unknown as RecordExport;
}
export function parseExportPage(value: unknown) {
  if (!object(value) || !Array.isArray(value.items) || !integer(value.total)) invalid();
  return { items: value.items.map(parseExport), total: value.total };
}
export function parseExportOptions(value: unknown) {
  if (
    !object(value) ||
    typeof value.clinic_name !== 'string' ||
    typeof value.patient_name !== 'string'
  )
    invalid();
  return {
    clinic_name: value.clinic_name,
    patient_name: value.patient_name,
    tutors: parseLinks(value.tutors),
  };
}
async function failure(response: Response): Promise<never> {
  let message =
    'Não foi possível concluir a solicitação. Consulte as exportações antes de tentar novamente.';
  try {
    const body: unknown = await response.json();
    if (object(body) && object(body.error) && typeof body.error.message === 'string')
      message = body.error.message;
  } catch {
    /* Uma resposta inválida não vira conteúdo de um arquivo. */
  }
  throw new Error(message);
}
export async function createRecordExport(
  token: string,
  patientId: string,
  values: unknown,
): Promise<RecordExport> {
  const response = await fetch(`/api/patients/${patientId}/record-exports`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(values),
    signal: AbortSignal.timeout(120000),
  });
  if (!response.ok) return failure(response);
  return parseExport(await response.json());
}
export async function downloadRecordExport(
  token: string,
  id: string,
  kind: 'file' | 'package',
): Promise<Blob> {
  const response = await fetch(`/api/record-exports/${id}/${kind}`, {
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(120000),
  });
  if (!response.ok) return failure(response);
  const expected = kind === 'file' ? 'application/pdf' : 'application/zip';
  if (response.headers.get('Content-Type')?.split(';')[0] !== expected)
    throw new Error('Tipo de arquivo inesperado.');
  return new Blob([await response.arrayBuffer()], { type: expected });
}
