from collections.abc import Sequence
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import Select, case, func, select, text
from sqlalchemy.orm import Session, aliased

from app.core.repositories import ClinicContext, TenantRepository
from app.modules.billing.models import FinancialEntry
from app.modules.billing.schemas import EntryFilters


class FinancialRepository(TenantRepository[FinancialEntry]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, FinancialEntry)

    def locked(self, entry_id: UUID) -> FinancialEntry | None:
        # O histórico não tem permissão UPDATE, necessária para SELECT FOR UPDATE.
        # A trava transacional serializa estornos sem tornar o original mutável.
        self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"financial:{self.context.clinic_id}:{entry_id}"},
        )
        return self.get(entry_id)

    def reversals(self, ids: Sequence[UUID]) -> dict[UUID, FinancialEntry]:
        rows = self.session.scalars(self._select().where(FinancialEntry.reverses_id.in_(ids)))
        return {row.reverses_id: row for row in rows if row.reverses_id is not None}

    def _filtered(self, filters: EntryFilters) -> Select[FinancialEntry]:
        reversal = aliased(FinancialEntry)
        reversed_entry = (
            select(reversal.id)
            .where(
                reversal.clinic_id == self.context.clinic_id,
                reversal.reverses_id == FinancialEntry.id,
            )
            .exists()
        )
        query = self._select().where(
            FinancialEntry.reverses_id.is_(None),
            FinancialEntry.occurred_on.between(filters.start, filters.end),
        )
        if filters.q:
            # Busca literal: caracteres SQL de padrão não ampliam a pesquisa.
            query = query.where(FinancialEntry.description.icontains(filters.q, autoescape=True))
        if filters.category:
            query = query.where(func.lower(FinancialEntry.category) == filters.category.lower())
        if filters.payment_method:
            query = query.where(FinancialEntry.payment_method == filters.payment_method)
        if filters.kind:
            query = query.where(FinancialEntry.kind == filters.kind)
        if filters.status:
            query = query.where(reversed_entry if filters.status == "reversed" else ~reversed_entry)
        return query

    def list(
        self, filters: EntryFilters, limit: int, offset: int
    ) -> tuple[Sequence[FinancialEntry], int, int, int]:
        query = self._filtered(filters)
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.session.scalars(
            query.order_by(
                FinancialEntry.occurred_on.desc(),
                FinancialEntry.created_at.desc(),
                FinancialEntry.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()
        # Totais efetivos usam todos os resultados filtrados, nunca só a página atual.
        active = self._filtered(filters.model_copy(update={"status": "posted"})).subquery()
        if filters.status == "reversed":
            return rows, total, 0, 0
        income, expense = self.session.execute(
            select(
                func.coalesce(
                    func.sum(case((active.c.kind == "income", active.c.amount_cents), else_=0)), 0
                ),
                func.coalesce(
                    func.sum(case((active.c.kind == "expense", active.c.amount_cents), else_=0)), 0
                ),
            )
        ).one()
        return rows, total, int(cast(Decimal, income)), int(cast(Decimal, expense))
