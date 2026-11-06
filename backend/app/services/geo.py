import math

EARTH_RADIUS_M = 6_371_000


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """Ikki nuqta orasidagi masofa (haversine), metrda.

    MySQL'dagi ST_Distance_Sphere bilan bir xil sferik model; Python'da hisoblash
    testlarni bazadan mustaqil qiladi.
    """
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * EARTH_RADIUS_M * math.asin(math.sqrt(h)))


def valid_coords(lat: float, lng: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lng <= 180


# O'zbekiston chegarasi (taxminiy to'rtburchak) — kiritilgan koordinatani tekshirish uchun
UZ_LAT, UZ_LNG = (37.0, 46.0), (55.0, 74.0)


def in_uzbekistan(lat: float, lng: float) -> bool:
    return UZ_LAT[0] <= lat <= UZ_LAT[1] and UZ_LNG[0] <= lng <= UZ_LNG[1]


def coords_error(lat: float | None, lng: float | None) -> str | None:
    """None — to'g'ri. Aks holda xato kodi: required | swapped (kenglik/uzunlik almashgan) | out_of_uz."""
    if lat is None or lng is None:
        return "required"
    if in_uzbekistan(lat, lng):
        return None
    if in_uzbekistan(lng, lat):
        return "swapped"
    return "out_of_uz"
