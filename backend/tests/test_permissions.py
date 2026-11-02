"""Huquqlar: admin → manager (bo'lim/amal + tumanlar), manager → o'z xodimlari, admin tasdig'i, tuman radiusi, Vaziyat."""
from tests.helpers import assign, fill_act, schedule_driver
from tests.test_customers import _import

ACT = {"containers": 1, "volume_m3": 2, "note": "Olib ketildi"}
NEW_PWD = "Yangi2026x"


async def _events(admin, **params) -> list[dict]:
    return (await admin.get("/api/v1/situation", params=params)).json()["items"]


async def _login_new(client_factory, username: str, temp: str = "Vaqtincha1"):
    c = await client_factory()
    r = await c.post("/api/v1/auth/login", json={"username": username, "password": temp})
    assert r.status_code == 200, r.text
    assert (await c.post("/api/v1/auth/change-password", json={"current_password": temp, "new_password": NEW_PWD})).status_code == 200
    return c


async def _manager_a(world, client_factory, admin, perms: list[str]):
    """Faqat A tumani manageri, berilgan ruxsatlar bilan."""
    r = await admin.post("/api/v1/admin/users", json={"username": "mgr_a", "full_name": "Manager A", "role": "manager",
                                                      "district_ids": [world["districts"]["a"]], "password": "Vaqtincha1"})
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    base = r.json()["permissions"]
    r = await admin.put(f"/api/v1/admin/users/{uid}/access", json={"permissions": sorted(set(base) | set(perms))})
    assert r.status_code == 200, r.text
    return uid, await _login_new(client_factory, "mgr_a")


async def test_me_has_permissions_and_scope(world, client_factory):
    admin, mgr, gps = await client_factory("admin"), await client_factory("manager"), await client_factory("gps")
    me = (await admin.get("/api/v1/auth/me")).json()
    assert "staff.permissions" in me["permissions"] and me["district_ids"] == []
    me = (await mgr.get("/api/v1/auth/me")).json()
    assert me["permissions"] == sorted(["accounting.view", "orders.view", "orders.unlock", "customers.view", "customers.location_confirm", "staff.view", "vehicles.view", "settings.view", "settings.tariff",
                                        "requests.view", "stats.view"])
    assert me["district_ids"] == sorted(world["districts"].values())
    assert (await gps.get("/api/v1/auth/me")).json()["district_ids"] == [world["districts"]["a"]]


async def test_default_manager_is_read_only_and_sees_own_situation(world, client_factory):
    mgr = await client_factory("manager")
    assert (await mgr.get("/api/v1/admin/users")).status_code == 200
    assert (await mgr.post("/api/v1/admin/users", json={"username": "x1", "full_name": "Xx", "role": "gps",
                                                        "district_id": world["districts"]["a"], "password": "Vaqtincha1"})).status_code == 403
    assert (await mgr.patch(f"/api/v1/admin/vehicles/{world['vehicles']['v1']}", json={"model": "X"})).status_code == 403
    assert (await mgr.put("/api/v1/admin/settings", json={"gps_radius_m": 200})).status_code == 403
    assert (await mgr.patch(f"/api/v1/admin/districts/{world['districts']['a']}", json={"is_active": False})).status_code == 403
    # PR #20: manager Vaziyat panelini ko'radi — faqat o'z tumanlari
    r = await mgr.get("/api/v1/situation")
    assert r.status_code == 200


async def test_admin_grants_and_manager_scope(world, client_factory):
    admin = await client_factory("admin")
    uid, mgr = await _manager_a(world, client_factory, admin, ["staff.edit", "vehicles.edit"])
    ev = (await _events(admin, kind="access_changed"))[0]
    assert "staff.edit" in ev["params"]["added"] and ev["ref_id"] == uid
    # Faqat A tumanining o'z xodimlari: gps, driver, driver2 (yurist A+B — to'liq doirada emas)
    names = {u["username"] for u in (await mgr.get("/api/v1/admin/users")).json()}
    assert names == {"gps", "driver", "driver2"}
    assert [d["id"] for d in (await mgr.get("/api/v1/admin/districts")).json()] == [world["districts"]["a"]]
    assert {v["id"] for v in (await mgr.get("/api/v1/admin/vehicles")).json()} == {world["vehicles"]["v1"], world["vehicles"]["v2"]}
    # O'z xodimini tahrirlash → admin xabar topadi (eski → yangi)
    r = await mgr.patch(f"/api/v1/admin/users/{world['users']['driver']}", json={"phone": "+998 90 111-22-33"})
    assert r.status_code == 200, r.text
    ev = (await _events(admin, kind="staff_updated"))[0]
    assert "telefon: — → +998 90 111-22-33" in ev["params"]["changes"] and ev["actor_name"] == "Manager A"
    # Boshqa tuman xodimi va mashinasi — yo'q
    assert (await mgr.patch(f"/api/v1/admin/users/{world['users']['driver_b']}", json={"phone": "1"})).status_code == 403
    assert (await mgr.patch(f"/api/v1/admin/vehicles/{world['vehicles']['vb']}", json={"model": "X"})).status_code == 403
    # Faolsizlantirish ruxsati berilmagan
    assert (await mgr.patch(f"/api/v1/admin/users/{world['users']['driver2']}", json={"is_active": False})).status_code == 403
    # Mashina tahriri → hodisa
    assert (await mgr.patch(f"/api/v1/admin/vehicles/{world['vehicles']['v1']}", json={"model": "ISUZU ELF"})).status_code == 200
    assert "model: — → ISUZU ELF" in (await _events(admin, kind="vehicle_updated"))[0]["params"]["changes"]


async def test_manager_cannot_grant_what_it_lacks(world, client_factory):
    admin = await client_factory("admin")
    _, mgr = await _manager_a(world, client_factory, admin, ["staff.permissions", "customers.edit"])
    gps_id = world["users"]["gps"]
    acc = (await mgr.get(f"/api/v1/admin/users/{gps_id}/access")).json()
    assert "customers.edit" in acc["grantable"] and "vehicles.create" not in acc["grantable"]
    r = await mgr.put(f"/api/v1/admin/users/{gps_id}/access", json={"permissions": acc["permissions"] + ["customers.edit"]})
    assert r.status_code == 200 and "customers.edit" in r.json()["permissions"]
    r = await mgr.put(f"/api/v1/admin/users/{gps_id}/access", json={"permissions": acc["permissions"] + ["vehicles.create"]})
    assert r.status_code == 403
    # Admin yoki boshqa tuman xodimiga tega olmaydi
    assert (await mgr.put(f"/api/v1/admin/users/{world['users']['admin']}/access", json={"permissions": []})).status_code == 403
    assert (await mgr.put(f"/api/v1/admin/users/{world['users']['driver_b']}/access", json={"permissions": []})).status_code == 403
    ev = (await _events(admin, kind="access_changed"))[0]
    assert ev["actor_name"] == "Manager A" and ev["params"]["added"] == "customers.edit"


async def test_staff_created_by_manager_waits_for_admin(world, client_factory):
    admin = await client_factory("admin")
    _, mgr = await _manager_a(world, client_factory, admin, ["staff.create"])
    body = {"username": "gps_new", "full_name": "Yangi GPS", "role": "gps", "district_id": world["districts"]["a"], "password": "Vaqtincha1"}
    r = await mgr.post("/api/v1/admin/users", json=body)
    assert r.status_code == 201 and r.json()["approval_status"] == "pending" and r.json()["is_active"] is False
    uid = r.json()["id"]
    assert (await mgr.post("/api/v1/admin/users", json={**body, "username": "gps_b", "district_id": world["districts"]["b"]})).status_code == 403
    assert (await mgr.post("/api/v1/admin/users", json={**body, "username": "mgr2", "role": "manager", "district_ids": [world["districts"]["a"]]})).status_code == 403
    ev = (await _events(admin, kind="staff_pending"))[0]
    assert ev["ref_id"] == uid and ev["level"] == "warning"
    c = await client_factory()
    r = await c.post("/api/v1/auth/login", json={"username": "gps_new", "password": "Vaqtincha1"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_pending"
    assert (await mgr.post(f"/api/v1/admin/users/{uid}/approve")).status_code == 403  # faqat admin
    r = await admin.post(f"/api/v1/admin/users/{uid}/approve")
    assert r.status_code == 200 and r.json()["is_active"] is True
    assert (await admin.post(f"/api/v1/admin/users/{uid}/approve")).json()["error"]["code"] == "user_not_pending"
    assert (await c.post("/api/v1/auth/login", json={"username": "gps_new", "password": "Vaqtincha1"})).status_code == 200
    assert (await _events(admin, kind="staff_approved"))[0]["ref_id"] == uid
    # Rad etish
    r = await mgr.post("/api/v1/admin/users", json={**body, "username": "gps_rej"})
    rid = r.json()["id"]
    assert (await admin.post(f"/api/v1/admin/users/{rid}/reject")).json()["approval_status"] == "rejected"
    assert (await mgr.patch(f"/api/v1/admin/users/{rid}", json={"is_active": True})).status_code == 403


async def test_district_radius_is_used_for_acts(world, client_factory):
    admin = await client_factory("admin")
    _, mgr = await _manager_a(world, client_factory, admin, ["settings.radius_edit"])
    a, b = world["districts"]["a"], world["districts"]["b"]
    r = await mgr.put(f"/api/v1/admin/districts/{a}/radius", json={"gps_radius_m": 100})
    assert r.status_code == 200 and r.json()["districts"] == [{"id": a, "name": "Asaka tumani", "gps_radius_m": 100, "effective_m": 100, "print_manual_confirm": True}]
    assert (await mgr.put(f"/api/v1/admin/districts/{b}/radius", json={"gps_radius_m": 100})).status_code == 403
    ev = (await _events(admin, kind="district_radius_changed"))[0]
    assert ev["params"] == {"name": "Asaka tumani", "old": 300, "new": 100} and ev["actor_name"] == "Manager A"
    # ~150 m — umumiy 300 m da "done" bo'lardi, tuman radiusi 100 m da "suspect"
    gps, driver = await client_factory("gps"), await client_factory("driver")
    await schedule_driver(gps, driver, world["users"]["driver"], world["vehicles"]["v1"])
    rid = world["requests"][0]
    at = {"lat": 40.64285, "lng": 72.2390}
    await assign(gps, rid, world["vehicles"]["v1"])
    await driver.post(f"/api/v1/driver/requests/{rid}/enroute")
    await fill_act(driver, rid, at)
    body = (await driver.post(f"/api/v1/driver/requests/{rid}/complete", json={**ACT, **at})).json()
    assert body["act"]["radius_m"] == 100 and body["request"]["status"] == "suspect"
    # Umumiy qiymatga qaytarish
    r = await mgr.put(f"/api/v1/admin/districts/{a}/radius", json={"gps_radius_m": None})
    assert r.json()["districts"][0]["effective_m"] == 300


async def test_manager_customer_changes_and_scoped_import(world, client_factory):
    admin = await client_factory("admin")
    _, mgr = await _manager_a(world, client_factory, admin, ["customers.edit", "customers.import"])
    cid = world["customer"].id
    r = await mgr.patch(f"/api/v1/customers/{cid}", json={"director": "Aliyev A."})
    assert r.status_code == 200, r.text
    assert "rahbar: — → Aliyev A." in (await _events(admin, kind="customer_updated"))[0]["params"]["changes"]
    b = (await _import(mgr, dry_run=True)).json()
    assert b["by_district"] == {"Asaka tumani": 3} and any("doirangizda emas" in e["message"] for e in b["errors"])
    legal = await client_factory("legal")  # yurist o'zgarishlari Vaziyatga yozilmaydi (faqat manager)
    await legal.patch(f"/api/v1/customers/{cid}", json={"director": "Boshqa"})
    assert len(await _events(admin, kind="customer_updated")) == 1


async def test_legal_and_operator_get_multiple_districts(world, client_factory):
    admin = await client_factory("admin")
    a, b = world["districts"]["a"], world["districts"]["b"]
    r = await admin.post("/api/v1/admin/users", json={"username": "op1", "full_name": "Operator", "role": "operator",
                                                      "district_ids": [a, b], "password": "Vaqtincha1"})
    assert r.status_code == 201 and r.json()["district_ids"] == [a, b]
    assert r.json()["permissions"] == ["appeals.create", "appeals.view", "customers.view", "orders.view",
                                       "requests.create", "requests.view"]
    uid = r.json()["id"]
    r = await admin.put(f"/api/v1/admin/users/{uid}/access", json={"permissions": ["customers.view"], "district_ids": [b]})
    assert r.json()["district_ids"] == [b]
    assert (await _events(admin, kind="access_changed"))[0]["params"]["districts_removed"] == "Asaka tumani"
    # GPS xodimining tumani kartada o'zgartiriladi, huquqlar oynasida emas
    r = await admin.put(f"/api/v1/admin/users/{world['users']['gps']}/access", json={"permissions": [], "district_ids": [b]})
    assert r.json()["error"]["code"] == "single_district_role"
