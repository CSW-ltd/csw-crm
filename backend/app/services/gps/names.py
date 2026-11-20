"""Mahalla nomi va davlat raqami kalitlari — Windows agentdagi (mfy_qamrov.py) qoidalar bilan aynan bir xil.
O'zgartirilsa agent bilan solishtiruv (qamrov natijasi tayoqcha darajasida) qayta tekshiriladi."""
import re

# Kirill/lotin bir xil ko'rinadigan harflar va o'zbek harflari → oddiy kirill (mahalla nomi uchun)
UZ = str.maketrans({"Ў": "У", "Қ": "К", "Ғ": "Г", "Ҳ": "Х", "Ё": "Е", "Ъ": "", "Ь": "",
                    "O": "О", "A": "А", "E": "Е", "K": "К", "M": "М", "H": "Н", "P": "Р",
                    "C": "С", "T": "Т", "X": "Х", "Y": "У", "B": "В"})

# Davlat raqamidagi harflar: kirill/lotin, ko'rinishi va o'qilishi bo'yicha bir sinfga
PLATE_CLS: dict[str, str] = {}
for _grp, _tok in (("AА", "A"), ("BVВБ", "B"), ("CSСЦ", "C"), ("EЕЭ", "E"), ("HNН", "N"), ("KКҚ", "K"),
                   ("MМ", "M"), ("OОЎ", "O"), ("PRРП", "P"), ("TТ", "T"), ("XХҲ", "X"), ("YUУЙ", "Y"),
                   ("JЖ", "J"), ("GГҒ", "G"), ("DД", "D"), ("LЛ", "L"), ("ZЗ", "Z"), ("FФ", "F"), ("IИ", "I"),
                   ("QҚ", "K"), ("WШ", "W")):
    for _ch in _grp:
        PLATE_CLS.setdefault(_ch, _tok)

NOT_MFY = ("НАРЯ", "ТУНГИ", "ЮРИДИК", "ЗАХИРА", "РЕМОНТ", "ТАМИР", "ШАРТНОМА", "ХИЗМАТ")


def plate_key(s) -> str:
    """«01 001 ААА», «HOWO 01 001 AAA», «002 ЖББ» / «002 JBB» → bir xil kalit (qavs ichidagi izohlar tashlanadi)."""
    s = re.sub(r"\(.*?(\)|$)", " ", str(s or "")).upper()
    return "".join(c if c.isdigit() else PLATE_CLS.get(c, "") for c in s)


def mfy_key(s) -> str:
    """«(1)Тест МФЙ✅», «ТЕСТ МФЙ», «Тест» → «ТЕСТ». Mahalla raqami nomning qismi: «Тест-2» ≠ «Тест-1»."""
    s = re.sub(r"\(.*?(\)|$)", " ", str(s or "")).upper().translate(UZ)  # yopilmagan qavs ham
    m0 = re.search(r"\s(\d{1,2})\s*(?:МФЙ|МФУ|MFY)\b", s) or re.search(r"[А-Я]\s+(\d)\s*$", s)
    s = re.sub(r"\bМФЙ\b|\bМФУ\b|\bMFY\b", " ", s)
    # «Тест-2», «Тест маҳалла-1», «Тест №2», «2-Тест» — raqam mahalla nomining qismi.
    # («Тест МФЙ (134) 473» dagi soni/qavsdagi raqamlar hisobga olinmaydi.)
    m = re.search(r"[-–—№]\s*(\d{1,2})(?!\d)", s) or re.match(r"\s*(\d{1,2})\s*[-–—]", s) or m0
    return re.sub(r"[^А-Я]", "", s) + (str(int(m.group(1))) if m else "")


def is_mfy_name(s) -> bool:
    """«Наряд», «Тунги навбатчи», «Юридик», «Захира», «Таъмир» — mahalla emas."""
    k = mfy_key(s)
    return bool(k) and not k.startswith(NOT_MFY)


def _match_unit(units: dict[int, str], plate: str) -> int | None:
    k = plate_key(plate)
    if not k:
        return None
    hits = [uid for uid, nm in units.items() if k in plate_key(nm)]
    if len(hits) == 1:
        return hits[0]
    exact = [uid for uid in hits if plate_key(units[uid]).endswith(k)]
    if len(exact) == 1:
        return exact[0]
    # harflar xato yozilgan bo'lsa («003 ААА» o'rniga «003 JBA») — raqamlar bo'yicha, faqat yagona bo'lsa
    digits = "".join(re.findall(r"\d+", re.sub(r"\(.*?(\)|$)", " ", str(plate))))
    if len(digits) >= 3 and not hits:
        dh = [uid for uid, nm in units.items() if "".join(re.findall(r"\d+", re.sub(r"\(.*?(\)|$)", " ", nm))) == digits]
        if len(dh) == 1:
            return dh[0]
    return None


def match_unit(units: dict[int, str], plate: str) -> int | None:
    """CRM davlat raqami → GPS obyekti (unit id). Topilmasa yoki bir nechta bo'lsa — None."""
    uid = _match_unit(units, plate)
    if uid is None:
        # «01 004 AAA» — boshida hudud kodi bo'lsa, usiz ham qidiriladi
        m = re.match(r"^\s*\d{2}\s*[/ ]\s*(\d{3}.*)$", str(plate or ""))
        if m:
            uid = _match_unit(units, m.group(1))
    return uid
