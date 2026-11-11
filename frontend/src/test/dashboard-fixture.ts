import type { Role } from '../api';
import type { DashboardData } from '../dashboard-api';

export function dashboardFixture(role: Role = 'admin'): DashboardData {
  return {
    generated_at: '2026-11-11T15:00:00Z',
    day: '2026-11-11',
    month_start: '2026-11-01',
    month_end: '2026-11-30',
    timezone: 'America/Fortaleza',
    scheduling: {
      appointments_total: 12,
      scheduled: 3,
      confirmed: 2,
      in_progress: 1,
      completed: 4,
      cancelled: 1,
      no_show: 1,
      open_encounters: 2,
    },
    messaging: { needs_attention: 7, simulated: true },
    inventory: { low_stock_products: 2, expired_lots: 1, expiring_lots: 3 },
    financial:
      role === 'admin'
        ? { income_cents: '12345', expense_cents: '2500', difference_cents: '9845' }
        : role === 'reception'
          ? { income_cents: '12345', expense_cents: null, difference_cents: null }
          : null,
  };
}
