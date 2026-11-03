"""Vaziyat paneli jurnali: hodisa turi bo'yicha alohida PDF (bitta tur — PDF, hammasi — ZIP ichida turlar bo'yicha PDF'lar)."""
import io
import zipfile
from datetime import timedelta
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.order_form_pdf import _fonts

KIND_UZ = {
    "act_request_created": "Murojaat yaratildi", "act_request_cancelled": "Murojaat bekor qilindi",
    "act_assigned": "Mashina biriktirildi", "act_reassigned": "Qayta biriktirildi", "request_reassigned": "Qayta biriktirildi (ogohlantirish)", "contract_deleted": "Shartnoma o'chirildi", "act_form_printed": "Varaqa chop etildi",
    "act_print_confirmed": "Varaqa printerdan chiqdi", "act_form_closed": "Murojaat varaqa bilan yopildi",
    "act_act_completed": "Dalolatnoma bilan yakunlandi", "act_contract_started": "Shartnoma boshlandi",
    "act_contract_saved": "Shartnoma ma'lumotlari saqlandi", "act_contract_signed": "Shartnoma imzolandi",
    "act_contract_imported": "Mavjud shartnoma kiritildi", "act_contract_import": "Excel'dan shartnomalar kiritildi",
    "act_contract_approved": "Shartnoma tasdiqlandi", "act_contract_returned": "Shartnoma qaytarildi",
    "act_tariff_set": "Ta'rif o'zgardi", "act_tariff_lock": "Ta'rif qulfi", "act_payment": "To'lov kiritildi",
    "act_payment_cancelled": "To'lov bekor qilindi", "act_payment_import": "To'lovlar importi",
    "act_invoices_generated": "Oy yopildi (fakturalar)", "act_invoices_sent": "Fakturalar jo'natildi",
    "request_overdue": "Muddati o'tgan murojaatlar", "act_suspect": "Shubhali dalolatnoma", "order_locked": "Varaqa bloklandi",
    "order_reprint": "Qayta chop etishga ruxsat", "customer_updated": "Korxona o'zgartirildi", "customer_created": "Korxona qo'shildi",
}


def kind_label(kind: str) -> str:
    return KIND_UZ.get(kind, kind)


def render(kind: str, rows: list[tuple], districts: dict[int, str], period: str) -> bytes:
    """rows: (created_at UTC, district_id, actor_name, message, level)."""
    _fonts()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                            title=kind_label(kind))
    st = ParagraphStyle("n", fontName="DejaVu", fontSize=8.5, leading=11)
    h = ParagraphStyle("h", fontName="DejaVu-Bold", fontSize=14, leading=18)
    story = [Paragraph(escape(f"Vaziyat paneli — {kind_label(kind)}"), h),
             Paragraph(escape(f"Davr: {period} · Yozuvlar: {len(rows)}"), st), Spacer(1, 4 * mm)]
    data = [[Paragraph(f"<b>{x}</b>", st) for x in ("№", "Sana, vaqt", "Tuman", "Xodim", "Hodisa")]]
    for i, (at, did, actor, msg, _lvl) in enumerate(rows, start=1):
        local = (at + timedelta(hours=5)).strftime("%d.%m.%Y %H:%M")
        data.append([str(i), local, Paragraph(escape(districts.get(did, "—") if did else "—"), st),
                     Paragraph(escape(actor or "—"), st), Paragraph(escape(msg), st)])
    t = Table(data, colWidths=[10 * mm, 30 * mm, 38 * mm, 45 * mm, 150 * mm], repeatRows=1)
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "DejaVu"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ee")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(t)
    doc.build(story)
    return buf.getvalue()


def bundle(groups: dict[str, list[tuple]], districts: dict[int, str], period: str) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for kind, rows in sorted(groups.items(), key=lambda x: kind_label(x[0])):
            z.writestr(f"{kind}.pdf", render(kind, rows, districts, period))
    return out.getvalue()
