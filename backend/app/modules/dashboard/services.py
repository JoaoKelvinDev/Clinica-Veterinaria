from calendar import monthrange
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.errors import AccessDenied
from app.core.repositories import ClinicContext
from app.modules.billing.services import FinancialService
from app.modules.clinics.models import Role, User
from app.modules.dashboard.schemas import DashboardRead
from app.modules.inventory.services import InventoryService
from app.modules.messaging.services import MessagingService
from app.modules.scheduling.services import SchedulingService
from app.providers.messaging import MessagingProvider

TIMEZONE = ZoneInfo("America/Fortaleza")


class DashboardService:
    @classmethod
    def for_clinic(
        cls, session: Session, context: ClinicContext, provider: MessagingProvider
    ) -> "DashboardService":
        return cls(
            SchedulingService.for_clinic(session, context),
            MessagingService.for_clinic(session, context, provider),
            InventoryService.for_clinic(session, context),
            FinancialService.for_clinic(session, context),
        )

    def __init__(
        self,
        scheduling: SchedulingService,
        messaging: MessagingService,
        inventory: InventoryService,
        financial: FinancialService,
    ) -> None:
        self.scheduling, self.messaging = scheduling, messaging
        self.inventory, self.financial = inventory, financial

    def read(self, actor: User) -> DashboardRead:
        if not actor.active or actor.deleted_at is not None:
            raise AccessDenied("Usuário sem acesso ativo.")
        now = datetime.now(UTC)
        day = now.astimezone(TIMEZONE).date()
        start = day.replace(day=1)
        end = day.replace(day=monthrange(day.year, day.month)[1])
        return DashboardRead(
            generated_at=now,
            day=day,
            month_start=start,
            month_end=end,
            scheduling=self.scheduling.summary(day),
            messaging=self.messaging.summary(actor),
            inventory=self.inventory.alerts(day),
            financial=self.financial.summary(actor, start, end)
            if actor.role in {Role.ADMIN, Role.RECEPTION}
            else None,
        )
