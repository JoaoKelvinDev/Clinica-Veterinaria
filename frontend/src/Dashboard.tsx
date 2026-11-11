import { useEffect, useState } from 'react';
import { apiRequest } from './api';
import type { UserProfile } from './api';
import { dashboardDate, parseDashboard } from './dashboard-api';
import type { DashboardData, DashboardDestination } from './dashboard-api';
import { financialMoney } from './financial-api';
import { errorMessage } from './registry-api';

export function Dashboard({
  token,
  user,
  onNavigate,
}: {
  token: string;
  user: UserProfile;
  onNavigate: (destination: DashboardDestination) => void;
}) {
  return (
    <DashboardContent
      key={`${token}:${user.id}:${user.role}`}
      token={token}
      user={user}
      onNavigate={onNavigate}
    />
  );
}

function DashboardContent({
  token,
  user,
  onNavigate,
}: {
  token: string;
  user: UserProfile;
  onNavigate: (destination: DashboardDestination) => void;
}) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    void apiRequest(token, '/dashboard')
      .then((value) => parseDashboard(value, user.role))
      .then((next) => {
        if (active) {
          setData(next);
          setError('');
        }
      })
      .catch((reason) => {
        if (active) {
          setData(null);
          setError(errorMessage(reason));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, user.role, revision]);
  function refresh() {
    setLoading(true);
    setData(null);
    setError('');
    setRevision((current) => current + 1);
  }
  return (
    <section className="panel dashboard" aria-labelledby="dashboard-title">
      <div className="section-heading">
        <div>
          <p className="screen-eyebrow">Rotina da clínica</p>
          <h2 id="dashboard-title">Visão geral</h2>
          <p className="muted">Acompanhe o dia e abra a área que precisa de atenção.</p>
        </div>
        <button className="secondary" disabled={loading} onClick={refresh}>
          Atualizar visão geral
        </button>
      </div>
      {loading && <p role="status">Carregando visão geral…</p>}
      {error && (
        <p className="form-error" role="alert">
          {error} Use “Atualizar visão geral” para tentar novamente.
        </p>
      )}
      {!loading && data && (
        <>
          <p className="dashboard-updated">
            Dia {dashboardDate(data.day)} · Atualizado em{' '}
            {new Date(data.generated_at).toLocaleString('pt-BR', { timeZone: data.timezone })} ·
            Horário de Fortaleza
          </p>
          <div className="dashboard-grid">
            <article className="dashboard-card" aria-labelledby="dashboard-scheduling">
              <div className="dashboard-card-heading">
                <span className="dashboard-kicker">Hoje</span>
                <h3 id="dashboard-scheduling">Agenda e atendimentos</h3>
              </div>
              <dl>
                <div className="dashboard-metric">
                  <dt>Agendamentos no dia</dt>
                  <dd>{data.scheduling.appointments_total.toLocaleString('pt-BR')}</dd>
                </div>
                <div>
                  <dt>Agendados</dt>
                  <dd>{data.scheduling.scheduled}</dd>
                </div>
                <div>
                  <dt>Confirmados</dt>
                  <dd>{data.scheduling.confirmed}</dd>
                </div>
                <div>
                  <dt>Em atendimento</dt>
                  <dd>{data.scheduling.in_progress}</dd>
                </div>
                <div>
                  <dt>Concluídos</dt>
                  <dd>{data.scheduling.completed}</dd>
                </div>
                <div>
                  <dt>Cancelados</dt>
                  <dd>{data.scheduling.cancelled}</dd>
                </div>
                <div>
                  <dt>Faltas</dt>
                  <dd>{data.scheduling.no_show}</dd>
                </div>
                <div className="dashboard-divider">
                  <dt>Atendimentos em aberto</dt>
                  <dd>{data.scheduling.open_encounters}</dd>
                </div>
              </dl>
              <p className="muted">Em aberto inclui atendimentos de dias anteriores.</p>
              <button className="secondary" onClick={() => onNavigate('scheduling')}>
                Ver agenda
              </button>
            </article>
            <article className="dashboard-card" aria-labelledby="dashboard-messaging">
              <div className="dashboard-card-heading">
                <span className="dashboard-kicker">Equipe</span>
                <h3 id="dashboard-messaging">Comunicação</h3>
              </div>
              <dl>
                <div className="dashboard-metric">
                  <dt>Mensagens aguardando atenção</dt>
                  <dd>{data.messaging.needs_attention.toLocaleString('pt-BR')}</dd>
                </div>
              </dl>
              <p>
                {data.messaging.needs_attention === 0
                  ? 'Nenhuma mensagem aguardando a equipe.'
                  : 'Abra as mensagens para conferir as respostas pendentes.'}
              </p>
              {data.messaging.simulated && (
                <p className="muted">Modo de testes (MOCK): os envios continuam simulados.</p>
              )}
              <button className="secondary" onClick={() => onNavigate('messaging')}>
                Ver mensagens
              </button>
            </article>
            <article className="dashboard-card" aria-labelledby="dashboard-inventory">
              <div className="dashboard-card-heading">
                <span className="dashboard-kicker">Insumos</span>
                <h3 id="dashboard-inventory">Alertas de estoque</h3>
              </div>
              <dl>
                <div className="dashboard-metric">
                  <dt>Produtos abaixo do mínimo</dt>
                  <dd>{data.inventory.low_stock_products}</dd>
                </div>
                <div>
                  <dt>Lotes vencidos</dt>
                  <dd>{data.inventory.expired_lots}</dd>
                </div>
                <div>
                  <dt>Lotes que vencem em até 30 dias</dt>
                  <dd>{data.inventory.expiring_lots}</dd>
                </div>
              </dl>
              <p className="muted">
                Produtos ativos. Alertas de validade consideram somente lotes com saldo positivo.
              </p>
              <button className="secondary" onClick={() => onNavigate('inventory')}>
                Ver estoque
              </button>
            </article>
            {data.financial && (user.role === 'admin' || user.role === 'reception') && (
              <article
                className="dashboard-card dashboard-card-financial"
                aria-labelledby="dashboard-financial"
              >
                <div className="dashboard-card-heading">
                  <span className="dashboard-kicker">Neste mês</span>
                  <h3 id="dashboard-financial">Financeiro do mês</h3>
                </div>
                <p className="muted">
                  {dashboardDate(data.month_start)} a {dashboardDate(data.month_end)}
                </p>
                <dl>
                  <div className="dashboard-metric">
                    <dt>Recebimentos vigentes</dt>
                    <dd>{financialMoney(data.financial.income_cents)}</dd>
                  </div>
                  {user.role === 'admin' &&
                    data.financial.expense_cents !== null &&
                    data.financial.difference_cents !== null && (
                      <>
                        <div>
                          <dt>Despesas vigentes</dt>
                          <dd>{financialMoney(data.financial.expense_cents)}</dd>
                        </div>
                        <div>
                          <dt>Diferença do mês</dt>
                          <dd>{financialMoney(data.financial.difference_cents)}</dd>
                        </div>
                      </>
                    )}
                </dl>
                <p className="muted">
                  Exclui estornados. A diferença não representa lucro contábil nem saldo bancário.
                </p>
                <button className="secondary" onClick={() => onNavigate('financial')}>
                  Ver financeiro
                </button>
              </article>
            )}
          </div>
        </>
      )}
    </section>
  );
}
