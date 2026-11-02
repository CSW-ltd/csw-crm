# CSW Chiqindi CRM

Yuridik shaxslardan chiqindi olib ketish arizalarini boshqarish tizimi: call-center, yuridik bo'lim, GPS xodimi, haydovchi plansheti va statistika.

Monorepo:

| Papka | Stek |
| --- | --- |
| `backend/` | Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, MySQL 8, JWT (httpOnly cookie), python-socketio, MinIO |
| `frontend/` | React 18 + TypeScript (Vite), Material UI, Redux Toolkit, React-Router, Axios, Socket.IO-client, SweetAlert2 |

## Hozirgi holat — 1-bosqich: haydovchi moduli

- Login + parol (bcrypt, 5 xato urinishdan keyin 15 daqiqaga bloklanadi), access 15 daqiqa / refresh 7 kun.
- **Smena:** GPS xodimi haydovchini o'z tumanidagi bo'sh mashina bilan juftlab smena ochadi; haydovchi mashina rasmi, spidometr va yoqilg'i bilan boshlaydi va yopadi.
- **Avtonaryad:** `BTE-2026-00001` — xizmat ko'rsatuvchi kodi, yil, tartib raqami (har kompaniya alohida).
- **Dalolatnoma (14 maydon):** oldin/keyin rasm (GPS bilan), sana, davlat raqami, haydovchi, avtonaryad, shartnoma, INN — avtomatik; konteyner, hajm, izoh, imzo, yuz rasmi — haydovchi kiritadi. Hammasi serverda tekshiriladi.
- **GPS radiusi** (100–300 m, standart 300): tashqarida yopilgan ariza `suspect` bo'ladi.
- **Bajarib bo'lmadi:** ariza `failed` holatida ochiq qoladi (Manager nazorati).
- **Jonli yangilanish:** `request:updated`, `driver:location` (Socket.IO).
- Internet yo'q bo'lsa yuborish bloklanadi (to'liq oflayn rejim — keyingi bosqich).

## 2-bosqich: korxonalar bazasi va Excel import

- **Korxonalar** (`/admin#customers`): qidiruv (nom kirill/lotin, STIR, telefon), filtrlar, karta, aloqa raqamlari, shartnomalar.
  Ko'rish — admin, manager, yurist, GPS (o'z tumani); tahrirlash va shartnoma — admin, yurist; koordinata tasdig'i — admin, manager.
- **Fayldan import** (`customers.import` ruxsati): call-center jadvali — .xlsx, .xls, .csv (UTF-8 yoki Windows-1251), .docx (jadval), matnli .pdf.
  Skanerlangan PDF uchun OCR keyingi bosqichda. Avval tahlil (bazaga yozilmaydi), keyin import. Viloyat/tuman yozuvlari
  normallashtiriladi, bir korxonaning takror qatorlari birlashadi, barcha telefonlar saqlanadi; qayta import xavfsiz.
  Buyurtmalar tarixi import qilinmaydi. Namunalar (sun'iy ma'lumot): `docs/samples/call-center-namuna.{xlsx,csv,docx,pdf}`.
- **Biriktirish sharti:** korxonada STIR va amaldagi shartnoma bo'lmasa haydovchi biriktirilmaydi (`customer_incomplete`).
- **Koordinata:** importdagi korxonada yo'q → birinchi tashrifda haydovchi dalolatnoma yopgan nuqta olinadi (radius tekshirilmaydi) →
  Manager tasdiqlaydi → keyingi tashriflar shu nuqta bo'yicha tekshiriladi.
- Yangi xizmat turi: **assenizator** (`septic`).

## Vaziyat paneli (admin va manager)

- `/admin#situation` va navbardagi qo'ng'iroqcha: o'qilmagan hodisalar soni, yangi hodisa kelganda popup (Socket.IO `situation:new`).
- Serverda saqlanadigan hodisalar (90 kun): akkaunt bloklandi, shubhali dalolatnoma, bajarib bo'lmadi, koordinata tasdig'i,
  Excel import, xodim/tuman/mashina faolsizlantirildi yoki faollashtirildi, parol tiklandi, GPS radiusi o'zgardi.
- "Shu sessiyadagi xabarlar": ekranda chiqqan barcha popuplar (forma xatolari ham), sahifa yangilanguncha.
- O'qilganlik har bir xodim uchun alohida.

## Jonli demo (Render, bepul)

`render.yaml` + `Dockerfile.demo`: bitta konteynerda frontend va backend, SQLite, fayllar xotirada.
Har push'da avtomatik qayta deploy bo'ladi; har qayta ishga tushishda baza boshlang'ich holatga qaytadi.

1. https://render.com → **GitHub bilan kirish** (karta shart emas)
2. **New → Blueprint** → `uzsaltmine-dev/csw-crm` → **Apply**
3. Havola: `https://csw-crm-demo.onrender.com` (yoki Render bergan nom)

Demo loginlar (parol `demo1234`): GPS xodimi `gps4`, haydovchi `driver41` (ikkalasi Asaka tumani), `admin`, `manager`, yurist `legal`.
Tavsiya: GPS xodimini kompyuterda, haydovchini telefon/planshetda oching.
Demo serverda (`TAB_SESSIONS=true`) bitta brauzerning har tabida boshqa rolda kirish mumkin; tab sarlavhasida rol va ism turadi.
Yangi tab ochib manzilni qo'lda kiriting (tabni "Dublikat" qilsangiz, sessiya ham nusxalanadi). Prod'da bu rejim o'chiq — httpOnly cookie.

Bepul reja cheklovlari: 15 daqiqa kirilmasa uxlaydi, keyingi ochilish ~1 daqiqa.
Namuna korxonalar Asakada joylashgan — boshqa joydan yakunlangan ariza haqli ravishda `Shubhali` (radiusdan tashqarida) bo'ladi.

## Lokal ishga tushirish (Docker)

```bash
cp .env.example .env          # parollarni almashtiring
docker compose up -d --build
docker compose exec api python -m app.seed   # boshlang'ich ma'lumotlar, parol: SEED_PASSWORD yoki ChangeMe123!
```

- Frontend: http://localhost:8080 — haydovchi `driver41` (Asaka tumani), GPS xodimi `gps4`
- API hujjati (Swagger): http://localhost:8000/docs
- MinIO konsoli: http://localhost:9001
- MySQL (DBeaver): `localhost:3306`, `.env` dagi foydalanuvchi

## Docker'siz ishlab chiqish

```bash
# backend
cd backend
pipenv install --dev
export DATABASE_URL=sqlite+aiosqlite:///./dev.db STORAGE_BACKEND=memory   # MySQL/MinIO'siz tezkor variant
pipenv run alembic upgrade head && pipenv run python -m app.seed
pipenv run uvicorn app.main:asgi_app --reload

# frontend (boshqa terminalda) — /api va /socket.io avtomatik :8000 ga proksi qilinadi
cd frontend
yarn && yarn dev              # http://localhost:5173
```

## Testlar

```bash
cd backend && pipenv run pytest      # 19 test: auth, smena qoidalari, avtonaryad, to'liq haydovchi oqimi
cd frontend && yarn build            # tsc typecheck + build
```

## Arxitektura (backend)

```
app/api/v1/*        router (controller) — HTTP, validatsiya, Depends orqali DI
app/services/*      biznes qoidalari (smena, biriktirish, dalolatnoma, avtonaryad)
app/repositories/*  baza so'rovlari
app/models          SQLAlchemy modellari; app/schemas.py — Pydantic sxemalar
app/middleware.py   X-Request-ID + vaqt logi, CSRF sarlavha tekshiruvi
app/realtime.py     Socket.IO xonalari: managers, gps:{tuman}, driver:{id}
```

API'ni Postman bilan sinash: `Authorization: Bearer <token>` sarlavhasi bilan CSRF tekshiruvi talab qilinmaydi; brauzer cookie bilan ishlaganda `X-Requested-With: csw` sarlavhasi shart.

## Prod (VPS) uchun eslatma

- Tashqi Nginx: SSL (Let's Encrypt) va `proxy_pass http://127.0.0.1:8080`; `.env` da `COOKIE_SECURE=true`.
- UFW: faqat 22, 80, 443 ochiq; MySQL, MinIO va API portlari `127.0.0.1` ga bog'langan.
- Planshetda GPS va kamera faqat **HTTPS** orqali ishlaydi.

## Huquqlar (PR #7)

- Ruxsat kodi `<bo'lim>.<amal>`: `customers.*`, `staff.*`, `vehicles.*`, `settings.*` (katalog: `backend/app/core/permissions.py`).
  Admin hammasiga ega; boshqa xodimga yaratilganda rol andozasi yoziladi, keyin "Xodimlar → Huquqlar" oynasida ochiladi/yopiladi.
- Doira: GPS/haydovchi — bitta tuman; manager/yurist/operator — bir nechta tuman. Manager faqat o'z tumanlaridagi
  GPS/yurist/operator/haydovchilarni ko'radi va boshqaradi; faqat o'zida bor ruxsatlarni bera oladi.
- Manager qo'shgan xodim admin tasdiqlamaguncha kira olmaydi ("Vaziyat" yoki "Xodimlar"da "Tasdiqlash").
- GPS radiusi tuman bo'yicha (bo'sh bo'lsa umumiy). Vaziyat paneli — faqat admin; managerning har o'zgarishi u yerga yoziladi.

## Call-center va statistika (PR #9)

- **Operator** (`/operator`): korxonani telefon/nom/STIR bo'yicha topadi → ariza ochadi (xizmat turi, hajm, vaqt, qo'ng'iroq qiluvchi, manba).
  Korxonada ochiq ariza bo'lsa — "Qayta ariza sifatida belgilaymi?" tasdig'i; ariza "qayta" belgisi bilan avvalgisiga bog'lanadi.
  Korxona topilmasa — **birinchi murojaat** yuridik bo'limga; yurist karta (+ shartnoma) ochadi, ariza avtomatik GPS xodimiga o'tadi.
- **72 soat**: har arizada muddat (`due_at`); muddati o'tganlari qizil belgilanadi va admin Vaziyat paneliga bir marta ogohlantirish tushadi.
- **Statistika** (`stats.view`): bugun / oxirgi 5 kun / oxirgi 10 kun / shu oy — tushgan, qayta, kutilmoqda, muddatdan oshgan,
  bajarilgan va bajarilmagan (soni va ulushi). Kartochka bosilsa — tumanlar kesimida diagramma va jadval. Manager — o'z tumanlari.
- Yangi ruxsatlar: `requests.view/create/cancel`, `appeals.view/create/review`, `stats.view`. Demo login: `operator`.
- Ovozli AI assistent bo'yicha kelishuvlar: `docs/plans/voice-ai-assistant.md`.

## Statistika, Arizalar va GPS "Yangilar" (PR #10)

- **Statistika** admin panelida birinchi yorliq. Kartochka (ko'rsatkich) tanlansa to'rtta diagramma faqat shu ko'rsatkich bo'yicha:
  Area (dinamika: bugun — soatlar, boshqa davrlar — kunlar), Pie (tarkib), Histogramma (ochilgandan bajarilguncha soatlar: 0–24, 24–48,
  48–72, 72+), Bar (tumanlar). Har biri "Jadval" ko'rinishiga o'tadi. **Excel / PDF** — tanlangan davr va ko'rsatkich bo'yicha
  (`GET /api/v1/stats/export?period=&metric=&format=xlsx|pdf`; PDF shriftlari: `backend/app/assets/fonts`, DejaVu litsenziyasi).
- **Arizalar** yorlig'i (`requests.view`; manager — o'z tumanlari): holat, tuman, xizmat turi, sana, qayta, muddati o'tgan, qidiruv;
  karta + holatlar tarixi; `requests.cancel` bo'lsa yangi arizani sabab bilan bekor qilish.
- **"Yangi"** — har xodim uchun alohida (`request_seen` jadvali, migratsiya 0008): arizani ochguncha/bosguncha belgilanadi.
  GPS ro'yxati eng yangisi tepada; filtrlar: Yangilar (standart), Bugun, Qayta, Muddati o'tgan, Assenizator, Barchasi.

## Yozishma (PR #11) — olib tashlandi (PR #16)

Ariza/murojaat ichidagi yozishma (matn va ovozli xabar) PR #16 da butunlay olib tashlandi: UI, API, socket, ovoz tozalash.
Migratsiya 0013 `chat_messages`, `chat_reads` jadvallarini va `chat.*` ruxsatlarini o'chiradi (downgrade jadvallarni bo'sh
holda qaytaradi). Keyinchalik boshqa formatda qo'shilishi mumkin.

## Uch bosqichli jarayon va buyurtma varaqasi (PR #12)

Batafsil kelishuvlar: `docs/plans/three-stage-flow.md`.

- 🔴 **Qizil** (GPS): 72 soat teskari timer, rang to'qlashadi, 72 soatdan keyin qora; yangi karta tushganda ovozli alert.
  Mashina dropdowni: bugungi ish jadvalidan, yuridik bo'lim mashinalari yuqorida, korxonagacha masofa bilan.
- 🟡 **Sariq** (GPS, legal, haydovchi): biriktirilganiga N soat; legal va haydovchi uchun ham ovozli alert.
- 🟢 **Yashil**: legal varaqani yopganda yoki haydovchi planshetda dalolatnomani yakunlaganda.
- **Korxona maxsus raqami** (`KTR47`): STIR o'rniga, avtomatik va doimiy. STIR endi takrorlanishi mumkin.
- **Buyurtma varaqasi**: GPS chop etadi (PDF, ikki qism). Maxfiy tasdiq kodi faqat qog'ozda bo'ladi, bazada HMAC xeshi.
  Qayta chop etish manager ruxsati bilan. Kod 3 marta noto'g'ri kiritilsa blok. Yopish uchun skan, kod, kub va tur kerak.
- **Kunlik ish jadvali** smenalar o'rnida. Haydovchi smenasiz ishlaydi.
- **GPS-monitoring uchun API** (`X-Api-Key`, `INTEGRATION_API_KEY`): `POST /api/v1/integrations/vehicle-positions`,
  `GET/PUT /api/v1/integrations/schedule`. Ixtiyoriy sozlama: `ORDER_CODE_SECRET` (bo'sh bo'lsa `JWT_SECRET`'dan olinadi).
- **Yangi ruxsatlar** (migratsiya 0010 mavjud xodimlarga beradi): `orders.view`, `orders.print` (GPS), `orders.close` (legal),
  `orders.unlock` (manager); legal uchun `requests.view`.

## Murojaatlar va operator (PR #13)

- «Ariza» tushunchasi olib tashlandi: hamma joyda **murojaat**, raqamlar `M-000123` (migratsiya 0011 eski `AR-` raqamlarni o'zgartiradi).
- **Admin/manager → Murojaatlar**: barcha murojaatlar o'z rangida (qizil, qora — 72 soatdan o'tgan, sariq, yashil),
  12 / 72 / 144 soatlik 4 ta rangli panel, rang filtri, qidiruv. Manager sariq kartadan qayta chop etishga ruxsat beradi
  va blokni ochadi.
- **Operator**: «Yangi korxona» (telefon, STIR, mashinani kutib oluvchi) — korxona «shartnoma kutilmoqda» holatida ochiladi,
  maxsus raqam SMS bilan yuboriladi (Eskiz.uz: `ESKIZ_EMAIL`, `ESKIZ_PASSWORD`, `SMS_SENDER`; sozlanmasa faqat jurnal).
  Mavjud korxona: telefon, chiqindi turi, kutib oluvchi → «Murojaat yaratish».
- **STIR yana unikal**: band bo'lsa «Siz STIRni xato kiritdingiz — bu STIR «X» korxonasiga tegishli» va shu korxonaga o'tish.
- Shartnomasiz korxonalar murojaatlari GPS'ga ko'rinmaydi. GPS socket xonasi tuman bo'yicha (yangi qizil karta jonli tushadi).
- Sariq kartalarda buyurtma varaqasi raqami ko'rsatilmaydi (faqat qidiruv uchun).

## Korxonalar statistikasi va buxgalteriya (PR #14)

- **Legal → Korxonalar** (faqat statistika): yashil panel — shartnomasi bor korxonalar soni (bosilsa jadvalga o'tadi); jadval:
  nom, maxsus raqam, debitor, kreditor, jami chiqindi (har ustun bo'yicha saralash). Har son bosilsa `/admin/korxona/:id/:view`:
  debitor/kreditor — ikki davrni solishtirish (tayyor davrlar yoki sanalar, oyma-oy diagramma); kub — barcha yashil murojaatlar.
- Tablar qatorining o'ng chetida **«Yangi shartnoma»** (PR #15 da to'liq jarayon: tekshirish, qog'oz shartnoma, buxgalter tasdig'i).
- **Hisob** (vaqtincha tizim ichida, `app/services/billing.py`): har reys — narx × yashil; hajm — narx × kub; oylik — har oy;
  bir martalik — bir marta. Qoldiq = hisoblangan − to'langan (+ debitor, − kreditor).
- **Buxgalter** roli (demo: `buxgalter`): to'lovlar — qo'lda, bekor qilish (o'chirilmaydi), bank ko'chirmasi importi (avval sinov).
  Ruxsatlar: `accounting.view` (legal, manager), `accounting.payments` (buxgalter). Migratsiya 0012.
- Admin «Murojaatlar»: tuman dropdowni 12/72/144 soat bilan birga ishlaydi. GPS'da «Assenizator» filtri olib tashlandi.
  Statistika: kartochkalar → tumanlar jadvali → diagrammalar.

## Admin/manager «Korxonalar» va CMYK ranglar (PR #15)

- **Admin/manager → Korxonalar**: ichki tablar «Statistika» (standart) va «Korxonalar bazasi». O'ng chetda «Fayldan import» va
  yashil «Yangi shartnoma» (oldingi «Yangi korxona»).
- Statistika: tuman dropdowni (barchasi yoki bitta tuman — hamma raqamlarga), 5 panel — oxirgi 7 / 15 / 30 / 182 / 365 kunda
  tuzilgan yangi shartnomalar (imzolangan sana, bo'lmasa kiritilgan), debitor/kreditor jadvali (tuman ustuni bilan).
  «Tumanlar kesimida» jadvali PR #16 da olib tashlandi. API: `GET /api/v1/accounting/new-contracts?district_id=`.
- Karta ranglari CMYK: sariq 0/0/100/0 (`#FFF200`), yashil 100/0/100/0 (`#00A651`, matn oq).

## Buyurtma varaqalari va oylik schyot-faktura (PR #16)

- **Buxgalter → «Buyurtma varaqalari»** (`accounting.payments`): tanlangan oyda yashil bo'lgan har bir varaqa (varaqa yoki akt
  orqali yopilgan). Summa — o'sha sanada amalda bo'lgan shartnoma bo'yicha: kub → narx × m³, reys → reys narxi, oylik → summasiz
  («abonent»). Oy, tuman, korxona filtrlari; korxonalar bo'yicha jami. API: `GET /api/v1/accounting/order-forms?month=&district_id=&customer_id=`.
- **«Schyot-fakturalar»**: «Oyni yopish va schyot-fakturalarni yaratish» — har korxonaga oyiga bitta faktura
  (`SF-YYYY-MM-#####`). Reys/kub — har varaqa alohida qator; oylik shartnoma — bitta qator (oylik summa) + varaqalar summasiz ilova.
  Narxlar QQS bilan, PDF'da «shu jumladan QQS 12%» (`VAT_RATE`, standart 12) va summa so'z bilan.
- «Hammasiga jo'natish» — har korxona telefoniga SMS: summa va PDF havolasi (`/api/v1/public/invoices/{token}`, login'siz,
  32 baytli tasodifiy token, faqat yuborilgan faktura). Havola bazasi: `PUBLIC_BASE_URL` (bo'lmasa `RENDER_EXTERNAL_URL`).
  Yuborilgan faktura qulflanadi: qayta yaratish unga tegmaydi; yuborilmaganlari qayta hisoblanadi (raqam saqlanadi).
- Debitor/kreditor va faktura bitta hisob manbasidan (`billing.Ledger`) foydalanadi.
- **Admin → Sozlamalar → Rekvizitlar**: har viloyat xizmat ko'rsatuvchisining to'liq nomi, STIR, manzil, bank, MFO, hisob raqam,
  rahbar, bosh buxgalter (fakturaga chiqadi). Demo qiymatlar haqiqiy emas. API: `GET/PUT /api/v1/admin/providers`.
- Didox / Soliq e-faktura integratsiyasi keyingi bosqichda (ERI kaliti kerak).

## «Yangi shartnoma» jarayoni (PR #17)

- **Legal → «Yangi shartnoma»** (`customers.contract`) — 3 bosqichli usta:
  1. korxona: mavjudini qidirish (nom, maxsus raqam, STIR) yoki yangisini qo'shish;
  2. rekvizitlar (direktor, yuridik manzil, obyekt manzili, kadastr, bank, MFO, hisob raqam, OKED) va shartlar
     (tur, narx QQS bilan, yillik hajm m³ / yillik reyslar, muddat, tuzilgan joyi, imzo usuli) → «Tekshirish»
     (maydonlar bo'yicha xatolar, ustma-ust faol shartnoma) → jami, QQS 12% (ichida), summa so'z bilan → «Saqlash va raqam olish»;
  3. hujjat: PDF (chop etish) va Word (.docx — Didox / hujjat.uz'ga yuklash) → «Imzolandi — buxgalteriyaga yuborish».
- Ichki raqam viloyat bo'yicha avtomatik: `BTE-2026/00001`, `BTK-2026/00001`. Elektron imzoda platforma (Didox, hujjat.uz,
  my.soliq) va hujjat ID'si majburiy, imzolangan PDF yoki skan ixtiyoriy. Platforma ID bo'lsa fakturada va ro'yxatlarda u ko'rinadi.
- Shablon viloyat bo'yicha: Andijon (`BTE`) — «Ommaviy shartnoma» (hujjat.uz namunasi), Surxondaryo (`BTK`) va boshqalar —
  Didox namunasi. Matn namunalardan olingan; tomonlar, jadval, summa va sanalar formadan qo'yiladi
  (`backend/app/services/contract_templates.py`). Repoda haqiqiy korxona ma'lumotlari yo'q.
- Holatlar: `draft` → `signed` (faol: murojaat ochiladi, GPS ko'radi) → `approved` (buxgalter). Buxgalter izoh bilan qaytarsa —
  `returned` (faol qoladi), legal tuzatib qayta yuboradi. Har qadam tarixda (`contract_events`).
- Hisob-kitob (faktura, debitor) **faqat tasdiqlangan** shartnoma bo'yicha. Tasdiqlanmagan shartnoma varaqalari «Buyurtma
  varaqalari»da «tasdiq kutilmoqda»; «Oyni yopish»da ogohlantirish. Yillik hajmdan foydalanish: 90% va 100% dan oshganda belgi.
- «Shartnomalar» tabi: legal — barcha holatlar (sariq — kutilmoqda, qizil — qaytarilgan, yashil — tasdiqlangan);
  buxgalter — standart «Tasdiq kutilmoqda» navbati, «Tasdiqlash» / «Izoh bilan qaytarish».
- GPS va legal kartalarida 30 kun davomida «Yangi shartnoma» belgisi.
- Admin → Sozlamalar → Rekvizitlar: telefon va OKED qo'shildi (shartnomaga chiqadi).
- API: `POST /api/v1/contracts/check`, `POST /api/v1/contracts`, `PUT/DELETE /api/v1/contracts/{id}`,
  `GET /api/v1/contracts?status=&q=`, `GET /api/v1/contracts/{id}/document?format=pdf|docx`, `POST /api/v1/contracts/{id}/sign`
  (multipart), `GET /api/v1/contracts/{id}/scan`, `POST /api/v1/contracts/{id}/approve`, `POST /api/v1/contracts/{id}/return`.
  Migratsiya 0014. Keyingi: «Qo'shimcha kelishuv», Didox / hujjat.uz integratsiyasi (ERI).

## Varaqa chop tasdig'i, ta'riflar, mavjud shartnomalar (PR #18)

- **Buyurtma varaqasi:** bitta murojaatga bitta raqam (yopilguncha o'zgarmaydi). GPS mashina biriktirgach murojaat `printing`
  holatida — karta **qizil** qoladi («chop etilishi kutilmoqda»), haydovchiga ko'rinmaydi. Chop etilgach «Varaqa printerdan
  chiqdimi?»: «Ha» → sariq (`assigned`), «Yo'q» → o'sha raqam bilan qayta chop etiladi (tasdiqgacha manager ruxsati kerak emas).
  Tasdiqni server printer agentidan qabul qiladi (PR #20); agent o'rnatilguncha tumanda **agentsiz rejim** (standart yoqilgan):
  admin → Sozlamalar → «Varaqa tasdig'i». API: `POST /api/v1/order-forms/{id}/confirm-print`, `PUT /api/v1/admin/districts/{id}/print-mode`.
- **Ta'riflar** (Admin/Manager → «Ta'riflar»): 1 m³ narxi (QQS bilan) viloyat bo'yicha, tuman/shahar uchun alohida; sanadan kuchga
  kiradi, tarix saqlanadi, kelajakdagisini o'chirish mumkin. Manager — o'z tumanlari; admin — hammasi va managerga viloyat yoki
  tuman bo'yicha qulf. Kub bo'yicha hisob (varaqa, faktura, debitor) **varaqa yopilgan kundagi ta'rif** bo'yicha; ta'rif kiritilmagan
  hududda — shartnoma narxi. Yangi shartnomada narx ta'rifdan (o'zgartirilmaydi), turi — faqat kub.
  API: `GET /api/v1/tariffs`, `GET /api/v1/tariffs/price`, `POST /api/v1/tariffs`, `DELETE /api/v1/tariffs/{id}`, `PUT /api/v1/tariffs/lock`.
- **Raqamli maydonlar:** STIR 9, MFO 5, hisob raqam 20, OKED 5 raqamdan oshmaydi, harf qabul qilinmaydi (barcha formalarda).
- **Kadastr** ixtiyoriy, yonida «Ijara» belgisi (shartnoma 10.3-bandi: ijara / mulk huquqi asosida).
- **Tugallanmagan shartnomalar:** korxona tanlangan zahoti raqamsiz loyiha; «Saqlab chiqish» yoki yopish — forma tekshiruvsiz
  saqlanadi; «Shartnomalar › Tugallanmagan»dan «Davom etish». Raqam — tekshiruvdan o'tgach.
- **Mavjud shartnomalarni kiritish** («Yangi shartnoma» ustasida): bittalab forma (raqam, platforma ID, tur, sanalar, skan) va
  Excel (shablon → sinov → import; korxona tuman + STIR yoki nom bo'yicha topiladi, topilmasa yaratiladi). Darhol «Tasdiqlangan».
- **Rol sarlavhasi:** har oynada katta qilib: Administrator, Boshqaruv (Manager), Call-markaz, GPS dispetcherlik, Yuridik bo'lim,
  Buxgalteriya, Haydovchi.
- **Refresh:** tab, ichki tab, filtr va oy tanlovi saqlanadi; sessiya tugab qayta kirilganda oxirgi sahifa ochiladi.
- Migratsiya 0015.
