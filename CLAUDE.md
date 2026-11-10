# CLAUDE.md — CSW Chiqindi CRM

Bu fayl Claude Code uchun: har sessiya boshida o'qiladi. Repo **ochiq (public)** — bu yerga parol, kalit, IP manzil, haqiqiy korxona/shaxs ma'lumoti yozilmaydi.

## Rollar va muloqot

- Claude — ishlab chiquvchi jamoa; foydalanuvchi — texnik rahbar (tech lead).
- Muloqot **o'zbek tilida (lotin)**.
- **Har o'zgarishdan oldin reja ko'rsatiladi va tasdiq olinadi** («ha», «boshlaymanmi» va h.k.). Tasdiqsiz kod yozilmaydi, commit/push qilinmaydi.
- Noaniq joylar **grill uslubida** so'raladi: qisqa variantli savollar, tavsiya etilgan variant birinchi va «(Tavsiya)» belgisi bilan.
- Har ishdan keyin **«Nimani sinash kerak»** ro'yxati chatda beriladi (raqamlangan, tekshirib bo'ladigan qadamlar).

## Filiallar (2026-11-06 dan) — faqat uchta, PR yo'q

| Filial | Vazifasi | Kim/qachon yangilaydi |
|---|---|---|
| `dev` | kundalik ish, `*.test.csw.uz` | Claude — reja tasdiqlangach, to'g'ridan push |
| `prod` | production, rol portallari `*.csw.uz` | foydalanuvchi «prod'ga chiqar» deganda: `dev` → `prod` **faqat fast-forward** (aynan testda sinalgan commit va rasm) |
| `master` | oxirgi barqaror versiya (tiklash nuqtasi) | foydalanuvchi «barqaror» deganda: `prod` → `master` fast-forward |

- Boshqa filial ochilmaydi. `prod` va `master`ga force-push va o'chirish taqiqlangan (GitHub himoyasi).
- Jiddiy muammo: `prod` `master` holatiga qaytariladi (yangi commit bilan, force-push'siz) → `deploy.sh` bilan qayta chiqariladi; baza kerak bo'lsa `restore.sh`.
- Commit xabarlarida haqiqiy ma'lumot bo'yicha faqat umumiy sonlar (agregat) yoziladi.

## Maxfiylik qoidalari (buzilmaydi)

- Haqiqiy call-center Excel fayli (shaxsiy ma'lumot) va haqiqiy shartnoma namunalari (korxona/shaxs nomlari, STIR, hisob raqamlari) **hech qachon commit qilinmaydi** va repo papkasida saqlanmaydi. Testlar va namunalar — faqat sun'iy ma'lumot (`docs/samples/`).
- Commit xabarlari va hisobotlarda haqiqiy ma'lumot bo'yicha faqat umumiy sonlar (agregat) yoziladi.
- Shartnoma shablonlarida faqat placeholder va demo rekvizitlar.
- Test/demo server (`*.test.csw.uz`) ga haqiqiy ma'lumot yuklanmaydi.
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

- **Migratsiyalar:** `backend/alembic/versions/NNNN_nom.py`, ketma-ket raqam (oxirgisi `0021_appeal_contract`, keyingisi `0022_...`). SQLite uchun `batch_alter_table` ishlatiladi.
- **Huquqlar:** `backend/app/core/permissions.py` — modul/amal katalogi va rol shablonlari (`apply_template`); tekshiruv `actor.can("modul.amal")`, frontendda `useCan`.
- **i18n:** `frontend/src/i18n/messages.ts`, har kalit `[uz, ru, en]`. Yangi kalitlar `"  // backend xato kodlari\n"` markeridan oldinga qo'shiladi.
- **Xatolar:** backend mashina o'qiydigan xato kodlari qaytaradi (masalan `reason_required`), frontend ularni i18n orqali ko'rsatadi.
- **Vaziyat paneli:** muhim hodisalar `situation.add(...)` orqali; yangi tur qo'shilsa `SITUATION_KINDS` (frontend) va `KIND_UZ` (eksport) ham yangilanadi.
- Arxitektura: `api/v1/*` (router) → `services/*` (biznes qoidalar) → `repositories/*` (so'rovlar) → `models`.

## Muhim biznes qoidalari

- Shartnoma holatlari: draft → signed → approved / returned; `deleted` — arxiv (tugallanmagan shartnoma izoh bilan o'chiriladi, raqami bo'shatiladi, `archived_number`da saqlanadi).
- **Korxona = shartnoma kontragenti (qaror 2026-11-10):** korxona alohida yaratilmaydi — shartnoma ustasi STIR bilan boshlanadi (bazada bo'lsa o'sha korxona; amaldagi shartnomasi bo'lsa — qo'shimcha shartnoma taklifi; yo'q bo'lsa — rekvizitlardan yangi korxona, `/contracts/counterparty`). Joylashuv (koordinata, geofence, kadastr) ixtiyoriy, uni GPS oynasi to'ldiradi. Yangi korxona qo'ng'irog'i korxona yaratmaydi — murojaat legal'da «Yangi shartnomaga yo'naltirilgan», shartnoma raqam olganda yopiladi (`appeals.contract_id`).
- `source`: flow / manual / import. Mavjud (manual/import) shartnomada qo'lda narx faqat `customers.existing_price` huquqi bilan va tarifdan farq qilsa — sabab majburiy.
- Hisob-kitob (billing): flow shartnomalar buyurtma varaqasi yopilgan kundagi **tarif** bo'yicha. **Qaror (2026-11-06):** mavjud (manual/import) shartnomalar muddati (`valid_to`) tugaguncha shartnomadagi **eski (qo'lda) narx** bo'yicha hisoblanadi — 3-bosqich PR'ida amalga oshiriladi.

## Infratuzilma (umumiy)

- Prod: UzCloud (Toshkent), domen `csw.uz` (Airnet, 2027-11-09 gacha; DNS'da wildcard `*.csw.uz`, DNS API yo'q → Let's Encrypt faqat HTTP-01, nomlar ro'yxati bilan — `deploy/app/certs.sh`).
- **Portallar (qaror 2026-11-09): har rol o'z subdomenida, bitta ilova.** `csw.uz`/`www` — landing; `admin.csw.uz` — faqat ruxsat etilgan IP'lardan (`admin-allow.conf`, faqat serverda); 1-bosqich: `manager`, `legal`, `account` (buxgalter); keyin: `billing` (yangi rol), `call` (operator), `gps`, `driver`, `hr` (yangi rol); kelajak, alohida tizim: `mine.csw.uz`, `mine.tpp.csw.uz`. Test: `*.test.csw.uz` → csw-test. Backend `ROLE_HOSTS` (`app/core/portals.py`: boshqa rol — `wrong_portal`, ro'yxatda yo'q host — `unknown_portal`; login/refresh/`current_user`/socket tekshiradi), cookie host-only, edge nginx faqat `.env`dagi nomlarni ochadi (qolgani 444 / TLS rad). Yangi portal: `.env` (`PORTAL_HOSTS`, `ROLE_HOSTS`, `CORS_ORIGINS`) + `./certs.sh`.
- Deploy: GitHub Actions `dev` push'ida rasmlarni GHCR'ga chiqaradi (prod'da qayta yig'ilmaydi) (public, tag = commit SHA); serverda qo'lda `deploy/deploy.sh <sha>` — avval test, keyin aynan o'sha rasm prod'ga. Actions'da SSH kalit yo'q.
- 3 server bitta VPC'da: **csw-app** (nginx + api + web, yagona ochiq IP), **csw-db** (MySQL, faqat app tarmog'idan), **csw-test** (ochiq IP'siz; `*.test.csw.uz` csw-app nginx orqali proksi qilinadi; prod bazaga ulana olmaydi). Hammasida Ubuntu 24.04, faqat kalit bilan SSH, ufw, fail2ban, Docker.
- Fayllar: UzCloud S3 (endpoint `s3.uzcstorage.uz`, region `default`). Lokal ishlab chiqishda MinIO (`cgr.dev/chainguard/minio` — `minio/minio` Docker Hub'dan olib tashlangan).
- IP manzillar, kirish buyruqlari va to'lov tafsilotlari — repoda emas, foydalanuvchining shaxsiy hujjatlarida.

## Ish tartibi (2026-11-06 da kelishilgan)

1–4 bajarildi va `dev`da: prod'ga tayyorlik (deploy/, GHCR, `ACTIVE_ROLES`, `app.bootstrap`, health, age zaxira), Render demo olib tashlandi,
billing (mavjud shartnoma eski narxda), demo loginlari (`DEMO_CREDENTIALS`, 7 ta `csw.*`, `seed --reset --yes`).
5. **Portallar (subdomenlar)** — avval shu, keyin **prod'ga chiqish** (`dev` → `prod`) va tuman xodimlariga tarqatish (qaror 2026-11-09). Keyin — OCR, yuz tanish, STIR.

- Keyinroq: bitta STIR ostida bosh korxona guruhlash; xaritadagi takror nuqtalar tekshiruvi; maktab/bog'chalar (hududiy boshqarma orqali); printer agenti; haydovchilar uchun Telegram bot; o'z GPS monitoringi; jismoniy abonentlar; 1C o'rniga o'z buxgalteriyasi; Didox/Soliq e-faktura; qo'shimcha kelishuvlar; edo.ijro.uz muqobili — ichki hujjat aylanishi.
