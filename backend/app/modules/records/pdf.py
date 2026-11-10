"""Renderiza somente os dados conferidos pelo serviço; não abre anexos externos."""

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Protocol
from uuid import UUID
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import reportlab  # type: ignore[import-untyped]
from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_LEFT  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from app.core.errors import InvalidData
from app.modules.records.export_schemas import ExportSnapshot
from app.modules.records.schemas import DocumentRead, RecordEntryRead, VaccineRead, WeightRead

FONT = "VetsysVera"
for font, file in ((FONT, "Vera.ttf"), (f"{FONT}-Bold", "VeraBd.ttf")):
    pdfmetrics.registerFont(TTFont(font, str(Path(reportlab.__file__).parent / "fonts" / file)))
pdfmetrics.registerFontFamily(
    FONT, normal=FONT, bold=f"{FONT}-Bold", italic=FONT, boldItalic=f"{FONT}-Bold"
)

NOTICE = "SEM ASSINATURA DIGITAL INCORPORADA - conferir e assinar antes da entrega"
DOCUMENT_KINDS = {
    "lab_report": "Laudo de exame",
    "external_history": "Histórico externo",
    "prescription": "Receita externa",
    "other": "Outro documento",
}
ENTRY_FIELDS = (
    ("complaint", "Relato do responsável / queixa"),
    ("general_state", "Estado geral e parâmetros"),
    ("findings", "Achados"),
    ("presumptive_diagnosis", "Diagnóstico presuntivo"),
    ("conclusive_diagnosis", "Diagnóstico conclusivo"),
    ("procedures", "Procedimentos e evolução"),
    ("prescription", "Prescrição"),
    ("follow_up", "Retorno / orientações"),
    ("follow_up_on", "Data sugerida de retorno"),
)


class Versioned(Protocol):
    id: UUID
    supersedes_id: UUID | None


def replaced_ids(items: Sequence[Versioned]) -> set[UUID]:
    return {item.supersedes_id for item in items if item.supersedes_id is not None}


def formatted(value: object) -> str:
    if value is None or value == "":
        return "Não informado"
    if isinstance(value, datetime):
        return value.astimezone(ZoneInfo("America/Fortaleza")).strftime("%d/%m/%Y às %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def plain(value: object) -> str:
    text = formatted(value).replace("\r\n", "\n").replace("\r", "\n")
    # Não interpretar tags, links, comandos ou caminhos enviados no texto clínico.
    supported = pdfmetrics.getFont(FONT).face.charToGlyph
    text = "".join(
        char if char in "\n\t" or ord(char) in supported else f"[U+{ord(char):04X}]"
        for char in text
    )
    return escape(text).replace("\n", "<br/>").replace("\t", "    ")


class PageNumbers(Canvas):  # type: ignore[misc]
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.saved_pages: list[dict[str, object]] = []

    def showPage(self) -> None:
        self.saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        count = len(self.saved_pages)
        for state in self.saved_pages:
            self.__dict__.update(state)
            self.setFont(FONT, 7)
            self.setFillColor(colors.HexColor("#53616c"))
            self.drawString(
                18 * mm, 15 * mm, "Prontuário - cópia sem assinatura digital incorporada"
            )
            self.drawRightString(192 * mm, 15 * mm, f"Página {self._pageNumber} de {count}")
            super().showPage()
        super().save()


class PdfBuilder:
    def __init__(self) -> None:
        self.story: list[object] = []
        common = {
            "fontName": FONT,
            "fontSize": 9,
            "leading": 13,
            "spaceAfter": 6,
            "alignment": TA_LEFT,
            "splitLongWords": True,
        }
        self.body = ParagraphStyle("body", **common)
        self.small = ParagraphStyle(
            "small", parent=self.body, fontSize=8, leading=11, textColor=colors.HexColor("#53616c")
        )
        self.heading = ParagraphStyle(
            "heading",
            parent=self.body,
            fontName=f"{FONT}-Bold",
            fontSize=13,
            leading=17,
            spaceBefore=12,
            keepWithNext=True,
        )
        self.subheading = ParagraphStyle(
            "subheading", parent=self.heading, fontSize=10, leading=14, spaceBefore=8
        )

    def title(self, text: str) -> None:
        self.story.append(Paragraph(plain(text), self.heading))

    def section(self, text: str) -> None:
        self.story.append(Paragraph(plain(text), self.subheading))

    def text(self, text: object, *, small: bool = False) -> None:
        self.story.append(Paragraph(plain(text), self.small if small else self.body))

    def field(self, label: str, value: object) -> None:
        self.story.append(Paragraph(f"<b>{plain(label)}:</b> {plain(value)}", self.body))

    def author(self, item: RecordEntryRead | VaccineRead | WeightRead | DocumentRead) -> None:
        self.text(
            f"Registrado em {formatted(item.created_at)} por {item.author_name} | "
            f"{getattr(item, 'author_crmv', None) or 'Sem CRMV neste registro'}",
            small=True,
        )
        self.text(f"Identificador: {item.id}", small=True)
        if item.supersedes_id:
            self.field("Corrige o registro", item.supersedes_id)
            self.field("Motivo da correção", item.correction_reason)

    def entry(self, item: RecordEntryRead) -> None:
        self.section(f"Registro clínico - versão {item.version}")
        self.author(item)
        self.field("Local", item.location)
        self.text(f"Atendimento: {item.encounter_id}", small=True)
        for name, label in ENTRY_FIELDS:
            self.field(label, getattr(item, name))

    def weight(self, item: WeightRead) -> None:
        self.section("Peso")
        self.author(item)
        self.field("Peso (kg)", str(Decimal(item.weight_grams) / 1000).replace(".", ","))

    def vaccine(self, item: VaccineRead) -> None:
        self.section(f"Imunização - {item.vaccine_name}")
        self.author(item)
        for name, label in (
            ("batch", "Lote"),
            ("manufacturer", "Fabricante"),
            ("dose", "Dose"),
            ("manufactured_on", "Fabricação"),
            ("expires_on", "Validade"),
            ("next_dose_on", "Próxima dose"),
        ):
            self.field(label, getattr(item, name))

    def document(self, item: DocumentRead) -> None:
        self.section(f"{DOCUMENT_KINDS[item.kind]} - versão {item.version}")
        self.author(item)
        self.field("Origem", item.origin_name)
        self.field("CRMV da origem", item.origin_crmv)
        self.field("Data do documento", item.document_date)
        self.field("Resumo", item.summary)
        self.field("Arquivo original", item.file_name or "SEM ARQUIVO ORIGINAL ANEXADO")
        if item.sha256:
            self.field("SHA-256 do original", item.sha256)
            self.text("O arquivo original acompanha o pacote ZIP, separado deste PDF.", small=True)


def build_pdf(snapshot: ExportSnapshot) -> bytes:
    b = PdfBuilder()
    b.title("Prontuário médico-veterinário")
    b.text(NOTICE)
    b.field("Clínica", snapshot.clinic_name)
    b.field("Exportação", snapshot.export_id)
    b.field("Gerado em", snapshot.generated_at)
    b.text(
        "Horários em America/Fortaleza. Cópia dos registros disponíveis nesta emissão. "
        "Este arquivo não comprova assinatura nem recebimento pelo responsável.",
        small=True,
    )
    b.title("Identificação")
    p = snapshot.patient
    for label, value in (
        ("Paciente", p.name),
        ("Espécie", p.species),
        ("Raça", p.breed),
        ("Sexo", {"male": "Macho", "female": "Fêmea", "unknown": "Não informado"}[p.sex]),
        ("Nascimento", p.birth_date),
        ("Idade estimada cadastrada (meses)", p.estimated_age_months),
        ("Pelagem", p.coat),
        ("Microchip", p.microchip),
        ("Observações cadastrais atuais", p.notes),
        ("Responsável", snapshot.tutor.name),
        ("CPF", snapshot.tutor.document),
        ("Endereço do responsável", snapshot.tutor.address),
    ):
        b.field(label, value)
    b.text(
        "Identificação cadastral conferida na emissão; "
        "não reconstrói alterações cadastrais anteriores.",
        small=True,
    )
    b.section("Veterinário responsável pela preparação da cópia")
    for label, value in (
        ("Nome", snapshot.author_name),
        ("CRMV", snapshot.author_crmv),
        ("Endereço profissional", snapshot.emission.professional_address),
        ("Telefone", snapshot.emission.professional_phone),
        ("E-mail", snapshot.emission.professional_email),
    ):
        b.field(label, value)
    if snapshot.emission.establishment_legal_name:
        b.field("Razão social", snapshot.emission.establishment_legal_name)
        b.field("CNPJ", snapshot.emission.establishment_cnpj)
        b.field("Registro do estabelecimento no CRMV", snapshot.emission.establishment_crmv)
    b.text("A preparação desta cópia não altera a autoria dos registros abaixo.", small=True)
    record = snapshot.record
    replaced = {
        "entry": replaced_ids(record.entries),
        "weight": replaced_ids(record.weights),
        "vaccine": replaced_ids(record.vaccines),
        "document": replaced_ids(record.documents),
    }
    b.story.append(PageBreak())
    b.title("Histórico clínico vigente")
    events: list[tuple[datetime, str, object]] = []
    for encounter in record.encounters:
        events.append((encounter.started_at, "encounter", encounter))
    for kind, items in (
        ("entry", record.entries),
        ("weight", record.weights),
        ("vaccine", record.vaccines),
        ("document", record.documents),
    ):
        for item in items:
            if item.id not in replaced[kind]:
                events.append((item.created_at, kind, item))
    from app.modules.records.schemas import TimelineEncounter

    def show(kind: str, item: object) -> None:
        if isinstance(item, TimelineEncounter):
            b.section("Atendimento")
            b.field("Início", item.started_at)
            b.field("Conclusão", item.completed_at or "Em andamento")
            b.field("Veterinário atendente (cadastro atual)", item.veterinarian_name)
            b.text(f"Identificador do atendimento: {item.id}", small=True)
        elif isinstance(item, RecordEntryRead):
            b.entry(item)
        elif isinstance(item, WeightRead):
            b.weight(item)
        elif isinstance(item, VaccineRead):
            b.vaccine(item)
        elif isinstance(item, DocumentRead):
            b.document(item)
        b.story.append(Spacer(1, 3 * mm))

    for _, event_kind, event_item in sorted(events, key=lambda event: (event[0], event[1])):
        show(event_kind, event_item)
    if not events:
        b.text("Nenhum atendimento ou registro clínico disponível nesta emissão.")
    b.story.append(PageBreak())
    b.title("Correções e versões anteriores")
    prior_count = 0
    for kind, items in (
        ("entry", record.entries),
        ("weight", record.weights),
        ("vaccine", record.vaccines),
        ("document", record.documents),
    ):
        for item in items:
            if item.id in replaced[kind]:
                prior_count += 1
                b.text("VERSÃO SUBSTITUÍDA - preservada para rastreabilidade")
                show(kind, item)
    if prior_count == 0:
        b.text("Não há versões substituídas nesta emissão.")
    b.title("Anexos e conferência para entrega")
    b.text(
        f"Documentos registrados: {len(record.documents)}. Com arquivo original: "
        f"{sum(item.file_name is not None for item in record.documents)}. "
        f"Sem arquivo original: {sum(item.file_name is None for item in record.documents)}."
    )
    b.text(
        "O PDF descreve os documentos, mas não incorpora seus arquivos. Para obter os originais "
        "disponíveis, utilize o pacote PDF e anexos. Resumos não substituem laudos ausentes."
    )
    b.text(
        "Conferir a identidade e autorização de quem solicita a cópia e obter comprovante de "
        "recebimento são procedimentos manuais da clínica. O download não registra a entrega."
    )
    b.text("Caracteres sem glifo na fonte são preservados na notação [U+XXXX].", small=True)
    b.story.append(
        KeepTogether(
            [
                Paragraph("Conferência e assinatura manual da cópia", b.subheading),
                Spacer(1, 12 * mm),
                Paragraph("____________________________________________", b.body),
                Paragraph(plain(f"{snapshot.author_name} | {snapshot.author_crmv}"), b.body),
                Paragraph("Assinatura não coletada por este sistema.", b.small),
            ]
        )
    )
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=24 * mm,
        title="Prontuário médico-veterinário - cópia sem assinatura digital",
        author="Sistema Veterinário",
    )
    doc.build(b.story, canvasmaker=PageNumbers)
    content = output.getvalue()
    if len(content) > 10 * 1024 * 1024:
        raise InvalidData(
            "O PDF excede 10 MB. Nenhuma exportação foi registrada; avise o administrador."
        )
    return content
