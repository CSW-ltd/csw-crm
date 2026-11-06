# CLAUDE.md — CSW Chiqindi CRM

Bu fayl Claude Code uchun: har sessiya boshida o'qiladi. Repo **ochiq (public)** — bu yerga parol, kalit, IP manzil, haqiqiy korxona/shaxs ma'lumoti yozilmaydi.

## Rollar va muloqot

- Claude — ishlab chiquvchi jamoa; foydalanuvchi — texnik rahbar (tech lead).
- Muloqot **o'zbek tilida (lotin)**.
- **Har o'zgarishdan oldin reja ko'rsatiladi va tasdiq olinadi** («ha», «boshlaymanmi» va h.k.). Tasdiqsiz kod yozilmaydi, commit/push qilinmaydi.
- Noaniq joylar **grill uslubida** so'raladi: qisqa variantli savollar, tavsiya etilgan variant birinchi va «(Tavsiya)» belgisi bilan.
- Har PR'dan keyin **«Nimani sinash kerak»** ro'yxati beriladi — chatda ham, PR tavsifida ham (raqamlangan, tekshirib bo'ladigan qadamlar).
- Ish filiallarda: `feature/...` yoki `fix/...`, PR → `main`. `main`ga to'g'ridan-to'g'ri push qilinmaydi.

## Maxfiylik qoidalari (buzilmaydi)

- Haqiqiy call-center Excel fayli (shaxsiy ma'lumot) va haqiqiy shartnoma namunalari (korxona/shaxs nomlari, STIR, hisob raqamlari) **hech qachon commit qilinmaydi** va repo papkasida saqlanmaydi. Testlar va namunalar — faqat sun'iy ma'lumot (`docs/samples/`).
- PR tavsiflarida haqiqiy ma'lumot bo'yicha faqat umumiy sonlar (agregat) yoziladi.
- Shartnoma shablonlarida faqat placeholder va demo rekvizitlar.
- Test/demo server (test.csw.uz) ga haqiqiy ma'lumot yuklanmaydi.
- Demo parollari faqat test serverning `.env` idagi `DEMO_CREDENTIALS` da — kodda, README'da, i18n'da emas.
- Maxfiy SSH kalit va parollar so'ralmaydi va ulashilmaydi; `.env` commit qilinmaydi.

## Kechiktirilgan ishlar — boshlanmaydi

**OCR, yuz tanish (face recognition) va STIR orqali firma ma'lumotlarini aniqlash** — prod'da proyekt to'liq ishlay boshlagandan keyin (5-bosqichdan so'ng) va foydalanuvchi **«to'liq tugadi»** deganidan keyin boshlanadi. Undan keyin uchalasi ketma-ket bitta reja sifatida bajariladi.

## Stek

| Qism | Texnologiya |
|---|---|
| backend/ | Python 3.12, FastAPI, SQLAlchemy 2 (async) + Alembic, MySQL 8.4 (prod/lokal), SQLite (testlar), python-socketio, pydantic v2, MinIO/S3 |
| frontend/ | React 18 + TypeScript (Vite), MUI v6, Redux Toolkit, Axios, Socket.IO-client |

## Buyruqlar

```bash
# lokal (Docker): mysql, minio, api, web
cp .env.example .env            # bir marta, parollarni almashtiring
docker compose up -d --build
docker compose exec api python -m app.seed   # demo ma'lumot; loginlar/parollar .env DEMO_CREDENTIALS (JSON); --reset --yes — qayta yaratish
docker compose logs api --tail 50
# ilova: http://localhost:8080   API hujjati: http://localhost:8000/docs

# testlar
cd backend && pipenv install --dev && pipenv run pytest     # SQLite'da
cd frontend && yarn && yarn build                           # tsc typecheck + build
```

Muhim: testlar SQLite'da ishlaydi — MySQL'ga xos xatolar ko'rinmaydi. Baza/drayver bilan bog'liq o'zgarishdan keyin lokal Docker (MySQL) da ham login va asosiy sahifalarni tekshiring.

## Kod konvensiyalari

- **Migratsiyalar:** `backend/alembic/versions/NNNN_nom.py`, ketma-ket raqam (oxirgisi `0019_contract_delete_archive`, keyingisi `0020_...`). SQLite uchun `batch_alter_table` ishlatiladi.
- **Huquqlar:** `backend/app/core/permissions.py` — modul/amal katalogi va rol shablonlari (`apply_template`); tekshiruv `actor.can("modul.amal")`, frontendda `useCan`.
- **i18n:** `frontend/src/i18n/messages.ts`, har kalit `[uz, ru, en]`. Yangi kalitlar `"  // backend xato kodlari\n"` markeridan oldinga qo'shiladi.
- **Xatolar:** backend mashina o'qiydigan xato kodlari qaytaradi (masalan `reason_required`), frontend ularni i18n orqali ko'rsatadi.
- **Vaziyat paneli:** muhim hodisalar `situation.add(...)` orqali; yangi tur qo'shilsa `SITUATION_KINDS` (frontend) va `KIND_UZ` (eksport) ham yangilanadi.
- Arxitektura: `api/v1/*` (router) → `services/*` (biznes qoidalar) → `repositories/*` (so'rovlar) → `models`.

## Muhim biznes qoidalari

- Shartnoma holatlari: draft → signed → approved / returned; `deleted` — arxiv (tugallanmagan shartnoma izoh bilan o'chiriladi, raqami bo'shatiladi, `archived_number`da saqlanadi).
- `source`: flow / manual / import. Mavjud (manual/import) shartnomada qo'lda narx faqat `customers.existing_price` huquqi bilan va tarifdan farq qilsa — sabab majburiy.
- Hisob-kitob (billing): flow shartnomalar buyurtma varaqasi yopilgan kundagi **tarif** bo'yicha. **Qaror (2026-11-06):** mavjud (manual/import) shartnomalar muddati (`valid_to`) tugaguncha shartnomadagi **eski (qo'lda) narx** bo'yicha hisoblanadi — 3-bosqich PR'ida amalga oshiriladi.

## Infratuzilma (umumiy)

- Prod: UzCloud (Toshkent), domen `crm.csw.uz` (sotib olinmoqda), test: `test.csw.uz`.
- Deploy: GitHub Actions `main`ga merge'da rasmlarni GHCR'ga chiqaradi (public, tag = commit SHA); serverda qo'lda `deploy/deploy.sh <sha>` — avval test, keyin aynan o'sha rasm prod'ga. Actions'da SSH kalit yo'q.
- 3 server bitta VPC'da: **csw-app** (nginx + api + web, yagona ochiq IP), **csw-db** (MySQL, faqat app tarmog'idan), **csw-test** (ochiq IP'siz; test.csw.uz csw-app nginx orqali proksi qilinadi; prod bazaga ulana olmaydi). Hammasida Ubuntu 24.04, faqat kalit bilan SSH, ufw, fail2ban, Docker.
- Fayllar: UzCloud S3 (endpoint `s3.uzcstorage.uz`, region `default`). Lokal ishlab chiqishda MinIO (`cgr.dev/chainguard/minio` — `minio/minio` Docker Hub'dan olib tashlangan).
- IP manzillar, kirish buyruqlari va to'lov tafsilotlari — repoda emas, foydalanuvchining shaxsiy hujjatlarida.

## Ish tartibi (2026-11-06 da kelishilgan)

1. **Prod'ga tayyorlik PR'i** (`feature/prod-readiness`): `deploy/app`, `deploy/db`, `deploy/test` compose fayllari; GHCR + Actions; `deploy.sh`; `ACTIVE_ROLES` (1-bosqichda faqat admin, manager, legal, buxgalter faol); `python -m app.bootstrap` (YAML'dan boshlang'ich foydalanuvchilar, tasodifiy vaqtinchalik parol); birinchi kirishda parolni majburiy almashtirish; `/api/v1/health`; S3 region sozlamasi; nginx (crm.csw.uz va test.csw.uz → csw-test); `age` bilan shifrlangan tungi zaxira S3 `csw-backups` ga + csw-db'da 7 kunlik lokal nusxa; `restore.sh`; MinIO rasmini digest bo'yicha qotirish.
2. **Render demo'ni to'liq olib tashlash:** `render.yaml`, `Dockerfile.demo`, `docker/demo-start.sh`, `RENDER_EXTERNAL_URL` va boshqa izlar; Render dashboard'dagi servisni foydalanuvchi o'chiradi.
3. **Billing tuzatish:** mavjud shartnomalar eski narxda (yuqoridagi qaror).
4. **Demo loginlari PR'i (faqat test.csw.uz):** har rolga bitta foydalanuvchi (csw.admin, csw.manager, csw.yurist, csw.buxgalter, csw.operator, csw.gps, csw.haydovchi — Asaka); parollar faqat test serverdagi `DEMO_CREDENTIALS` env'dan; umumiy parol koddan va README'dan olib tashlanadi; ro'yxatda yo'q foydalanuvchilar seed'da o'chiriladi.
5. **Prod'ga chiqish** va tuman xodimlariga tarqatish. Keyin — OCR, yuz tanish, STIR.

- Keyinroq: bitta STIR ostida bosh korxona guruhlash; xaritadagi takror nuqtalar tekshiruvi; maktab/bog'chalar (hududiy boshqarma orqali); printer agenti; haydovchilar uchun Telegram bot; o'z GPS monitoringi; jismoniy abonentlar; 1C o'rniga o'z buxgalteriyasi; Didox/Soliq e-faktura; qo'shimcha kelishuvlar; edo.ijro.uz muqobili — ichki hujjat aylanishi.
