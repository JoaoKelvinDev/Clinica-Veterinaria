from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import and_, delete, func, or_
from sqlalchemy.orm import Session

from app.core.repositories import ClinicContext, TenantRepository
from app.modules.quotes.models import Quote, QuoteItem


class QuoteRepository(TenantRepository[Quote]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, Quote)

    def locked(self, quote_id: UUID) -> Quote | None:
        return self.session.scalar(
            self._select()
            .where(Quote.id == quote_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def page(
        self, query: str, status: str | None, today: date, limit: int, offset: int
    ) -> tuple[Sequence[Quote], int]:
        statement = self._select()
        if query:
            statement = statement.where(
                or_(
                    Quote.patient_name.icontains(query, autoescape=True),
                    Quote.tutor_name.icontains(query, autoescape=True),
                )
            )
        expired = and_(Quote.status == "sent", Quote.valid_until < today)
        if status == "expired":
            statement = statement.where(expired)
        elif status == "sent":
            statement = statement.where(
                Quote.status == "sent", or_(Quote.valid_until.is_(None), Quote.valid_until >= today)
            )
        elif status:
            statement = statement.where(Quote.status == status)
        count = self.session.scalar(statement.with_only_columns(func.count()).order_by(None)) or 0
        items = self.session.scalars(
            statement.order_by(Quote.created_at.desc(), Quote.id).limit(limit).offset(offset)
        ).all()
        return items, count


class QuoteItemRepository(TenantRepository[QuoteItem]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, QuoteItem)

    def for_quote(self, quote_id: UUID) -> Sequence[QuoteItem]:
        return self.session.scalars(
            self._select().where(QuoteItem.quote_id == quote_id).order_by(QuoteItem.position)
        ).all()

    def replace(self, quote_id: UUID, items: Sequence[QuoteItem]) -> None:
        self.session.execute(
            delete(QuoteItem).where(
                QuoteItem.clinic_id == self.context.clinic_id, QuoteItem.quote_id == quote_id
            )
        )
        self.session.add_all(items)
        self.session.flush()
