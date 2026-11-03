"""Envio dos lembretes vencidos e processamento das respostas dos tutores."""

import logging
import re
import unicodedata
from datetime import UTC, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.errors import AccessDenied, InvalidData, ResourceNotFound
from app.core.permissions import require_registry_writer
from app.core.repositories import ClinicContext
from app.modules.clinics.models import User
from app.modules.clinics.repositories import ClinicRepository
from app.modules.clinics.services import ClinicService
from app.modules.messaging.models import Message, ReminderJob, ReminderKind, ReminderStatus
from app.modules.messaging.repositories import MessageRepository, ReminderRepository
from app.modules.messaging.schemas import (
    DispatchResult,
    MessageRead,
    MessagingOverview,
    ReminderRead,
)
from app.modules.scheduling.models import AppointmentStatus
from app.modules.scheduling.services import SchedulingService
from app.modules.tutors.models import Tutor
from app.modules.tutors.schemas import ConsentInput
from app.modules.tutors.services import TutorService, normalize_phone
from app.providers.messaging import MessagingProvider

TIMEZONE = ZoneInfo("America/Fortaleza")
MAX_ATTEMPTS = 3
OPT_OUT_HINT = "Para não receber mais mensagens, responda SAIR."
# Respostas curtas reconhecidas; o resto vai para a equipe ("Precisa de atenção").
INTENTS = {
    "confirm": {"confirmo", "confirmar", "confirmado", "confirma", "sim", "1", "ok"},
    "cancel": {"cancelar", "cancela", "cancelo", "nao", "nao posso", "nao vou", "2"},
    "opt_out": {"sair", "parar", "pare", "stop", "descadastrar"},
}
ACKS = {
    "confirm": "Consulta confirmada. Obrigado!",
    "cancel": "Consulta cancelada. Se quiser remarcar, fale com a clínica.",
    "opt_out": "Pronto: você não receberá mais mensagens da clínica por aqui.",
}

logger = logging.getLogger(__name__)


def classify(body: str) -> str:
    text = unicodedata.normalize("NFKD", body.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = " ".join(text.split())
    for intent, words in INTENTS.items():
        if text in words:
            return intent
    return "unknown"


def first_name(name: str) -> str:
    return name.split()[0] if name.strip() else name


def reminder_text(kind: str, tutor: str, patient: str, clinic: str, event: datetime) -> str:
    local = event.astimezone(TIMEZONE)
    when_day, when_time = local.strftime("%d/%m"), local.strftime("%H:%M")
    hello = f"Olá, {first_name(tutor)}!"
    # Sem conteúdo clínico (AGENTS.md, seção 8.4): nem nome de vacina, nem motivo.
    texts = {
        ReminderKind.APPOINTMENT_CONFIRMATION: (
            f"{hello} A {clinic} tem consulta marcada para {patient} em {when_day} às "
            f"{when_time}. Responda CONFIRMO para confirmar ou CANCELAR se não puder vir."
        ),
        ReminderKind.APPOINTMENT_REMINDER: (
            f"{hello} Lembrete da {clinic}: a consulta de {patient} é em {when_day} às {when_time}."
        ),
        ReminderKind.VACCINE: (
            f"{hello} A {clinic} lembra que o reforço de vacina de {patient} está previsto "
            f"para {local.strftime('%d/%m/%Y')}. Responda esta mensagem para agendar."
        ),
        ReminderKind.FOLLOW_UP: (
            f"{hello} A {clinic} lembra que o retorno de {patient} está previsto para "
            f"{local.strftime('%d/%m/%Y')}. Responda esta mensagem para agendar."
        ),
    }
    return f"{texts[ReminderKind(kind)]} {OPT_OUT_HINT}"


class MessagingService:
    @classmethod
    def for_clinic(
        cls, session: Session, context: ClinicContext, provider: MessagingProvider
    ) -> "MessagingService":
        scheduling = SchedulingService.for_clinic(session, context)
        return cls(
            ReminderRepository(session, context),
            MessageRepository(session, context),
            scheduling,
            TutorService.for_clinic(session, context),
            ClinicService(ClinicRepository(session, context)),
            provider,
        )

    def __init__(
        self,
        reminders: ReminderRepository,
        messages: MessageRepository,
        scheduling: SchedulingService,
        tutors: TutorService,
        clinics: ClinicService,
        provider: MessagingProvider,
    ) -> None:
        self.reminders = reminders
        self.messages = messages
        self.scheduling = scheduling
        self.tutors = tutors
        self.clinics = clinics
        self.provider = provider

    # Envio -----------------------------------------------------------------------------

    def _recipient(self, patient_id: UUID) -> Tutor | None:
        links = self.scheduling.patients.list_tutors(patient_id)
        primary = next((link.tutor for link in links if link.is_primary), None)
        if primary is None or primary.deleted_at is not None:
            return None
        if not primary.whatsapp_opt_in or not primary.phone:
            return None
        return self.tutors.get(primary.id)

    def _still_valid(self, job: ReminderJob, now: datetime) -> str | None:
        """Motivo para não enviar, ou None se o lembrete continua válido."""
        if job.event_at <= now:
            return "O evento já passou."
        if job.appointment_id is None:
            return None
        appointment = self.scheduling.get(job.appointment_id)
        expected = (
            AppointmentStatus.SCHEDULED
            if job.kind == ReminderKind.APPOINTMENT_CONFIRMATION
            else AppointmentStatus.CONFIRMED
        )
        if appointment.status != expected:
            return "A consulta mudou de situação."
        return None

    def dispatch_due(self, now: datetime | None = None, limit: int = 50) -> DispatchResult:
        now = now or datetime.now(UTC)
        sent = skipped = failed = 0
        clinic = self.clinics.current().name
        for job in self.reminders.due(now, limit):
            reason = self._still_valid(job, now)
            try:
                patient = self.scheduling.patients.get(job.patient_id)
            except ResourceNotFound:
                reason = reason or "Paciente arquivado."
            tutor = None if reason else self._recipient(job.patient_id)
            if reason is None and tutor is None:
                reason = "Tutor principal sem autorização de WhatsApp ou sem telefone."
            if reason is not None or tutor is None or tutor.phone is None:
                job.status, job.outcome = ReminderStatus.SKIPPED.value, reason
                self.reminders.save(job)
                skipped += 1
                continue
            body = reminder_text(job.kind, tutor.name, patient.name, clinic, job.event_at)
            job.attempts += 1
            try:
                provider_id = self.provider.send(tutor.phone, body)
            except Exception:
                # Sem dados pessoais no log; o tipo da falha basta para investigar.
                logger.exception("Falha do provedor de mensagens ao enviar lembrete")
                if job.attempts >= MAX_ATTEMPTS:
                    job.status, job.outcome = ReminderStatus.FAILED.value, "Falha no envio."
                    failed += 1
                self.reminders.save(job)
                continue
            self.messages.save(
                Message(
                    clinic_id=self.messages.context.clinic_id,
                    direction="outbound",
                    status="sent",
                    provider=self.provider.name,
                    provider_message_id=provider_id,
                    phone=tutor.phone,
                    body=body,
                    tutor_id=tutor.id,
                    patient_id=job.patient_id,
                    appointment_id=job.appointment_id,
                    reminder_job_id=job.id,
                )
            )
            job.status, job.sent_at, job.outcome = ReminderStatus.SENT.value, now, None
            self.reminders.save(job)
            sent += 1
        return DispatchResult(sent=sent, skipped=skipped, failed=failed)

    def dispatch_now(self, actor: User) -> DispatchResult:
        require_registry_writer(actor)
        if self.provider.name != "mock":
            raise AccessDenied("O envio manual só existe no modo de testes (MOCK).")
        return self.dispatch_due()

    # Respostas -------------------------------------------------------------------------

    def _reply(
        self, phone: str, body: str, tutor: Tutor | None, appointment_id: UUID | None
    ) -> None:
        provider_id = self.provider.send(phone, body)
        self.messages.save(
            Message(
                clinic_id=self.messages.context.clinic_id,
                direction="outbound",
                status="sent",
                provider=self.provider.name,
                provider_message_id=provider_id,
                phone=phone,
                body=body,
                tutor_id=tutor.id if tutor else None,
                appointment_id=appointment_id,
            )
        )

    def _pending_appointment(self, phone: str, now: datetime) -> UUID | None:
        for message in self.messages.latest_outbound_about_appointment(phone):
            assert message.appointment_id is not None
            appointment = self.scheduling.get(message.appointment_id)
            if appointment.status in {"scheduled", "confirmed"} and appointment.starts_at > now:
                return appointment.id
        return None

    def receive(
        self, actor: User, raw_phone: str, body: str, provider_message_id: str | None = None
    ) -> MessageRead:
        """Processa uma resposta do tutor. Repetir o mesmo identificador não tem efeito."""
        require_registry_writer(actor)
        if self.provider.name != "mock":
            raise AccessDenied("A simulação de respostas só existe no modo de testes (MOCK).")
        phone = normalize_phone(raw_phone)
        if phone is None:
            raise InvalidData("Informe o telefone do tutor.")
        provider_message_id = provider_message_id or f"mock-in-{uuid4()}"
        existing = self.messages.by_provider_id(self.provider.name, provider_message_id)
        if existing is not None:
            return self._read(existing)
        now = datetime.now(UTC)
        tutors = [t for t in self.tutors.by_phone(phone) if t.deleted_at is None]
        tutor = tutors[0] if tutors else None
        intent = classify(body)
        appointment_id = self._pending_appointment(phone, now) if tutor else None
        needs_attention = tutor is None or intent == "unknown"
        if intent == "opt_out" and tutors:
            for item in tutors:
                if item.whatsapp_opt_in:
                    self.tutors.consent(actor, item.id, ConsentInput(granted=False))
        elif intent in {"confirm", "cancel"}:
            if appointment_id is None:
                needs_attention = True
            else:
                status = (
                    AppointmentStatus.CONFIRMED
                    if intent == "confirm"
                    else AppointmentStatus.CANCELLED
                )
                self.scheduling.change_status(actor, appointment_id, status)
        inbound = Message(
            clinic_id=self.messages.context.clinic_id,
            direction="inbound",
            status="received",
            provider=self.provider.name,
            provider_message_id=provider_message_id,
            phone=phone,
            body=body,
            tutor_id=tutor.id if tutor else None,
            appointment_id=appointment_id,
            intent=intent,
            needs_attention=needs_attention,
        )
        self.messages.save(inbound)
        if not needs_attention and intent in ACKS:
            self._reply(phone, ACKS[intent], tutor, appointment_id)
        return self._read(inbound)

    def mark_handled(self, actor: User, message_id: UUID) -> MessageRead:
        require_registry_writer(actor)
        message = self.messages.get(message_id)
        if message is None:
            raise ResourceNotFound("Mensagem não encontrada.")
        message.needs_attention, message.handled_at, message.handled_by = (
            False,
            datetime.now(UTC),
            actor.id,
        )
        self.messages.save(message)
        return self._read(message)

    # Consulta --------------------------------------------------------------------------

    def _read(self, message: Message) -> MessageRead:
        tutor = (
            self.tutors.get(message.tutor_id, include_archived=True) if message.tutor_id else None
        )
        return MessageRead(
            id=message.id,
            direction=message.direction,
            status=message.status,
            phone=message.phone,
            body=message.body,
            tutor_id=message.tutor_id,
            tutor_name=tutor.name if tutor else None,
            patient_id=message.patient_id,
            appointment_id=message.appointment_id,
            intent=message.intent,
            needs_attention=message.needs_attention,
            handled_at=message.handled_at,
            created_at=message.created_at,
        )

    def _reminder(self, job: ReminderJob) -> ReminderRead:
        patient = self.scheduling.patients.get(job.patient_id, include_archived=True)
        return ReminderRead(
            id=job.id,
            kind=job.kind,
            status=job.status,
            due_at=job.due_at,
            event_at=job.event_at,
            patient_id=job.patient_id,
            patient_name=patient.name,
            outcome=job.outcome,
            sent_at=job.sent_at,
        )

    def overview(self, actor: User) -> MessagingOverview:
        if not actor.active or actor.deleted_at is not None:
            raise AccessDenied("Usuário sem acesso ativo.")
        return MessagingOverview(
            provider=self.provider.name,
            simulated=self.provider.name == "mock",
            attention=[self._read(m) for m in self.messages.needing_attention()],
            upcoming=[self._reminder(j) for j in self.reminders.upcoming(50)],
            recent_reminders=[self._reminder(j) for j in self.reminders.recent(20)],
            messages=[self._read(m) for m in self.messages.recent(50)],
        )
