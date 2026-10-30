import { useEffect, useState } from 'react';

export function HealthStatus() {
  const [status, setStatus] = useState('Verificando conexão…');
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timeout = window.setTimeout(() => controller.abort(), 5000);
    async function checkHealth() {
      try {
        const response = await fetch('/api/health', { signal: controller.signal });
        const body: unknown = await response.json();
        if (
          !response.ok ||
          typeof body !== 'object' ||
          body === null ||
          !('status' in body) ||
          body.status !== 'ok'
        )
          throw new Error();
        if (active) setStatus('Sistema disponível');
      } catch {
        if (active) setStatus('Não foi possível conectar ao sistema');
      } finally {
        window.clearTimeout(timeout);
      }
    }
    void checkHealth();
    return () => {
      active = false;
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, []);
  return (
    <span role="status" className="health-status">
      {status}
    </span>
  );
}
