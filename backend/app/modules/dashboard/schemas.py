from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.modules.billing.schemas import FinancialSummary
from app.modules.inventory.schemas import InventoryAlerts
from app.modules.messaging.schemas import MessagingSummary
from app.modules.scheduling.schemas import ScheduleSummary


class DashboardRead(BaseModel):
    generated_at: datetime
    day: date
    month_start: date
    month_end: date
    timezone: Literal["America/Fortaleza"] = "America/Fortaleza"
    scheduling: ScheduleSummary
    messaging: MessagingSummary
    inventory: InventoryAlerts
    financial: FinancialSummary | None
