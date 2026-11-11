import type { ComponentProps } from 'react';
import { ActionScreen, ScreenArea, ScreenFeedback } from './Screen';
import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest } from './api';
import type { UserProfile } from './api';
import { errorMessage } from './registry-api';
import { displayDate } from './records-api';
import { displayDateTime } from './scheduling-api';

import {
  movementKinds,
  parseMovements,
  parseProduct,
  parseProducts,
  stockDisplay,
  stockQuantity,
} from './inventory-api';
import type { Movement, Product, ProductSummary } from './inventory-api';

const root = '/inventory/products';
type Operation = 'lots' | 'receipts' | 'issues' | 'adjustments' | 'archive';
interface Draft {
  id: string | null;
  name: string;
  unit: string;
  minimum_stock: string;
  track_expiry: boolean;
}

function InventoryContent({ token, user }: { token: string; user: UserProfile }) {
  const admin = user.role === 'admin';
  const operator = ['admin', 'veterinarian', 'assistant'].includes(user.role);
  const [page, setPage] = useState<{ items: ProductSummary[]; total: number }>({
    items: [],
    total: 0,
  });
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState({ q: '', archived: false });
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selected, setSelected] = useState<Product | null>(null);
  const [history, setHistory] = useState<{ items: Movement[]; total: number }>({
    items: [],
    total: 0,
  });
  const [historyOffset, setHistoryOffset] = useState(0);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [operation, setOperation] = useState<Operation | null>(null);
  const [correction, setCorrection] = useState<Movement | null>(null);

  useEffect(() => {
    let active = true;
    void apiRequest(
      token,
      `${root}?q=${encodeURIComponent(filter.q)}&archived=${filter.archived}&limit=20&offset=${offset}`,
    )
      .then((body) => {
        if (active) setPage(parseProducts(body));
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
  async function loadHistory(id: string, nextOffset = 0) {
    const body = parseMovements(
      await apiRequest(token, `${root}/${id}/movements?limit=20&offset=${nextOffset}`),
    );
    setHistory(body);
    setHistoryOffset(nextOffset);
  }
  async function open(id: string) {
    const product = parseProduct(await apiRequest(token, `${root}/${id}`));
    await loadHistory(id);
    setSelected(product);
    setDraft(null);
    setOperation(null);
    setCorrection(null);
  }
  async function saveProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft) return;
    await run(async () => {
      const values = {
        name: draft.name.trim(),
        unit: draft.unit.trim(),
        minimum_stock: stockQuantity(draft.minimum_stock, 'minimum'),
        track_expiry: draft.track_expiry,
        ...(draft.id && selected ? { expected_version: selected.version } : {}),
      };
      const saved = parseProduct(
        await apiRequest(
          token,
          `${root}${draft.id ? `/${draft.id}` : ''}`,
          values,
          draft.id ? 'PUT' : 'POST',
        ),
      );
      setSelected(saved);
      setDraft(null);
      setOperation(null);
      setHistory({ items: [], total: 0 });
      setHistoryOffset(0);
      setRevision((value) => value + 1);
      setNotice('Produto salvo.');
      try {
        await loadHistory(saved.id);
      } catch {
        setError(
          'Produto salvo, mas não foi possível atualizar o histórico. Use Atualizar produto.',
        );
      }
    });
  }
  async function submitOperation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !operation) return;
    const data = new FormData(event.currentTarget);
    await run(async () => {
      const values: Record<string, unknown> = { expected_version: selected.version };
      if (operation === 'lots') {
        values.code = String(data.get('code')).trim();
        values.expires_on = data.get('expires_on') || null;
      } else if (operation !== 'archive') {
        values.quantity = stockQuantity(
          String(data.get('quantity')),
          operation === 'adjustments' ? 'adjustment' : 'positive',
        );
        values.reason = String(data.get('reason')).trim();
        if (operation !== 'issues') values.lot_id = data.get('lot_id');
        if (operation === 'adjustments' && correction) values.corrects_id = correction.id;
      }
      const saved = parseProduct(
        await apiRequest(token, `${root}/${selected.id}/${operation}`, values, 'POST'),
      );
      setSelected(saved);
      setOperation(null);
      setCorrection(null);
      setRevision((value) => value + 1);
      setNotice(
        operation === 'issues'
          ? 'Saída registrada por FEFO. Confira os lotes no histórico.'
          : operation === 'archive'
            ? 'Produto arquivado. Histórico preservado.'
            : operation === 'lots'
              ? 'Lote cadastrado com saldo zero. Registre uma entrada para adicionar estoque.'
              : 'Movimentação registrada.',
      );
      try {
        await loadHistory(saved.id);
      } catch {
        setError(
          'Operação registrada, mas não foi possível atualizar o histórico. Use Atualizar produto.',
        );
      }
    });
  }
  function choose(next: Operation, original: Movement | null = null) {
    setDraft(null);
    setOperation(next);
    setCorrection(original);
    setError('');
    setNotice('');
  }
  const alertText = (p: ProductSummary) =>
    [
      p.low_stock ? 'Abaixo do mínimo' : '',
      p.expiring_lots ? `${p.expiring_lots} lote(s) vencem em até 30 dias` : '',
      p.expired_lots ? `${p.expired_lots} lote(s) vencidos com saldo` : '',
    ]
      .filter(Boolean)
      .join(' · ');

  return (
    <section className="panel registry inventory">
      <div className="section-heading">
        <div>
          <h2>Estoque</h2>
          <p className="muted">Produtos, lotes e consumo por validade.</p>
        </div>
        {admin && (
          <button
            disabled={busy}
            onClick={() => {
              setSelected(null);
              setOperation(null);
              setDraft({ id: null, name: '', unit: 'un', minimum_stock: '0', track_expiry: true });
              setError('');
              setNotice('');
            }}
          >
            Novo produto
          </button>
        )}
      </div>
      <ScreenFeedback error={error} />
      <ScreenFeedback notice={notice} />
      <form
        className="search-form inventory-search"
        onSubmit={(event) => {
          event.preventDefault();
          setLoading(true);
          setOffset(0);
          setFilter({ ...filter, q: query.trim() });
          setRevision((value) => value + 1);
        }}
      >
        <label>
          Buscar produto
          <input value={query} maxLength={100} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <label>
          Situação
          <select
            value={filter.archived ? 'archived' : 'active'}
            onChange={(event) => {
              setLoading(true);
              setOffset(0);
              setFilter({ ...filter, archived: event.target.value === 'archived' });
            }}
          >
            <option value="active">Ativos</option>
            <option value="archived">Arquivados</option>
          </select>
        </label>
        <button className="secondary" disabled={busy}>
          Buscar
        </button>
      </form>
      {loading ? (
        <p role="status">Carregando estoque…</p>
      ) : (
        <>
          <div className="table-scroll">
            <table>
              <caption>Produtos {filter.archived ? 'arquivados' : 'ativos'}</caption>
              <thead>
                <tr>
                  <th>Produto</th>
                  <th>Disponível</th>
                  <th>Físico</th>
                  <th>Alertas</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <button
                        className="text-button"
                        disabled={busy}
                        onClick={() => {
                          void run(() => open(p.id));
                        }}
                      >
                        {p.name}
                      </button>
                    </td>
                    <td>
                      {stockDisplay(p.available_stock)} {p.unit}
                    </td>
                    <td>
                      {stockDisplay(p.physical_stock)} {p.unit}
                    </td>
                    <td>{alertText(p) || 'Sem alertas'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {page.total === 0 && <p>Nenhum produto encontrado.</p>}
          <div className="pagination">
            <span>{page.total} produto(s)</span>
            <button
              className="secondary"
              disabled={busy || offset === 0}
              onClick={() => {
                setLoading(true);
                setOffset(offset - 20);
              }}
            >
              Anteriores
            </button>
            <button
              className="secondary"
              disabled={busy || offset + 20 >= page.total}
              onClick={() => {
                setLoading(true);
                setOffset(offset + 20);
              }}
            >
              Próximos
            </button>
          </div>
        </>
      )}
      {draft && (
        <ActionScreen
          title={<>{draft.id ? 'Editar produto' : 'Cadastrar produto'}</>}
          onBack={() => {
            setDraft(null);
          }}
          busy={busy}
          error={error}
          notice={notice}
          layer={selected ? 1 : 0}
        >
          <form
            className="registry-form"

            onSubmit={(event) => {
              void saveProduct(event);
            }}
          >
            <fieldset disabled={busy}>
              <label>
                Nome do produto
                <input
                  required
                  maxLength={200}
                  value={draft.name}
                  onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                />
              </label>
              <div className="field-pair">
                <label>
                  Unidade de controle
                  <input
                    required
                    maxLength={20}
                    value={draft.unit}
                    onChange={(event) => setDraft({ ...draft, unit: event.target.value })}
                  />
                </label>
                <label>
                  Estoque mínimo
                  <input
                    required
                    inputMode="decimal"
                    value={draft.minimum_stock}
                    onChange={(event) => setDraft({ ...draft, minimum_stock: event.target.value })}
                  />
                </label>
              </div>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={draft.track_expiry}
                  onChange={(event) => setDraft({ ...draft, track_expiry: event.target.checked })}
                />
                Exigir validade dos lotes
              </label>
              <p className="muted">
                Use uma única unidade por produto, com até três casas decimais. Unidade e controle
                de validade são preservados após a primeira movimentação.
              </p>
              <div className="actions">
                <button>Salvar produto</button>
                <button type="button" className="secondary" onClick={() => setDraft(null)}>
                  Cancelar
                </button>
              </div>
            </fieldset>
          </form>
        </ActionScreen>
      )}
      {selected && (
        <ActionScreen
          title={
            <>
              {selected.name}
              {selected.deleted_at ? ' · Arquivado' : ''}
            </>
          }
          onBack={() => {
            setSelected(null);
            setOperation(null);
            setDraft(null);
          }}
          busy={busy}
          error={error}
          notice={notice}
        >
          <article className="registry-form inventory-detail">
            <div className="section-heading">
              <button
                className="secondary"
                disabled={busy}
                onClick={() => {
                  void run(() => open(selected.id));
                }}
              >
                Atualizar produto
              </button>
            </div>
            <dl className="profile">
              <div>
                <dt>Disponível</dt>
                <dd>
                  {stockDisplay(selected.available_stock)} {selected.unit}
                </dd>
              </div>
              <div>
                <dt>Físico (inclui vencidos)</dt>
                <dd>
                  {stockDisplay(selected.physical_stock)} {selected.unit}
                </dd>
              </div>
              <div>
                <dt>Vencido</dt>
                <dd>
                  {stockDisplay(selected.expired_stock)} {selected.unit}
                </dd>
              </div>
              <div>
                <dt>Mínimo</dt>
                <dd>
                  {stockDisplay(selected.minimum_stock)} {selected.unit}
                </dd>
              </div>
            </dl>
            {alertText(selected) && <p className="stock-alert">{alertText(selected)}</p>}
            {!selected.deleted_at && (
              <div className="actions">
                {operator && (
                  <>
                    <button disabled={busy} onClick={() => choose('lots')}>
                      Cadastrar lote
                    </button>
                    <button
                      disabled={busy || selected.lots.length === 0}
                      onClick={() => choose('receipts')}
                    >
                      Registrar entrada
                    </button>
                    <button
                      disabled={
                        busy ||
                        selected.available_stock === '0.000' ||
                        selected.available_stock === '0'
                      }
                      onClick={() => choose('issues')}
                    >
                      Registrar saída FEFO
                    </button>
                  </>
                )}
                {admin && (
                  <>
                    <button
                      className="secondary"
                      disabled={busy || selected.lots.length === 0}
                      onClick={() => choose('adjustments')}
                    >
                      Ajustar inventário
                    </button>
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => {
                        setOperation(null);
                        setDraft({
                          id: selected.id,
                          name: selected.name,
                          unit: selected.unit,
                          minimum_stock: selected.minimum_stock.replace('.', ','),
                          track_expiry: selected.track_expiry,
                        });
                      }}
                    >
                      Editar produto
                    </button>
                    <button className="secondary" disabled={busy} onClick={() => choose('archive')}>
                      Arquivar produto
                    </button>
                  </>
                )}
              </div>
            )}
            {operation && (
              <ActionScreen
                title={
                  <>
                    {operation === 'lots'
                      ? 'Novo lote'
                      : operation === 'receipts'
                        ? 'Entrada no lote'
                        : operation === 'issues'
                          ? 'Saída por validade (FEFO)'
                          : operation === 'adjustments'
                            ? 'Ajuste de inventário'
                            : 'Arquivar produto'}
                  </>
                }
                onBack={() => {
                  setOperation(null);
                  setCorrection(null);
                }}
                busy={busy}
                error={error}
                notice={notice}
              >
                <form
                  key={`${operation}-${correction?.id ?? ''}`}
                  className="registry-form"
                  onSubmit={(event) => {
                    void submitOperation(event);
                  }}
                >
                  <fieldset disabled={busy}>
                    {operation === 'lots' ? (
                      <>
                        <label>
                          Código do lote
                          <input name="code" required maxLength={80} />
                        </label>
                        <label>
                          Validade
                          <input name="expires_on" type="date" required={selected.track_expiry} />
                        </label>
                        <p className="muted">
                          Código e validade ficam preservados. Lote vencido só recebe ajuste de
                          inventário.
                        </p>
                      </>
                    ) : operation === 'archive' ? (
                      <p>
                        O produto só pode ser arquivado com saldo físico zero. O histórico
                        continuará disponível.
                      </p>
                    ) : (
                      <>
                        {operation !== 'issues' && (
                          <label>
                            Lote
                            <select
                              name="lot_id"
                              required
                              defaultValue={correction?.lot_id ?? ''}
                              disabled={!!correction}
                            >
                              <option value="" disabled>
                                Selecione o lote
                              </option>
                              {selected.lots.map((l) => (
                                <option
                                  key={l.id}
                                  value={l.id}
                                  disabled={operation === 'receipts' && l.expired}
                                >
                                  {l.code} ·{' '}
                                  {l.expires_on ? displayDate(l.expires_on) : 'Sem validade'}
                                  {l.expired ? ' · Vencido' : ''}
                                </option>
                              ))}
                            </select>
                            {correction && (
                              <input type="hidden" name="lot_id" value={correction.lot_id} />
                            )}
                          </label>
                        )}
                        {operation === 'issues' && (
                          <p className="muted">
                            Consome primeiro os lotes válidos que vencem antes. Lotes sem validade
                            ficam por último. Se faltar saldo, nenhuma baixa será registrada.
                          </p>
                        )}
                        {correction && (
                          <p>
                            Correção de {movementKinds[correction.kind].toLowerCase()} de{' '}
                            {stockDisplay(correction.quantity)} {correction.unit}, registrada em{' '}
                            {displayDateTime(correction.created_at)}. O lançamento original será
                            preservado.
                          </p>
                        )}
                        <label>
                          {operation === 'adjustments'
                            ? 'Variação do saldo (use − para reduzir)'
                            : 'Quantidade'}
                          <input
                            name="quantity"
                            required
                            inputMode="decimal"
                            aria-describedby="stock-unit"
                          />
                        </label>
                        <p className="muted" id="stock-unit">
                          Unidade: {selected.unit}. Até três casas decimais.
                          {operation === 'adjustments'
                            ? ' Informe a diferença, não o saldo final. Descarte de vencidos usa quantidade negativa.'
                            : ''}
                        </p>
                        <label>
                          Motivo
                          <textarea name="reason" required minLength={3} maxLength={500} />
                        </label>
                      </>
                    )}
                    <div className="actions">
                      <button>
                        {operation === 'archive'
                          ? 'Confirmar arquivamento'
                          : operation === 'lots'
                            ? 'Salvar lote'
                            : 'Confirmar movimentação'}
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => {
                          setOperation(null);
                          setCorrection(null);
                        }}
                      >
                        Cancelar
                      </button>
                    </div>
                  </fieldset>
                </form>
              </ActionScreen>
            )}
            <div className="table-scroll">
              <table>
                <caption>Lotes e saldos</caption>
                <thead>
                  <tr>
                    <th>Lote</th>
                    <th>Validade</th>
                    <th>Saldo físico</th>
                    <th>Situação</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.lots.map((l) => (
                    <tr key={l.id}>
                      <td>{l.code}</td>
                      <td>{l.expires_on ? displayDate(l.expires_on) : 'Sem validade'}</td>
                      <td>
                        {stockDisplay(l.balance)} {selected.unit}
                      </td>
                      <td>
                        {l.expired ? 'Vencido' : l.expiring ? 'Vence em até 30 dias' : 'Regular'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {selected.lots.length === 0 && <p>Nenhum lote cadastrado.</p>}
            <div className="table-scroll">
              <table>
                <caption>Histórico de movimentações</caption>
                <thead>
                  <tr>
                    <th>Quando / autor</th>
                    <th>Operação / lote</th>
                    <th>Quantidade</th>
                    <th>Motivo</th>
                    {admin && <th>Correção</th>}
                  </tr>
                </thead>
                <tbody>
                  {history.items.map((m) => (
                    <tr key={m.id}>
                      <td>
                        {displayDateTime(m.created_at)}
                        <br />
                        {m.author_name}
                      </td>
                      <td>
                        {movementKinds[m.kind]} ·{' '}
                        {selected.lots.find((l) => l.id === m.lot_id)?.code ?? 'Lote'}
                        <br />
                        <small>{m.product_name}</small>
                        {m.corrects_id && <p className="muted">Corrige lançamento anterior</p>}
                      </td>
                      <td>
                        {stockDisplay(m.quantity)} {m.unit}
                      </td>
                      <td>{m.reason}</td>
                      {admin && (
                        <td>
                          {!selected.deleted_at && (
                            <button
                              className="secondary"
                              disabled={busy}
                              onClick={() => choose('adjustments', m)}
                            >
                              Corrigir lançamento
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {history.total === 0 && <p>Nenhuma movimentação registrada.</p>}
            <div className="pagination">
              <span>{history.total} movimentação(ões)</span>
              <button
                className="secondary"
                disabled={busy || historyOffset === 0}
                onClick={() => {
                  void run(() => loadHistory(selected.id, historyOffset - 20));
                }}
              >
                Movimentações anteriores
              </button>
              <button
                className="secondary"
                disabled={busy || historyOffset + 20 >= history.total}
                onClick={() => {
                  void run(() => loadHistory(selected.id, historyOffset + 20));
                }}
              >
                Mais movimentações
              </button>
            </div>
          </article>
        </ActionScreen>
      )}
    </section>
  );
}

export function Inventory(props: ComponentProps<typeof InventoryContent>) {
  return (
    <ScreenArea>
      <InventoryContent {...props} />
    </ScreenArea>
  );
}
