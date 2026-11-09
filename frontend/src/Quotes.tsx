import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest } from './api';
import type { UserProfile } from './api';
import { errorMessage, parsePage, parsePatient } from './registry-api';
import type { Patient } from './registry-api';
import { displayDate } from './records-api';
import { displayDateTime } from './scheduling-api';
import {
  decisionSources,
  money,
  moneyInput,
  parseQuote,
  parseQuoteOptions,
  parseQuotePage,
  preview,
  quantity,
  quoteStatuses,
  toCents,
} from './quotes-api';
import type { ItemDraft, Quote, QuoteOptions, QuoteSummary } from './quotes-api';
import { reveal } from './reveal';

interface Draft {
  id: string | null;
  version: number;
  patient_id: string;
  patient_name: string;
  tutor_id: string;
  encounter_id: string;
  valid_until: string;
  discount: string;
  items: ItemDraft[];
}
const emptyItem = (): ItemDraft => ({
  kind: 'service',
  description: '',
  quantity: '1',
  price: '0,00',
});
const today = () => new Date().toLocaleDateString('sv-SE', { timeZone: 'America/Fortaleza' });

export function Quotes({ token, user }: { token: string; user: UserProfile }) {
  const canWrite = user.role !== 'assistant';
  const [page, setPage] = useState<{ items: QuoteSummary[]; total: number }>({
    items: [],
    total: 0,
  });
  const [filter, setFilter] = useState({ q: '', status: '' });
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selected, setSelected] = useState<Quote | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [options, setOptions] = useState<QuoteOptions | null>(null);
  const [patientQuery, setPatientQuery] = useState('');
  const [patients, setPatients] = useState<Patient[]>([]);
  const [decision, setDecision] = useState<'approve' | 'reject' | null>(null);
  const [source, setSource] = useState('in_person');

  useEffect(() => {
    let active = true;
    void apiRequest(
      token,
      `/quotes?q=${encodeURIComponent(filter.q)}${filter.status ? `&status=${filter.status}` : ''}&limit=20&offset=${offset}`,
    )
      .then((body) => {
        if (active) setPage(parseQuotePage(body));
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
  }, [token, filter, offset, revision]);

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
  function refresh() {
    setLoading(true);
    setRevision((current) => current + 1);
  }
  async function open(id: string) {
    await run(async () => {
      setSelected(parseQuote(await apiRequest(token, `/quotes/${id}`)));
      setDraft(null);
      setDecision(null);
    });
  }
  async function edit(item: Quote) {
    await run(async () => {
      const choices = parseQuoteOptions(
        await apiRequest(token, `/quotes/options/${item.patient_id}`),
      );
      setOptions(choices);
      setSelected(null);
      setDecision(null);
      setPatients([]);
      setDraft({
        id: item.id,
        version: item.version,
        patient_id: item.patient_id,
        patient_name: item.patient_name,
        tutor_id: choices.tutors.some((t) => t.id === item.tutor_id) ? item.tutor_id : '',
        encounter_id: item.encounter_id ?? '',
        valid_until: item.valid_until ?? '',
        discount: moneyInput(item.discount_cents),
        items: item.items.map((line) => ({
          kind: line.kind,
          description: line.description,
          quantity: line.quantity,
          price: moneyInput(line.unit_price_cents),
        })),
      });
    });
  }
  async function choosePatient(patient: Patient) {
    await run(async () => {
      const choices = parseQuoteOptions(await apiRequest(token, `/quotes/options/${patient.id}`));
      setOptions(choices);
      setPatients([]);
      setDraft((current) =>
        current
          ? {
              ...current,
              patient_id: patient.id,
              patient_name: patient.name,
              tutor_id: choices.tutors.find((t) => t.is_primary)?.id ?? choices.tutors[0]?.id ?? '',
              encounter_id: '',
            }
          : current,
      );
    });
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft) return;
    await run(async () => {
      const totals = preview(draft.items, draft.discount);
      const values = {
        patient_id: draft.patient_id,
        tutor_id: draft.tutor_id,
        encounter_id: draft.encounter_id || null,
        valid_until: draft.valid_until || null,
        discount_cents: totals.discount,
        items: draft.items.map((item) => ({
          kind: item.kind,
          description: item.description.trim(),
          quantity: quantity(item.quantity).text,
          unit_price_cents: toCents(item.price),
        })),
        ...(draft.id ? { expected_version: draft.version } : {}),
      };
      setSelected(
        parseQuote(
          await apiRequest(
            token,
            draft.id ? `/quotes/${draft.id}` : '/quotes',
            values,
            draft.id ? 'PUT' : 'POST',
          ),
        ),
      );
      setDraft(null);
      setNotice('Rascunho do orçamento salvo.');
      refresh();
    });
  }
  async function transition(action: 'present' | 'revise') {
    if (!selected) return;
    await run(async () => {
      setSelected(
        parseQuote(
          await apiRequest(
            token,
            `/quotes/${selected.id}/${action}`,
            { expected_version: selected.version },
            'POST',
          ),
        ),
      );
      setDecision(null);
      setNotice(
        action === 'present'
          ? 'Apresentação registrada. Itens e valores preservados.'
          : 'Nova revisão criada em rascunho. O orçamento anterior foi preservado.',
      );
      refresh();
    });
  }
  async function recordDecision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !decision) return;
    const data = new FormData(event.currentTarget);
    await run(async () => {
      setSelected(
        parseQuote(
          await apiRequest(
            token,
            `/quotes/${selected.id}/${decision}`,
            {
              expected_version: selected.version,
              source,
              note: String(data.get('note') ?? '').trim() || null,
            },
            'POST',
          ),
        ),
      );
      setDecision(null);
      setNotice('Decisão do tutor registrada.');
      refresh();
    });
  }
  function updateItem(index: number, changes: Partial<ItemDraft>) {
    if (draft)
      setDraft({
        ...draft,
        items: draft.items.map((item, current) =>
          current === index ? { ...item, ...changes } : item,
        ),
      });
  }
  let totals: ReturnType<typeof preview> | null = null;
  let calculationError = '';
  if (draft) {
    try {
      totals = preview(draft.items, draft.discount);
    } catch (reason) {
      calculationError = errorMessage(reason);
    }
  }

  return (
    <section className="panel registry" aria-labelledby="quotes-title">
      <div className="section-heading">
        <div>
          <h2 id="quotes-title">Orçamentos</h2>
          <p className="muted">
            Estimativas de serviços e produtos, com decisão do tutor registrada pela equipe.
          </p>
        </div>
        {canWrite && (
          <button
            disabled={busy}
            onClick={() => {
              setDraft({
                id: null,
                version: 1,
                patient_id: '',
                patient_name: '',
                tutor_id: '',
                encounter_id: '',
                valid_until: '',
                discount: '0,00',
                items: [emptyItem()],
              });
              setSelected(null);
              setOptions(null);
              setPatients([]);
              setPatientQuery('');
              setError('');
              setNotice('');
            }}
          >
            Novo orçamento
          </button>
        )}
      </div>
      <form
        className="search-form"
        onSubmit={(event) => {
          event.preventDefault();
          setLoading(true);
          setOffset(0);
          setFilter((current) => ({ ...current, q: query.trim() }));
        }}
      >
        <label>
          Buscar orçamento
          <input
            value={query}
            maxLength={100}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Paciente ou tutor"
          />
        </label>
        <button className="secondary">Pesquisar</button>
      </form>
      <label>
        Situação do orçamento
        <select
          value={filter.status}
          onChange={(event) => {
            setLoading(true);
            setOffset(0);
            setFilter({ ...filter, status: event.target.value });
          }}
        >
          <option value="">Todas</option>
          {Object.entries(quoteStatuses).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </label>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="success-message" role="status">
          {notice}
        </p>
      )}
      {loading ? (
        <p role="status">Carregando orçamentos…</p>
      ) : page.items.length === 0 ? (
        <p>Nenhum orçamento encontrado.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Paciente / tutor</th>
                <th>Criação</th>
                <th>Situação</th>
                <th>Total</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {page.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    {item.patient_name}
                    <br />
                    <span className="muted">{item.tutor_name}</span>
                  </td>
                  <td>{displayDateTime(item.created_at)}</td>
                  <td>{quoteStatuses[item.status]}</td>
                  <td>{money(item.total_cents)}</td>
                  <td>
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => {
                        void open(item.id);
                      }}
                    >
                      Abrir orçamento de {item.patient_name}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="pagination">
        <span>{page.total} orçamento(s)</span>
        <div className="actions">
          <button
            className="secondary"
            disabled={loading || offset === 0}
            onClick={() => {
              setLoading(true);
              setOffset(Math.max(0, offset - 20));
            }}
          >
            Anterior
          </button>
          <button
            className="secondary"
            disabled={loading || offset + 20 >= page.total}
            onClick={() => {
              setLoading(true);
              setOffset(offset + 20);
            }}
          >
            Próxima
          </button>
        </div>
      </div>
      {draft && (
        <form
          className="registry-form"
          key={draft.id ?? 'novo'}
          ref={reveal}
          onSubmit={(event) => {
            void save(event);
          }}
        >
          <h3>{draft.id ? 'Editar rascunho de orçamento' : 'Novo orçamento'}</h3>
          <div className="field-pair">
            <label>
              Buscar paciente do orçamento
              <input
                value={patientQuery}
                onChange={(event) => setPatientQuery(event.target.value)}
                maxLength={100}
              />
            </label>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => {
                void run(async () =>
                  setPatients(
                    parsePage(
                      await apiRequest(
                        token,
                        `/patients?q=${encodeURIComponent(patientQuery.trim())}&limit=20&offset=0`,
                      ),
                      parsePatient,
                    ).items,
                  ),
                );
              }}
            >
              Buscar pacientes
            </button>
          </div>
          {patients.length > 0 && (
            <ul className="link-list">
              {patients.map((patient) => (
                <li key={patient.id}>
                  {patient.name}
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy}
                    onClick={() => {
                      void choosePatient(patient);
                    }}
                  >
                    Selecionar {patient.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p>
            Paciente selecionado:{' '}
            <strong>{draft.patient_name || 'Selecione um paciente acima'}</strong>
          </p>
          <label>
            Tutor do orçamento
            <select
              value={draft.tutor_id}
              required
              disabled={busy || !options}
              onChange={(event) => setDraft({ ...draft, tutor_id: event.target.value })}
            >
              <option value="">Selecione</option>
              {options?.tutors.map((tutor) => (
                <option key={tutor.id} value={tutor.id}>
                  {tutor.name}
                  {tutor.is_primary ? ' (principal)' : ''}
                </option>
              ))}
            </select>
          </label>
          {options?.tutors.length === 0 && (
            <p className="confirmation">
              Vincule um tutor ativo ao paciente em Animais antes de criar o orçamento.
            </p>
          )}
          <label>
            Atendimento do orçamento (opcional)
            <select
              value={draft.encounter_id}
              disabled={busy || !options}
              onChange={(event) => setDraft({ ...draft, encounter_id: event.target.value })}
            >
              <option value="">Sem atendimento</option>
              {options?.encounters.map((item) => (
                <option key={item.id} value={item.id}>
                  {displayDateTime(item.started_at)} com {item.veterinarian_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Validade do orçamento (opcional)
            <input
              type="date"
              min={today()}
              value={draft.valid_until}
              onChange={(event) => setDraft({ ...draft, valid_until: event.target.value })}
            />
          </label>
          {draft.items.map((item, index) => (
            <fieldset key={index}>
              <legend>Item {index + 1}</legend>
              <label>
                Tipo do item {index + 1}
                <select
                  value={item.kind}
                  onChange={(event) =>
                    updateItem(index, { kind: event.target.value as ItemDraft['kind'] })
                  }
                >
                  <option value="service">Serviço</option>
                  <option value="product">Produto</option>
                </select>
              </label>
              <label>
                Descrição do item {index + 1}
                <input
                  value={item.description}
                  required
                  maxLength={300}
                  onChange={(event) => updateItem(index, { description: event.target.value })}
                />
              </label>
              <div className="field-pair">
                <label>
                  Quantidade do item {index + 1}
                  <input
                    value={item.quantity}
                    required
                    inputMode="decimal"
                    onChange={(event) => updateItem(index, { quantity: event.target.value })}
                  />
                </label>
                <label>
                  Preço unitário do item {index + 1} (R$)
                  <input
                    value={item.price}
                    required
                    inputMode="decimal"
                    onChange={(event) => updateItem(index, { price: event.target.value })}
                  />
                </label>
              </div>
              <button
                type="button"
                className="secondary"
                disabled={busy || draft.items.length === 1}
                onClick={() =>
                  setDraft({
                    ...draft,
                    items: draft.items.filter((_, current) => current !== index),
                  })
                }
              >
                Remover item {index + 1}
              </button>
            </fieldset>
          ))}
          <button
            type="button"
            className="secondary"
            disabled={busy || draft.items.length >= 100}
            onClick={() => setDraft({ ...draft, items: [...draft.items, emptyItem()] })}
          >
            Adicionar item
          </button>
          <label>
            Desconto do orçamento (R$)
            <input
              value={draft.discount}
              required
              inputMode="decimal"
              onChange={(event) => setDraft({ ...draft, discount: event.target.value })}
            />
          </label>
          <p className="muted">
            Quantidades com até três casas decimais; preços e desconto com até duas, sem separador
            de milhar. Valores finais são conferidos pelo servidor.
          </p>
          {totals ? (
            <p>
              Subtotal: {money(totals.subtotal)} · Desconto: {money(totals.discount)} ·{' '}
              <strong>Total: {money(totals.total)}</strong>
            </p>
          ) : (
            <p className="form-error">{calculationError}</p>
          )}
          <div className="actions">
            <button disabled={busy || !draft.patient_id || !draft.tutor_id || !totals}>
              Salvar rascunho
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => setDraft(null)}
            >
              Cancelar edição
            </button>
          </div>
        </form>
      )}
      {selected && (
        <section
          className="registry-form"
          key={selected.id}
          ref={reveal}
          aria-labelledby="quote-detail-title"
        >
          <h3 id="quote-detail-title">Orçamento de {selected.patient_name}</h3>
          <p>
            Tutor: {selected.tutor_name} · {quoteStatuses[selected.status]}
            {selected.valid_until && ` · Válido até ${displayDate(selected.valid_until)}`}
          </p>
          {selected.source_quote_id && (
            <button
              className="secondary"
              disabled={busy}
              onClick={() => {
                if (selected.source_quote_id) void open(selected.source_quote_id);
              }}
            >
              Ver orçamento anterior
            </button>
          )}
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Item</th>
                  <th>Quantidade</th>
                  <th>Preço unitário</th>
                  <th>Total do item</th>
                </tr>
              </thead>
              <tbody>
                {selected.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      {item.description}
                      <br />
                      <span className="muted">
                        {item.kind === 'service' ? 'Serviço' : 'Produto'}
                      </span>
                    </td>
                    <td>{item.quantity.replace('.', ',')}</td>
                    <td>{money(item.unit_price_cents)}</td>
                    <td>{money(item.line_total_cents)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>
            Subtotal: {money(selected.subtotal_cents)} · Desconto: {money(selected.discount_cents)}{' '}
            · <strong>Total: {money(selected.total_cents)}</strong>
          </p>
          {selected.presented_at && (
            <p className="muted">
              Apresentação registrada em {displayDateTime(selected.presented_at)}. Itens e valores
              preservados.
            </p>
          )}
          {selected.decision_source && selected.decision_at && (
            <p>
              Decisão informada pelo tutor e registrada em {displayDateTime(selected.decision_at)} ·{' '}
              {decisionSources[selected.decision_source]}
              {selected.decision_note && `: ${selected.decision_note}`}
            </p>
          )}
          {canWrite && (
            <div className="actions">
              {selected.status === 'draft' && (
                <>
                  <button
                    disabled={busy}
                    onClick={() => {
                      void edit(selected);
                    }}
                  >
                    Editar rascunho
                  </button>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => {
                      void transition('present');
                    }}
                  >
                    Marcar como apresentado
                  </button>
                </>
              )}
              {selected.status === 'sent' && (
                <>
                  <button
                    disabled={busy}
                    onClick={() => {
                      setDecision('approve');
                      setSource('in_person');
                    }}
                  >
                    Registrar aprovação
                  </button>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => {
                      setDecision('reject');
                      setSource('in_person');
                    }}
                  >
                    Registrar recusa
                  </button>
                </>
              )}
              {selected.status !== 'draft' && (
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => {
                    void transition('revise');
                  }}
                >
                  Criar revisão
                </button>
              )}
            </div>
          )}
          {selected.status === 'draft' && (
            <p className="muted">
              Marque como apresentado somente após mostrar o orçamento ao tutor. Essa ação registra
              a apresentação e não envia uma mensagem.
            </p>
          )}
          {decision && selected.status === 'sent' && (
            <form
              className="registry-form"
              ref={reveal}
              onSubmit={(event) => {
                void recordDecision(event);
              }}
            >
              <h4>
                {decision === 'approve'
                  ? 'Aprovação comunicada pelo tutor'
                  : 'Recusa comunicada pelo tutor'}
              </h4>
              <label>
                Origem da decisão
                <select value={source} onChange={(event) => setSource(event.target.value)}>
                  {Object.entries(decisionSources).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Observação da decisão{source === 'other' ? '' : ' (opcional)'}
                <textarea name="note" required={source === 'other'} maxLength={500} />
              </label>
              <div className="actions">
                <button disabled={busy}>
                  {decision === 'approve'
                    ? 'Confirmar registro de aprovação'
                    : 'Confirmar registro de recusa'}
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => setDecision(null)}
                >
                  Cancelar decisão
                </button>
              </div>
            </form>
          )}
        </section>
      )}
    </section>
  );
}
