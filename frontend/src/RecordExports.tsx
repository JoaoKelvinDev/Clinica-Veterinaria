import type { ComponentProps } from 'react';
import { ActionScreen, ScreenArea, ScreenFeedback } from './Screen';
import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest } from './api';
import type { UserProfile } from './api';
import { errorMessage } from './registry-api';
import { displayDateTime } from './scheduling-api';
import {
  createRecordExport,
  downloadRecordExport,
  parseExportOptions,
  parseExportPage,
} from './record-exports-api';
import type { RecordExport } from './record-exports-api';

function RecordExportsContent({
  token,
  user,
  patientId,
}: {
  token: string;
  user: UserProfile;
  patientId: string;
}) {
  const [opened, setOpened] = useState(false);
  if (user.role === 'reception') return null;
  return (
    <section aria-labelledby="exports-title">
      <h3 id="exports-title">Cópias em PDF</h3>
      <button className="secondary" onClick={() => setOpened(!opened)}>
        {opened ? 'Fechar exportações' : 'Ver exportações em PDF'}
      </button>
      {opened && (
        <ActionScreen title="Exportações em PDF" onBack={() => setOpened(false)}>
          <ExportPanel token={token} user={user} patientId={patientId} />
        </ActionScreen>
      )}
    </section>
  );
}

function ExportPanel({
  token,
  user,
  patientId,
}: {
  token: string;
  user: UserProfile;
  patientId: string;
}) {
  const [page, setPage] = useState<{ items: RecordExport[]; total: number }>({
    items: [],
    total: 0,
  });
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [options, setOptions] = useState<ReturnType<typeof parseExportOptions> | null>(null);
  const [tutorId, setTutorId] = useState('');
  const [establishment, setEstablishment] = useState(true);
  const [justCreated, setJustCreated] = useState<RecordExport | null>(null);
  const root = `/patients/${patientId}/record-exports`;
  useEffect(() => {
    let active = true;
    void apiRequest(token, `${root}?limit=20&offset=${offset}`)
      .then((body) => {
        if (active) setPage(parseExportPage(body));
      })
      .catch((reason: unknown) => {
        if (active) setError(errorMessage(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, root, offset, revision]);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }
  async function prepare() {
    const next = parseExportOptions(await apiRequest(token, `${root}/options`));
    setTutorId(
      next.tutors.find((item) => item.is_primary)?.tutor.id ?? next.tutors[0]?.tutor.id ?? '',
    );
    setOptions(next);
    setJustCreated(null);
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await run(async () => {
      const saved = await createRecordExport(token, patientId, {
        tutor_id: tutorId,
        professional_address: data.get('professional_address'),
        professional_phone: data.get('professional_phone'),
        professional_email: data.get('professional_email'),
        establishment_legal_name: establishment ? data.get('establishment_legal_name') : null,
        establishment_cnpj: establishment ? data.get('establishment_cnpj') : null,
        establishment_crmv: establishment ? data.get('establishment_crmv') : null,
        acknowledge_unsigned: data.get('acknowledge_unsigned') === 'on',
      });
      setOptions(null);
      setJustCreated(saved);
      setOffset(0);
      setRevision((value) => value + 1);
      setNotice(
        'Cópia preparada e preservada. Confira e assine antes da entrega; o download não comprova recebimento.',
      );
    });
  }
  async function download(item: RecordExport, kind: 'file' | 'package') {
    await run(async () => {
      const file = await downloadRecordExport(token, item.id, kind);
      const url = URL.createObjectURL(file);
      const link = document.createElement('a');
      link.href = url;
      link.download = `prontuario-${item.id}.${kind === 'file' ? 'pdf' : 'zip'}`;
      document.body.append(link);
      link.click();
      link.remove();
      // O navegador pode consumir o blob depois que click() retorna.
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      setNotice(
        'Download solicitado. A assinatura e o comprovante de recebimento são procedimentos manuais da clínica.',
      );
    });
  }
  const selectedTutor = options?.tutors.find((item) => item.tutor.id === tutorId)?.tutor;
  const incomplete = !!options && (!selectedTutor?.document || !selectedTutor.address);
  const downloads = (item: RecordExport) => (
    <div className="actions">
      <button
        disabled={busy}
        className="secondary"
        onClick={() => {
          void download(item, 'file');
        }}
      >
        Baixar PDF
      </button>
      <button
        disabled={busy}
        className="secondary"
        onClick={() => {
          void download(item, 'package');
        }}
      >
        Baixar PDF e anexos (ZIP)
      </button>
    </div>
  );
  return (
    <div className="export-panel">
      <p className="confirmation">
        Os PDFs são gerados sem assinatura digital incorporada. Conferir o solicitante, assinar e
        obter comprovante de recebimento continuam sendo procedimentos manuais da clínica.
      </p>
      <ScreenFeedback error={error} />
      <ScreenFeedback notice={notice} />
      <div className="actions">
        {user.role === 'veterinarian' && (
          <button
            disabled={busy}
            onClick={() => {
              void run(prepare);
            }}
          >
            Preparar novo PDF
          </button>
        )}
        <button
          className="secondary"
          disabled={busy}
          onClick={() => {
            setLoading(true);
            setError('');
            setRevision((value) => value + 1);
          }}
        >
          Atualizar exportações
        </button>
      </div>
      {options && (
        <ActionScreen
          title={<>Preparar cópia do prontuário</>}
          onBack={() => {
            setOptions(null);
          }}
          busy={busy}
          error={error}
          notice={notice}
        >
          <form
            className="registry-form"
            onSubmit={(event) => {
              void submit(event);
            }}
          >
            <fieldset disabled={busy}>
              <p>
                {options.clinic_name} · {options.patient_name}
              </p>
              <label>
                Responsável identificado na cópia
                <select
                  required
                  value={tutorId}
                  onChange={(event) => setTutorId(event.target.value)}
                >
                  <option value="" disabled>
                    Selecione o responsável
                  </option>
                  {options.tutors.map(({ tutor }) => (
                    <option key={tutor.id} value={tutor.id}>
                      {tutor.name}
                      {tutor.deleted_at ? ' (arquivado)' : ''}
                    </option>
                  ))}
                </select>
              </label>
              {selectedTutor && (
                <p className="muted">
                  CPF: {selectedTutor.document || 'Não informado'} · Endereço:{' '}
                  {selectedTutor.address || 'Não informado'}
                </p>
              )}
              {incomplete && (
                <p className="confirmation">
                  Complete CPF e endereço no cadastro do responsável antes de emitir.
                </p>
              )}
              {options.tutors.length === 0 && (
                <p className="confirmation">Vincule um responsável ao paciente antes de emitir.</p>
              )}
              <p>
                Preparação por {user.name} · CRMV-{user.crmv_state} {user.crmv}
              </p>
              <label>
                Endereço profissional
                <textarea name="professional_address" required minLength={3} maxLength={500} />
              </label>
              <div className="field-pair">
                <label>
                  Telefone profissional
                  <input
                    name="professional_phone"
                    type="tel"
                    required
                    minLength={8}
                    maxLength={40}
                  />
                </label>
                <label>
                  E-mail profissional
                  <input name="professional_email" type="email" required maxLength={254} />
                </label>
              </div>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={establishment}
                  onChange={(event) => setEstablishment(event.target.checked)}
                />
                Identificar estabelecimento (pessoa jurídica)
              </label>
              {establishment && (
                <>
                  <label>
                    Razão social
                    <input name="establishment_legal_name" required maxLength={200} />
                  </label>
                  <div className="field-pair">
                    <label>
                      CNPJ
                      <input name="establishment_cnpj" required minLength={14} maxLength={18} />
                    </label>
                    <label>
                      Registro do estabelecimento no CRMV
                      <input name="establishment_crmv" required minLength={3} maxLength={40} />
                    </label>
                  </div>
                </>
              )}
              <p className="muted">
                Os dados profissionais informados ficam preservados nesta cópia. O histórico inclui
                registros vigentes e versões anteriores; rascunhos de IA não aprovados ficam fora.
                Anexos originais são fornecidos separadamente no ZIP.
              </p>
              <label className="checkbox">
                <input name="acknowledge_unsigned" type="checkbox" required />
                Conferi os dados e estou ciente de que a cópia precisa de assinatura e entrega
                manuais.
              </label>
              <div className="actions">
                <button disabled={incomplete || !tutorId}>
                  {busy ? 'Preparando…' : 'Confirmar preparação do PDF'}
                </button>
                <button className="secondary" type="button" onClick={() => setOptions(null)}>
                  Cancelar
                </button>
              </div>
            </fieldset>
          </form>
        </ActionScreen>
      )}
      {justCreated && !page.items.some((item) => item.id === justCreated.id) && (
        <div className="confirmation">
          <p>Cópia recém-preparada por {justCreated.author_name}</p>
          {downloads(justCreated)}
        </div>
      )}
      {loading ? (
        <p role="status">Carregando exportações…</p>
      ) : (
        <>
          {page.total === 0 && !justCreated && <p>Nenhuma exportação preparada.</p>}
          <ul className="link-list">
            {page.items.map((item) => (
              <li key={item.id}>
                <div>
                  <strong>{displayDateTime(item.created_at)}</strong>
                  <p>
                    {item.author_name} · {item.author_crmv}
                  </p>
                  <p>
                    Responsável: {item.tutor_name} · {item.attachment_count} arquivo(s) original(is)
                  </p>
                  {item.missing_file_count > 0 && (
                    <p className="confirmation">
                      {item.missing_file_count} documento(s) registrado(s) sem arquivo original.
                    </p>
                  )}
                  <p className="muted export-hash">SHA-256: {item.sha256}</p>
                  {downloads(item)}
                </div>
              </li>
            ))}
          </ul>
          <div className="pagination">
            <span>{page.total} exportação(ões)</span>
            <button
              className="secondary"
              disabled={busy || offset === 0}
              onClick={() => {
                setLoading(true);
                setOffset(offset - 20);
              }}
            >
              Exportações anteriores
            </button>
            <button
              className="secondary"
              disabled={busy || offset + 20 >= page.total}
              onClick={() => {
                setLoading(true);
                setOffset(offset + 20);
              }}
            >
              Mais exportações
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export function RecordExports(props: ComponentProps<typeof RecordExportsContent>) {
  return (
    <ScreenArea>
      <RecordExportsContent {...props} />
    </ScreenArea>
  );
}
