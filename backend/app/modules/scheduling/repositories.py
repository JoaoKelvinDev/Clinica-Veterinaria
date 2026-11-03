from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.repositories import ClinicContext, TenantRepository
from app.modules.scheduling.models import Appointment, Encounter


class AppointmentRepository(TenantRepository[Appointment]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, Appointment)

    def locked(self, entity_id: UUID) -> Appointment | None:
        return self.session.scalar(
            self._select().where(Appointment.id == entity_id).with_for_update()
        )

    def page(
        self, start: datetime, end: datetime, veterinarian_id: UUID | None, limit: int, offset: int
    ) -> tuple[Sequence[Appointment], int]:
        query = self._select().where(Appointment.starts_at < end, Appointment.ends_at > start)
        if veterinarian_id is not None:
            query = query.where(Appointment.veterinarian_id == veterinarian_id)
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        return self.session.scalars(
            query.order_by(Appointment.starts_at, Appointment.id).limit(limit).offset(offset)
        ).all(), total

    def overlaps(self, appointment: Appointment) -> bool:
        with self.session.no_autoflush:
            return (
                self.session.scalar(
                    self._select()
                    .where(
                        Appointment.id != appointment.id,
                        Appointment.veterinarian_id == appointment.veterinarian_id,
                        Appointment.status.not_in(("cancelled", "no_show")),
                        Appointment.starts_at < appointment.ends_at,
                        Appointment.ends_at > appointment.starts_at,
                    )
                    .limit(1)
                )
                is not None
            )


class EncounterRepository(TenantRepository[Encounter]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, Encounter)

    def locked(self, entity_id: UUID) -> Encounter | None:
        return self.session.scalar(
            self._select()
            .where(Encounter.id == entity_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def fresh(self, entity_id: UUID) -> Encounter | None:
        return self.session.scalar(
            self._select()
            .where(Encounter.id == entity_id)
            .execution_options(populate_existing=True)
        )

    def for_patient(self, patient_id: UUID) -> Sequence[Encounter]:
        return self.session.scalars(
            self._select()
            .where(Encounter.patient_id == patient_id)
            .order_by(Encounter.started_at.desc(), Encounter.id)
        ).all()

    def for_appointment(self, appointment_id: UUID) -> Encounter | None:
        return self.session.scalar(self._select().where(Encounter.appointment_id == appointment_id))

    def page(
        self, start: datetime, end: datetime, veterinarian_id: UUID | None, limit: int, offset: int
    ) -> tuple[Sequence[Encounter], int]:
        query = self._select().where(Encounter.started_at >= start, Encounter.started_at < end)
        if veterinarian_id is not None:
            query = query.where(Encounter.veterinarian_id == veterinarian_id)
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        return self.session.scalars(
            query.order_by(Encounter.started_at, Encounter.id).limit(limit).offset(offset)
        ).all(), total
