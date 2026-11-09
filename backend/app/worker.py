"""Processo que envia os lembretes vencidos, uma clínica por vez.

Uso: python -m app.worker (no Docker, serviço `worker`). Provedor simulado (MOCK).
"""

import logging
import os
import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text

from app.core.db import Database, set_context, verify_runtime_role
from app.core.repositories import ClinicContext
from app.modules.messaging.schemas import DispatchResult
from app.modules.messaging.services import MessagingService

# O mapeamento precisa de todos os modelos referenciados pelas chaves estrangeiras.
from app.modules.records import models as _record_models  # noqa: F401
from app.providers.messaging import MessagingProvider, MockMessagingProvider

INTERVAL_SECONDS = 60
logger = logging.getLogger("app.worker")


def run_once(
    database: Database, provider: MessagingProvider, now: datetime | None = None
) -> DispatchResult:
    now = now or datetime.now(UTC)
    with database.sessions.begin() as session:
        verify_runtime_role(session)
        rows: list[object] = list(
            session.execute(
                text("SELECT vetsys.clinics_with_due_reminders(:at)"), {"at": now}
            ).scalars()
        )
        clinics = [UUID(str(value)) for value in rows]
    total = DispatchResult(sent=0, skipped=0, failed=0)
    for clinic_id in clinics:
        # Uma transação por clínica: falha numa clínica não impede as outras.
        try:
            with database.sessions.begin() as session:
                set_context(session, "vetsys.clinic_id", str(clinic_id))
                set_context(session, "vetsys.role", "system")
                set_context(session, "vetsys.user_id", "")
                result = MessagingService.for_clinic(
                    session, ClinicContext(clinic_id), provider
                ).dispatch_due(now)
        except Exception:
            logger.exception("Falha ao processar lembretes de uma clínica")
            continue
        total = DispatchResult(
            sent=total.sent + result.sent,
            skipped=total.skipped + result.skipped,
            failed=total.failed + result.failed,
        )
    return total


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("Configure DATABASE_URL para iniciar o worker.")
    database = Database(url)
    provider = MockMessagingProvider()
    logger.info("Worker de lembretes iniciado com provedor %s", provider.name.upper())
    while True:
        try:
            result = run_once(database, provider)
            if result.sent or result.skipped or result.failed:
                logger.info(
                    "Lembretes: %s enviados, %s ignorados, %s com falha",
                    result.sent,
                    result.skipped,
                    result.failed,
                )
        except Exception:
            logger.exception("Falha no ciclo do worker")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
