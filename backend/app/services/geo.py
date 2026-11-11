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


# --- Geofence: obyekt chegarasi (GPS tasdiqlaydi) ---
# {"type": "circle", "radius": 150}  — markaz korxona nuqtasi (lat/lng)
# {"type": "polygon", "points": [[lat, lng], ...]}  — 3..200 nuqta
GEOFENCE_RADIUS = (10, 3000)


def geofence_error(gf: dict | None) -> str | None:
    """None — to'g'ri (yoki bo'sh). Aks holda xato kodi."""
    if gf is None:
        return None
    if not isinstance(gf, dict):
        return "bad_geofence"
    if gf.get("type") == "circle":
        r = gf.get("radius")
        if not isinstance(r, (int, float)) or not GEOFENCE_RADIUS[0] <= r <= GEOFENCE_RADIUS[1]:
            return "bad_radius"
        return None
    if gf.get("type") == "polygon":
        pts = gf.get("points")
        if not isinstance(pts, list) or not 3 <= len(pts) <= 200:
            return "bad_polygon"
        for p in pts:
            if not (isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(v, (int, float)) for v in p)
                    and in_uzbekistan(p[0], p[1])):
                return "bad_polygon"
        return None
    return "bad_geofence"


def in_polygon(lat: float, lng: float, points: list) -> bool:
    """Nuqta poligon ichidami (ray casting; kichik hududlar uchun tekis yaqinlashuv yetarli)."""
    inside = False
    j = len(points) - 1
    for i in range(len(points)):
        yi, xi = points[i]
        yj, xj = points[j]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def check_visit(cust_lat: float, cust_lng: float, gf: dict | None, lat: float, lng: float, default_radius: int) -> tuple[int, bool, int]:
    """Tashrif nuqtasi geofence ichidami: (masofa markazgacha, ichida, qo'llanilgan radius). Poligon bo'lsa — poligon bo'yicha."""
    dist = distance_m(cust_lat, cust_lng, lat, lng)
    if gf and gf.get("type") == "polygon":
        return dist, in_polygon(lat, lng, gf["points"]), default_radius
    radius = int(gf["radius"]) if gf and gf.get("type") == "circle" else default_radius
    return dist, dist <= radius, radius
