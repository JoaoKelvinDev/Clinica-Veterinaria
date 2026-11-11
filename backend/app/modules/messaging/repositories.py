from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.repositories import ClinicContext, TenantRepository
from app.modules.messaging.models import Message, ReminderJob


class ReminderRepository(TenantRepository[ReminderJob]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, ReminderJob)

    def by_key(self, dedupe_key: str) -> ReminderJob | None:
        return self.session.scalar(self._select().where(ReminderJob.dedupe_key == dedupe_key))

    def pending_for(self, **source: UUID) -> Sequence[ReminderJob]:
        query = self._select().where(ReminderJob.status == "pending")
        for column, value in source.items():
            query = query.where(getattr(ReminderJob, column) == value)
        return self.session.scalars(query).all()

    def due(self, now: datetime, limit: int) -> Sequence[ReminderJob]:
        # SKIP LOCKED: dois workers nunca enviam o mesmo lembrete.
        return self.session.scalars(
            self._select()
            .where(ReminderJob.status == "pending", ReminderJob.due_at <= now)
            .order_by(ReminderJob.due_at, ReminderJob.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()

    def upcoming(self, limit: int) -> Sequence[ReminderJob]:
        return self.session.scalars(
            self._select()
            .where(ReminderJob.status == "pending")
            .order_by(ReminderJob.due_at, ReminderJob.id)
            .limit(limit)
        ).all()

    def recent(self, limit: int) -> Sequence[ReminderJob]:
        return self.session.scalars(
            self._select()
            .where(ReminderJob.status != "pending")
            .order_by(ReminderJob.updated_at.desc(), ReminderJob.id)
            .limit(limit)
        ).all()


class MessageRepository(TenantRepository[Message]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, Message)

    def attention_count(self) -> int:
        return (
            self.session.scalar(
                self._select()
                .where(Message.needs_attention.is_(True), Message.handled_at.is_(None))
                .with_only_columns(func.count())
            )
            or 0
        )

    def by_provider_id(self, provider: str, provider_message_id: str) -> Message | None:
        return self.session.scalar(
            self._select().where(
                Message.provider == provider, Message.provider_message_id == provider_message_id
            )
        )

    def insert_inbound_once(self, message: Message) -> Message | None:
        return self.session.scalar(
            insert(Message)
            .values(
                clinic_id=self.context.clinic_id,
                direction="inbound",
                status="received",
                provider=message.provider,
                provider_message_id=message.provider_message_id,
                phone=message.phone,
                body=message.body,
                tutor_id=message.tutor_id,
                appointment_id=message.appointment_id,
                intent=message.intent,
                needs_attention=message.needs_attention,
            )
            .on_conflict_do_nothing(constraint="uq_message_provider_id")
            .returning(Message)
        )

    def latest_outbound_about_appointment(self, phone: str) -> Sequence[Message]:
        return self.session.scalars(
            self._select()
            .where(
                Message.phone == phone,
                Message.direction == "outbound",
                Message.appointment_id.is_not(None),
            )
            .order_by(Message.created_at.desc(), Message.id)
            .limit(10)
        ).all()

    def recent(self, limit: int) -> Sequence[Message]:
        return self.session.scalars(
            self._select().order_by(Message.created_at.desc(), Message.id).limit(limit)
        ).all()

    def needing_attention(self) -> Sequence[Message]:
        return self.session.scalars(
            self._select()
            .where(Message.needs_attention.is_(True), Message.handled_at.is_(None))
            .order_by(Message.created_at, Message.id)
        ).all()
