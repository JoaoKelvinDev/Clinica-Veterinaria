"""Planeja lembretes quando a agenda, a vacina ou o retorno mudam.

Não importa a agenda nem o prontuário: recebe só identificadores e datas, para que esses
módulos possam chamá-lo sem dependência circular.
"""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.repositories import ClinicContext
from app.modules.messaging.models import ReminderJob, ReminderKind, ReminderStatus
from app.modules.messaging.repositories import ReminderRepository

TIMEZONE = ZoneInfo("America/Fortaleza")
WINDOW_START = time(8)
WINDOW_END = time(20)
CONFIRMATION_BEFORE = timedelta(hours=24)
REMINDER_BEFORE = timedelta(hours=2)
VACCINE_DAYS_BEFORE = 7
FOLLOW_UP_DAYS_BEFORE = 2
NOTICE_TIME = time(9)


def within_window(moment: datetime) -> datetime:
    """Leva o horário para dentro de 8h–20h de Fortaleza, sem antecipá-lo."""
    local = moment.astimezone(TIMEZONE)
    if local.time() < WINDOW_START:
        local = datetime.combine(local.date(), WINDOW_START, TIMEZONE)
    elif local.time() >= WINDOW_END:
        local = datetime.combine(local.date() + timedelta(days=1), WINDOW_START, TIMEZONE)
    return local.astimezone(UTC)


def day_notice(event_day: date, days_before: int, now: datetime) -> datetime:
    target = datetime.combine(event_day - timedelta(days=days_before), NOTICE_TIME, TIMEZONE)
    return within_window(max(target.astimezone(UTC), now))


class ReminderPlanner:
    @classmethod
    def for_clinic(cls, session: Session, context: ClinicContext) -> "ReminderPlanner":
        return cls(ReminderRepository(session, context))

    def __init__(self, reminders: ReminderRepository, clock: type[datetime] = datetime) -> None:
        self.reminders = reminders
        self.clock = clock

    def _now(self) -> datetime:
        return self.clock.now(UTC)

    def _plan(
        self,
        kind: ReminderKind,
        patient_id: UUID,
        source: dict[str, UUID],
        event_at: datetime,
        due_at: datetime,
    ) -> ReminderJob:
        source_id = next(iter(source.values()))
        key = f"{kind.value}:{source_id}:{event_at.astimezone(UTC).isoformat()}"
        # Um lembrete que cairia depois do próprio evento não é enviado, mas fica visível.
        status, outcome = ReminderStatus.PENDING, None
        if due_at >= event_at:
            status, outcome = ReminderStatus.SKIPPED, "Sem horário permitido antes do evento."
        existing = self.reminders.by_key(key)
        if existing is not None:
            if existing.status == ReminderStatus.CANCELLED:
                existing.status, existing.outcome, existing.due_at = status, outcome, due_at
                self.reminders.save(existing)
            return existing
        job = ReminderJob(
            clinic_id=self.reminders.context.clinic_id,
            kind=kind.value,
            status=status.value,
            outcome=outcome,
            dedupe_key=key,
            due_at=due_at,
            event_at=event_at,
            patient_id=patient_id,
            **source,
        )
        self.reminders.save(job)
        return job

    def cancel(self, reason: str, **source: UUID) -> None:
        for job in self.reminders.pending_for(**source):
            job.status, job.outcome = ReminderStatus.CANCELLED.value, reason
            self.reminders.save(job)

    def appointment_booked(
        self, appointment_id: UUID, patient_id: UUID, starts_at: datetime
    ) -> None:
        self.cancel("Consulta reagendada.", appointment_id=appointment_id)
        now = self._now()
        if starts_at <= now:
            return
        due = within_window(max(starts_at - CONFIRMATION_BEFORE, now))
        self._plan(
            ReminderKind.APPOINTMENT_CONFIRMATION,
            patient_id,
            {"appointment_id": appointment_id},
            starts_at,
            due,
        )

    def appointment_confirmed(
        self, appointment_id: UUID, patient_id: UUID, starts_at: datetime
    ) -> None:
        self.cancel("Consulta já confirmada.", appointment_id=appointment_id)
        now = self._now()
        if starts_at <= now:
            return
        due = within_window(max(starts_at - REMINDER_BEFORE, now))
        self._plan(
            ReminderKind.APPOINTMENT_REMINDER,
            patient_id,
            {"appointment_id": appointment_id},
            starts_at,
            due,
        )

    def appointment_closed(self, appointment_id: UUID, reason: str) -> None:
        self.cancel(reason, appointment_id=appointment_id)

    def vaccine_recorded(
        self,
        vaccine_id: UUID,
        patient_id: UUID,
        next_dose_on: date | None,
        superseded_id: UUID | None,
    ) -> None:
        if superseded_id is not None:
            self.cancel("Vacina corrigida.", vaccine_record_id=superseded_id)
        now = self._now()
        if next_dose_on is None or next_dose_on < now.astimezone(TIMEZONE).date():
            return
        event = datetime.combine(next_dose_on, NOTICE_TIME, TIMEZONE).astimezone(UTC)
        self._plan(
            ReminderKind.VACCINE,
            patient_id,
            {"vaccine_record_id": vaccine_id},
            event,
            day_notice(next_dose_on, VACCINE_DAYS_BEFORE, now),
        )

    def follow_up_recorded(
        self,
        entry_id: UUID,
        patient_id: UUID,
        follow_up_on: date | None,
        superseded_id: UUID | None,
    ) -> None:
        if superseded_id is not None:
            self.cancel("Registro corrigido.", record_entry_id=superseded_id)
        now = self._now()
        if follow_up_on is None or follow_up_on < now.astimezone(TIMEZONE).date():
            return
        event = datetime.combine(follow_up_on, NOTICE_TIME, TIMEZONE).astimezone(UTC)
        self._plan(
            ReminderKind.FOLLOW_UP,
            patient_id,
            {"record_entry_id": entry_id},
            event,
            day_notice(follow_up_on, FOLLOW_UP_DAYS_BEFORE, now),
        )
