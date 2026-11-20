"""Schyot-faktura PDF: rekvizitlar, qatorlar jadvali, jami, "shu jumladan QQS", summa so'z bilan, imzolar."""
import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.order_form_pdf import _fonts

ONES = ["", "bir", "ikki", "uch", "to'rt", "besh", "olti", "yetti", "sakkiz", "to'qqiz"]
TENS = ["", "o'n", "yigirma", "o'ttiz", "qirq", "ellik", "oltmish", "yetmish", "sakson", "to'qson"]
SCALES = [(10**9, "milliard"), (10**6, "million"), (1000, "ming")]


def _hundreds(n: int) -> str:
    parts = []
    if n >= 100:
        parts += [ONES[n // 100], "yuz"]
        n %= 100
    if n >= 10:
        parts.append(TENS[n // 10])
        n %= 10
    if n:
        parts.append(ONES[n])
    return " ".join(p for p in parts if p)


def words_uz(n: int) -> str:
    """1 250 000 → "bir million ikki yuz ellik ming"."""
    if n == 0:
        return "nol"
    parts = []
    for size, name in SCALES:
        if n >= size:
            parts += [_hundreds(n // size), name]
            n %= size
    if n:
        parts.append(_hundreds(n))
    return " ".join(p for p in parts if p)


def _q(v) -> str:
    d = Decimal(str(v or 0))
    return f"{d.normalize():f}" if d == d.to_integral() else f"{d:.2f}".rstrip("0")


def _m(v) -> str:
    d = Decimal(str(v or 0))
    return f"{d:,.2f}".replace(",", " ")


def render(inv, cust, prov) -> bytes:
    _fonts()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"Schyot-faktura {inv.number or 'QORALAMA'}")
    st = ParagraphStyle("n", fontName="DejaVu", fontSize=9, leading=12)
    b = ParagraphStyle("b", parent=st, fontName="DejaVu-Bold")
    h = ParagraphStyle("h", parent=b, fontSize=14, leading=18, alignment=1)
    # Qoralamada raqam yo'q — raqam faqat yuborishda beriladi
    story = [Paragraph(f"SCHYOT-FAKTURA № {inv.number}" if inv.number else "SCHYOT-FAKTURA — QORALAMA (raqam yuborishda beriladi)", h),
             Paragraph(f"Davr: {inv.period.strftime('%m.%Y')} · Sana: {(inv.sent_at or inv.created_at).strftime('%d.%m.%Y')}",
                       ParagraphStyle("c", parent=st, alignment=1)), Spacer(1, 6 * mm)]
    p = prov
    seller = [f"<b>Yetkazib beruvchi:</b> {(p.full_name or p.name) if p else '—'}", f"STIR: {p.inn or '—'}" if p else "",
              f"Manzil: {p.address or '—'}" if p else "", f"Bank: {p.bank or '—'}, MFO {p.mfo or '—'}" if p else "",
              f"H/r: {p.account or '—'}" if p else ""]
    buyer = [f"<b>Sotib oluvchi:</b> {cust.name}", f"Maxsus raqam: {cust.code or '—'}", f"STIR: {cust.stir or '—'}",
             f"Manzil: {cust.address or '—'}", f"Telefon: {cust.phone or '—'}"]
    story.append(Table([[Paragraph("<br/>".join(x for x in seller if x), st), Paragraph("<br/>".join(buyer), st)]],
                       colWidths=[90 * mm, 90 * mm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                                                       ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                                                                       ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
                                                                       ("PADDING", (0, 0), (-1, -1), 6)])))
    story.append(Spacer(1, 5 * mm))
    hs = ParagraphStyle("hs", parent=b, fontSize=8.5, leading=10)
    head = [Paragraph(x, hs) for x in ("№", "Sana", "Xizmat", "Miqdor", "Birlik", "Narx (QQS bilan)", "Summa")]
    rows, n = [head], 0
    main = [x for x in inv.lines if x.kind != "annex"]
    annex = [x for x in inv.lines if x.kind == "annex"]
    for x in main:
        n += 1
        rows.append([str(n), x.day.strftime("%d.%m"), Paragraph(x.description, st), _q(x.qty), x.unit, _m(x.price), _m(x.amount)])
    vat = Decimal(str(inv.vat))
    rows += [["", "", Paragraph("<b>Jami</b>", st), "", "", "", _m(inv.total)],
             ["", "", Paragraph(f"shu jumladan QQS 12%", st), "", "", "", _m(vat)]]
    t = Table(rows, colWidths=[8 * mm, 14 * mm, 68 * mm, 20 * mm, 14 * mm, 28 * mm, 28 * mm], repeatRows=1)
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "DejaVu"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                           ("FONTNAME", (0, 0), (-1, 0), "DejaVu-Bold"), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ee")),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("FONTNAME", (-1, -2), (-1, -2), "DejaVu-Bold")]))
    story += [t, Spacer(1, 3 * mm),
              Paragraph(f"<b>To'lanadigan summa:</b> {_m(inv.total)} so'm ({words_uz(int(Decimal(str(inv.total))))} so'm "
                        f"{int((Decimal(str(inv.total)) % 1) * 100):02d} tiyin), shu jumladan QQS {_m(vat)} so'm.", st)]
    if annex:
        story += [Spacer(1, 5 * mm), Paragraph("<b>Ilova: oy davomida bajarilgan buyurtma varaqalari (abonent shartnomasi bo'yicha)</b>", st)]
        ar = [["№", "Sana", "Murojaat / varaqa", "Kub"]] + [[str(i + 1), x.day.strftime("%d.%m"), Paragraph(x.description, st),
                                                             f"{_q(x.qty)} m³"] for i, x in enumerate(annex)]
        at = Table(ar, colWidths=[8 * mm, 16 * mm, 130 * mm, 26 * mm])
        at.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "DejaVu"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                                ("FONTNAME", (0, 0), (-1, 0), "DejaVu-Bold"), ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                                ("ALIGN", (-1, 1), (-1, -1), "RIGHT")]))
        story.append(at)
    story += [Spacer(1, 12 * mm),
              Table([[f"Rahbar: ____________ {p.director or '' if p else ''}", f"Bosh buxgalter: ____________ {p.chief_accountant or '' if p else ''}"],
                     ["M.O'.", ""]], colWidths=[90 * mm, 90 * mm],
                    style=TableStyle([("FONTNAME", (0, 0), (-1, -1), "DejaVu"), ("FONTSIZE", (0, 0), (-1, -1), 9)]))]
    doc.build(story)
    return buf.getvalue()
