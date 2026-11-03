import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest } from './api';
import type { UserProfile } from './api';
import { errorMessage } from './registry-api';
import { displayDateTime } from './scheduling-api';
import {
  intents,
  parseDispatch,
  parseMessage,
  parseOverview,
  reminderKinds,
  reminderStatuses,
} from './messaging-api';
import type { MessageItem, MessagingOverview, ReminderItem } from './messaging-api';

export function Messaging({ token, user }: { token: string; user: UserProfile }) {
  const canAct = user.role === 'admin' || user.role === 'reception';
  const [overview, setOverview] = useState<MessagingOverview | null>(null);
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    let active = true;
    void apiRequest(token, '/messaging')
      .then((body) => {
        const result = parseOverview(body);
        if (active) setOverview(result);
      })
      .catch((reason: unknown) => {
        if (active) setError(errorMessage(reason));
      });
    return () => {
      active = false;
    };
  }, [token, revision]);

  async function run(action: () => Promise<string>) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      setNotice(await action());
      setRevision((current) => current + 1);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  function simulate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    void run(async () => {
      const message = parseMessage(
        await apiRequest(
          token,
          '/messaging/mock-inbound',
          { phone: String(data.get('phone')), body: String(data.get('body')) },
          'POST',
        ),
      );
      form.reset();
      if (message.needs_attention) return 'Resposta registrada em "Precisa de atenção".';
      return `Resposta processada: ${message.intent ? intents[message.intent] : 'registrada'}.`;
    });
  }

  return (
    <section className="panel registry" aria-labelledby="messaging-title">
      <div className="section-heading">
        <div>
          <h2 id="messaging-title">Mensagens</h2>
          <p className="muted">
            Lembretes por WhatsApp para tutores com autorização registrada. Envios entre 8h e 20h,
            sem dados clínicos.
          </p>
        </div>
        {canAct && overview?.simulated && (
          <button
            className="secondary"
            disabled={busy}
            onClick={() => {
              void run(async () => {
                const result = parseDispatch(
                  await apiRequest(token, '/messaging/dispatch-now', {}, 'POST'),
                );
                return `Lembretes vencidos: ${result.sent} enviado(s), ${result.skipped} não enviado(s).`;
              });
            }}
          >
            Enviar lembretes vencidos agora
          </button>
        )}
      </div>
      {overview?.simulated && (
        <p className="confirmation">
          Modo de testes (MOCK): nenhuma mensagem sai deste computador e não há custo. As mensagens
          ficam registradas abaixo como se tivessem sido enviadas.
        </p>
      )}
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
      {!overview ? (
        !error && <p role="status">Carregando mensagens…</p>
      ) : (
        <>
          <h3>Precisa de atenção</h3>
          {overview.attention.length === 0 ? (
            <p>Nenhuma resposta aguardando a equipe.</p>
          ) : (
            <ul className="link-list">
              {overview.attention.map((item) => (
                <li key={item.id}>
                  <MessageLine item={item} />
                  {canAct && (
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => {
                        void run(async () => {
                          await apiRequest(token, `/messages/${item.id}/handled`, {}, 'POST');
                          return 'Mensagem marcada como resolvida.';
                        });
                      }}
                    >
                      Marcar como resolvida
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}

          {canAct && overview.simulated && (
            <form className="registry-form" onSubmit={simulate}>
              <h3>Simular resposta do tutor (MOCK)</h3>
              <p className="muted">
                Respostas reconhecidas: CONFIRMO, CANCELAR e SAIR. As demais vão para "Precisa de
                atenção".
              </p>
              <div className="field-pair">
                <label>
                  Telefone do tutor
                  <input name="phone" type="tel" required placeholder="(86) 99999-0000" />
                </label>
                <label>
                  Resposta
                  <input name="body" required maxLength={1000} placeholder="Confirmo" />
                </label>
              </div>
              <div>
                <button disabled={busy}>Registrar resposta</button>
              </div>
            </form>
          )}

          <h3>Próximos lembretes</h3>
          <ReminderTable items={overview.upcoming} empty="Nenhum lembrete agendado." />

          <h3>Lembretes processados</h3>
          <ReminderTable items={overview.recent_reminders} empty="Nenhum lembrete processado." />

          <h3>Histórico de mensagens</h3>
          {overview.messages.length === 0 ? (
            <p>Nenhuma mensagem ainda.</p>
          ) : (
            <ul className="link-list">
              {overview.messages.map((item) => (
                <li key={item.id}>
                  <MessageLine item={item} />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

function MessageLine({ item }: { item: MessageItem }) {
  const who = item.tutor_name ?? `Telefone ${item.phone} (não cadastrado)`;
  return (
    <div className="record-line">
      <p className="muted">
        {item.direction === 'outbound' ? `Enviada para ${who}` : `Recebida de ${who}`} em{' '}
        {displayDateTime(item.created_at)}
        {item.intent && `: ${intents[item.intent]}`}
      </p>
      <p className="message-body">{item.body}</p>
    </div>
  );
}

function ReminderTable({ items, empty }: { items: ReminderItem[]; empty: string }) {
  if (items.length === 0) return <p>{empty}</p>;
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Envio</th>
            <th>Paciente</th>
            <th>Tipo</th>
            <th>Situação</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{displayDateTime(item.sent_at ?? item.due_at)}</td>
              <td>{item.patient_name}</td>
              <td>
                {reminderKinds[item.kind]}
                <br />
                <span className="muted">evento em {displayDateTime(item.event_at)}</span>
              </td>
              <td>
                {reminderStatuses[item.status]}
                {item.outcome && (
                  <>
                    <br />
                    <span className="muted">{item.outcome}</span>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
