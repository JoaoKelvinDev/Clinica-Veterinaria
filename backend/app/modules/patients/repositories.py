from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.repositories import ClinicContext, TenantRepository
from app.modules.patients.models import Patient, TutorPatient


class PatientRepository(TenantRepository[Patient]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, Patient)

    def list(self, search: str, limit: int, offset: int) -> tuple[Sequence[Patient], int]:
        query = self._select()
        if search:
            query = query.where(
                or_(
                    Patient.name.icontains(search, autoescape=True),
                    Patient.microchip.icontains(search, autoescape=True),
                )
            )
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        return self.session.scalars(
            query.order_by(Patient.name, Patient.id).limit(limit).offset(offset)
        ).all(), total

    def locked(self, patient_id: UUID) -> Patient | None:
        return self.session.scalar(self._select().where(Patient.id == patient_id).with_for_update())

    def microchip_exists(self, value: str, excluding: UUID) -> bool:
        with self.session.no_autoflush:
            return (
                self.session.scalar(
                    self._select()
                    .where(Patient.microchip == value, Patient.id != excluding)
                    .limit(1)
                )
                is not None
            )


class LinkRepository(TenantRepository[TutorPatient]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, TutorPatient)

    def list(self, patient_id: UUID) -> Sequence[TutorPatient]:
        return self.session.scalars(
            self._select()
            .where(TutorPatient.patient_id == patient_id)
            .order_by(TutorPatient.created_at, TutorPatient.id)
        ).all()

    def pair(self, patient_id: UUID, tutor_id: UUID) -> TutorPatient | None:
        return self.session.scalar(
            self._select(include_archived=True).where(
                TutorPatient.patient_id == patient_id, TutorPatient.tutor_id == tutor_id
            )
        )

    def clear_primary(self, patient_id: UUID) -> None:
        for link in self.list(patient_id):
            link.is_primary = False
        self.session.flush()
