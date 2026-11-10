import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest } from './api';
import type { UserProfile } from './api';
import { errorMessage, parsePage, parsePatient, parseTutor } from './registry-api';
import {
  financialCents,
  financialKinds,
  financialMoney,
  financialToday,
  parseFinancialEntry,
  parseFinancialPage,
  paymentMethods,
} from './financial-api';
import type { FinancialEntry, FinancialPage } from './financial-api';

type Option = { id: string; name: string };
function PartySearch({
  token,
  kind,
  selected,
  onSelect,
}: {
  token: string;
  kind: 'tutors' | 'patients';
  selected: Option | null;
  onSelect: (value: Option | null) => void;
}) {
  const label = kind === 'tutors' ? 'tutor' : 'animal';
  const [search, setSearch] = useState('');
  const [options, setOptions] = useState<Option[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function find() {
    setBusy(true);
    setError('');
    try {
      const data = await apiRequest(
        token,
        `/${kind}?q=${encodeURIComponent(search.trim())}&limit=20`,
      );
      const result =
        kind === 'tutors' ? parsePage(data, parseTutor) : parsePage(data, parsePatient);
      setOptions(result.items);
      if (result.items.length === 0) setError('Nenhum resultado. Tente outro nome.');
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }
  return (
    <fieldset>
      <legend>{kind === 'tutors' ? 'Tutor' : 'Animal'} (opcional)</legend>
      <label>
        Buscar {label} por nome
        <input
          value={search}
          disabled={busy}
          maxLength={100}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      <button
        type="button"
        className="secondary"
        disabled={busy || !search.trim()}
        onClick={() => {
          void find();
        }}
      >
        Buscar {label}
      </button>
      <label>
        {kind === 'tutors' ? 'Tutor vinculado' : 'Animal vinculado'}
        <select
          value={selected?.id ?? ''}
          disabled={busy}
          onChange={(event) => {
            onSelect(options.find((option) => option.id === event.target.value) ?? null);
          }}
        >
          <option value="">Sem vínculo</option>
          {selected && !options.some((option) => option.id === selected.id) && (
            <option value={selected.id}>{selected.name}</option>
          )}
          {options.map((option) => (
            <option key={option.id} value={option.id}>
              {option.name}
            </option>
          ))}
        </select>
      </label>
      {error && <p role="status">{error}</p>}
      <small>Busca limitada a 20 resultados; refine o nome se necessário.</small>
    </fieldset>
  );
}

export function Financial({ token, user }: { token: string; user: UserProfile }) {
  if (!user.active || !['admin', 'reception'].includes(user.role)) return null;
  return (
    <FinancialWorkspace key={`${token}:${user.role}`} token={token} admin={user.role === 'admin'} />
  );
}

function FinancialWorkspace({ token, admin }: { token: string; admin: boolean }) {
  const today = financialToday();
  const [filters, setFilters] = useState(() =>
    new URLSearchParams({
      start: `${today.slice(0, 7)}-01`,
      end: today,
    }).toString(),
  );
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [page, setPage] = useState<FinancialPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState('');
  const [formError, setFormError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [tutor, setTutor] = useState<Option | null>(null);
  const [patient, setPatient] = useState<Option | null>(null);
  const [reversing, setReversing] = useState<FinancialEntry | null>(null);

  useEffect(() => {
    let active = true;
    void apiRequest(token, `/financial/entries?${filters}&limit=20&offset=${offset}`)
      .then(parseFinancialPage)
      .then((result) => {
        if (active) {
          setPage(result);
          setListError('');
        }
      })
      .catch((reason) => {
        if (active) {
          setPage(null);
          setListError(errorMessage(reason));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, filters, offset, revision]);

  function refresh() {
    setLoading(true);
    setRevision((current) => current + 1);
  }
  function filter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (String(data.get('start')) > String(data.get('end'))) {
      setListError('O início do período deve ser anterior ou igual ao fim.');
      return;
    }
    const params = new URLSearchParams();
    for (const [name, value] of data)
      if (String(value).trim()) params.set(name, String(value).trim());
    setFilters(params.toString());
    setOffset(0);
    refresh();
  }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setFormError('');
    setNotice('');
    try {
      const saved = parseFinancialEntry(
        await apiRequest(
          token,
          '/financial/entries',
          {
            kind: admin ? String(data.get('kind')) : 'income',
            description: String(data.get('description')).trim(),
            category: String(data.get('category')).trim(),
            amount_cents: financialCents(String(data.get('amount'))),
            occurred_on: String(data.get('occurred_on')),
            payment_method: String(data.get('payment_method')),
            tutor_id: tutor?.id ?? null,
            patient_id: patient?.id ?? null,
          },
          'POST',
        ),
      );
      setNotice(
        `${saved.kind === 'income' ? 'Recebimento registrado' : 'Despesa registrada'}. Consulte o período correspondente na lista.`,
      );
      form.reset();
      setTutor(null);
      setPatient(null);
      refresh();
    } catch (reason) {
      setFormError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }
  async function reverse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reversing || !admin) return;
    const reason = String(new FormData(event.currentTarget).get('reason')).trim();
    if (reason.length < 3) {
      setFormError('Descreva o motivo com pelo menos 3 caracteres.');
      return;
    }
    setBusy(true);
    setFormError('');
    setNotice('');
    try {
      parseFinancialEntry(
        await apiRequest(token, `/financial/entries/${reversing.id}/reverse`, { reason }, 'POST'),
      );
      setReversing(null);
      setNotice('Estorno registrado na data financeira original.');
      refresh();
    } catch (failure) {
      setFormError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel registry">
      <div className="section-heading">
        <div>
          <h2>Financeiro</h2>
          <p>Registre valores já recebidos ou pagos. Este registro não movimenta dinheiro.</p>
        </div>
        <button type="button" className="secondary" disabled={loading || busy} onClick={refresh}>
          Atualizar lançamentos
        </button>
      </div>
      <p className="muted">
        Orçamentos não geram lançamentos automaticamente.
        {admin
          ? ' A diferença entre recebimentos e despesas não representa lucro contábil nem saldo bancário.'
          : ' Seu acesso permite registrar e consultar recebimentos. Para corrigir, solicite ao administrador.'}
      </p>
      <form
        className="registry-form financial-filters"
        onSubmit={filter}
        aria-label="Filtrar financeiro"
      >
        <div className="field-pair">
          <label>
            De
            <input name="start" type="date" required defaultValue={`${today.slice(0, 7)}-01`} />
          </label>
          <label>
            Até
            <input name="end" type="date" required defaultValue={today} />
          </label>
        </div>
        <div className="field-pair">
          <label>
            Buscar descrição
            <input name="q" maxLength={100} />
          </label>
          <label>
            Categoria do filtro
            <input name="category" maxLength={80} placeholder="Nome exato" />
          </label>
        </div>
        <div className="field-pair">
          <label>
            Forma do filtro
            <select name="payment_method">
              <option value="">Todas as formas</option>
              {Object.entries(paymentMethods).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Situação
            <select name="status">
              <option value="">Todas</option>
              <option value="posted">Vigente</option>
              <option value="reversed">Estornado</option>
            </select>
          </label>
        </div>
        {admin && (
          <label>
            Tipo do filtro
            <select name="kind">
              <option value="">Todos os tipos</option>
              <option value="income">Recebimento</option>
              <option value="expense">Despesa</option>
            </select>
          </label>
        )}
        <button disabled={busy}>Aplicar filtros</button>
      </form>
      {listError && (
        <p className="form-error" role="alert">
          {listError}
        </p>
      )}
      {loading && <p role="status">Carregando lançamentos…</p>}
      {!loading && page && (
        <>
          <dl className="profile financial-summary" aria-label="Totais efetivos filtrados">
            <div>
              <dt>Recebimentos vigentes</dt>
              <dd>{financialMoney(page.summary.income_cents)}</dd>
            </div>
            {admin &&
              page.summary.expense_cents !== null &&
              page.summary.difference_cents !== null && (
                <>
                  <div>
                    <dt>Despesas vigentes</dt>
                    <dd>{financialMoney(page.summary.expense_cents)}</dd>
                  </div>
                  <div>
                    <dt>Diferença do período</dt>
                    <dd>{financialMoney(page.summary.difference_cents)}</dd>
                  </div>
                </>
              )}
          </dl>
          <p className="muted">
            Totais de todos os resultados filtrados. Lançamentos estornados não compõem os totais.
          </p>
          <div className="table-scroll">
            <table aria-label="Lançamentos financeiros">
              <thead>
                <tr>
                  <th>Data financeira</th>
                  <th>Descrição</th>
                  <th>Valor</th>
                  <th>Autoria e situação</th>
                  {admin && <th>Ação</th>}
                </tr>
              </thead>
              <tbody>
                {page.items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.occurred_on.split('-').reverse().join('/')}</td>
                    <td>
                      <strong>{item.description}</strong>
                      <div>
                        {item.category} · {paymentMethods[item.payment_method]}
                      </div>
                      {item.tutor_name && <div>Tutor: {item.tutor_name}</div>}
                      {item.patient_name && <div>Animal: {item.patient_name}</div>}
                    </td>
                    <td>
                      {financialKinds[item.kind]}
                      <div>{financialMoney(item.amount_cents)}</div>
                    </td>
                    <td>
                      {item.author_name}
                      <div>
                        {new Date(item.created_at).toLocaleString('pt-BR', {
                          timeZone: 'America/Fortaleza',
                        })}
                      </div>
                      <strong>{item.status === 'posted' ? 'Vigente' : 'Estornado'}</strong>
                      {item.reversal && (
                        <div className="financial-reversal">
                          {item.reversal.reversal_reason}
                          <div>
                            {item.reversal.author_name} ·{' '}
                            {new Date(item.reversal.created_at).toLocaleString('pt-BR', {
                              timeZone: 'America/Fortaleza',
                            })}
                          </div>
                        </div>
                      )}
                    </td>
                    {admin && (
                      <td>
                        {item.status === 'posted' && (
                          <button
                            type="button"
                            className="secondary"
                            disabled={busy}
                            onClick={() => {
                              setReversing(item);
                              setFormError('');
                              setNotice('');
                            }}
                            aria-label={`Estornar ${item.description}`}
                          >
                            Estornar
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {page.items.length === 0 && <p>Nenhum lançamento neste filtro.</p>}
          <div className="pagination">
            <span>{page.total} lançamento(s)</span>
            <button
              type="button"
              className="secondary"
              disabled={offset === 0 || busy}
              onClick={() => {
                setOffset((current) => Math.max(0, current - 20));
                setLoading(true);
              }}
            >
              Anterior
            </button>
            <button
              type="button"
              className="secondary"
              disabled={offset + 20 >= page.total || busy}
              onClick={() => {
                setOffset((current) => current + 20);
                setLoading(true);
              }}
            >
              Próxima
            </button>
          </div>
        </>
      )}
      {notice && (
        <p className="success-message" role="status">
          {notice}
        </p>
      )}
      {formError && (
        <p className="form-error" role="alert">
          {formError}
        </p>
      )}
      {reversing && admin ? (
        <form
          className="registry-form"
          onSubmit={(event) => {
            void reverse(event);
          }}
          aria-label="Estornar lançamento"
        >
          <h3>Estornar {reversing.description}</h3>
          <p>
            {financialMoney(reversing.amount_cents)} ·{' '}
            {reversing.occurred_on.split('-').reverse().join('/')}
          </p>
          <p>
            O original será preservado e deixará de compor os totais na sua data financeira. Este
            estorno é administrativo; uma devolução real deve ser registrada como despesa.
          </p>
          <label>
            Motivo do estorno
            <textarea name="reason" minLength={3} maxLength={500} required disabled={busy} />
          </label>
          <div className="actions">
            <button disabled={busy}>Confirmar estorno</button>
            <button
              className="secondary"
              type="button"
              disabled={busy}
              onClick={() => {
                setReversing(null);
                setFormError('');
              }}
            >
              Cancelar
            </button>
          </div>
        </form>
      ) : (
        <form
          className="registry-form"
          onSubmit={(event) => {
            void create(event);
          }}
          aria-label="Novo lançamento"
        >
          <h3>{admin ? 'Novo lançamento' : 'Novo recebimento'}</h3>
          <fieldset disabled={busy}>
            {admin && (
              <label>
                Tipo
                <select name="kind">
                  <option value="income">Recebimento</option>
                  <option value="expense">Despesa</option>
                </select>
              </label>
            )}
            <label>
              Descrição
              <input name="description" maxLength={300} required />
            </label>
            <div className="field-pair">
              <label>
                Categoria
                <input name="category" maxLength={80} required />
              </label>
              <label>
                Valor em reais
                <input name="amount" inputMode="decimal" placeholder="123,45" required />
              </label>
            </div>
            <div className="field-pair">
              <label>
                Data do recebimento ou pagamento
                <input name="occurred_on" type="date" defaultValue={today} max={today} required />
              </label>
              <label>
                Forma de pagamento
                <select name="payment_method">
                  {Object.entries(paymentMethods).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <PartySearch token={token} kind="tutors" selected={tutor} onSelect={setTutor} />
            <PartySearch token={token} kind="patients" selected={patient} onSelect={setPatient} />
            <p className="muted">
              Se informar ambos, o tutor deve estar vinculado ao animal no cadastro.
            </p>
            <button disabled={busy}>{busy ? 'Registrando…' : 'Registrar lançamento'}</button>
          </fieldset>
        </form>
      )}
    </section>
  );
}
