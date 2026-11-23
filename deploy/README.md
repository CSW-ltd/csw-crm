# Deploy: csw-app, csw-db, csw-test (UzCloud)

Bu yerda IP manzillar, parollar va kirish buyruqlari **yo'q** — ular tech lead'ning shaxsiy hujjatlarida.
Hamma serverda: Ubuntu 24.04, faqat kalit bilan SSH, `ufw`, `fail2ban`, Docker (compose plugin bilan). Repo nusxasi: `/opt/csw`.

```
internet ──443──▶ csw-app: edge nginx ─┬─▶ web ─▶ api ──3306──▶ csw-db: mysql
                                       │                └──────▶ UzCloud S3 (csw-files-<CRN>)
                                       └─▶ csw-test:8080 (*.test.csw.uz; o'z mysql + minio)
csw-db: backup.sh (har tun) ──▶ /var/backups/csw (7 kun) + S3 csw-backups-<CRN> (age bilan shifrlangan)
```

## Reliz oqimi

Filiallar: `dev` (test) → `prod` (production) → `master` (oxirgi barqaror versiya).

1. `dev`ga push → GitHub Actions testlar + `ghcr.io/csw-ltd/csw-crm-{api,web}:<to'liq SHA>` rasmlari.
2. **Test:** `cd /opt/csw/deploy/test && ../deploy.sh $(git rev-parse origin/dev)` → https://legal.test.csw.uz va boshqa test portallarida sinov.
3. **Prod:** `dev` → `prod` fast-forward (`git push origin dev:prod`) — SHA o'zgarmaydi. Migratsiyali reliz bo'lsa avval
   csw-db'da `sudo systemctl start csw-backup` → keyin `cd /opt/csw/deploy/app && ../deploy.sh <o'sha SHA>`.
4. Bir necha kun muammosiz ishlasa: `prod` → `master` (`git push origin prod:master`) — tiklash nuqtasi.
5. Muammo bo'lsa: tezkor — `../deploy.sh --rollback` (faqat rasm; migratsiya qaytmaydi — kerak bo'lsa `restore.sh`);
   jiddiy — `prod` kodini `master` holatiga qaytarish (revert commit) va `../deploy.sh $(git rev-parse origin/master)`.

`deploy.sh` rasmni tortadi, `up -d` qiladi va `/api/v1/health` ni kutadi; o'tmasa oldingi tag'ga avtomatik qaytaradi.
Joriy versiya: `cat .image-tag` yoki `curl https://manager.csw.uz/api/v1/health`.
Qo'lda compose buyruqlari (`ps`, `logs`, `exec`) — `../dc ...` orqali: u `IMAGE_TAG`ni `.image-tag`dan oladi
(oddiy `docker compose ...` «IMAGE_TAG kerak» xatosini beradi).

> Rasmlar repo egasi nomida (`CSW-ltd` → `ghcr.io/csw-ltd/...`); boshqa registry kerak bo'lsa `.env`da `IMAGE_REPO=...`.
> Birinchi push'dan keyin GitHub (CSW-ltd tashkiloti) → Packages → `csw-crm-api` va `csw-crm-web` → Package settings → **Change visibility → Public**
> (serverlar token'siz tortishi uchun). Rasmda sir yo'q — sirlar faqat serverdagi `.env`da.

## 1. csw-db

```bash
cd /opt/csw/deploy/db
cp .env.example .env && chmod 600 .env          # parollar: openssl rand -base64 32
docker compose up -d --wait
sudo ufw allow from <csw-app ichki IP> to any port 3306 proto tcp
```

**Zaxira** (`apt install age rclone`):

```bash
# Kalit juftligi — OFLAYN kompyuterda (serverda emas):  age-keygen -o csw-backup-key.txt
# Ochiq kalit (age1...) backup.env ga; maxfiy kalit — xavfsiz joyda (2 nusxa), serverga faqat tiklash paytida.
cp backup.env.example backup.env && chmod 600 backup.env
sudo ./backup.sh                                 # birinchi qo'lda sinov
sudo cp systemd/csw-backup.* /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now csw-backup.timer
systemctl list-timers csw-backup.timer           # keyingi ishga tushish
journalctl -u csw-backup --since today           # natija
```

S3 kaliti faqat zaxira omboriniki bo'lsin (prod fayllari omboridan alohida).

### UzCloud Object Storage — muhim
- Ikki alohida ombor (Object Storage): `csw-prod` (bucket `csw-files`, **Versioning yoqilgan**, Object Lock — yo'q) va
  `csw-backup` (bucket `csw-backups`, versioning'siz — eski zaxiralarni skript o'chiradi). Kalitlar ombor bo'yicha (panel → «Credentials»).
- **UzCloud bucket nomiga mijoz raqamini qo'shadi:** `csw-files` → `csw-files-<CRN>`. `.env`da `MINIO_BUCKET` va `backup.env`da
  `BACKUP_REMOTE=uzs3:csw-backups-<CRN>/db` — paneldagi aniq nom bilan. Noto'g'ri nomda `AccessDenied` qaytadi.
- `HEAD` so'rovida (bucket tekshiruvi) noto'g'ri secret ham `AccessDenied` bo'lib ko'rinadi; aniq sababni `list_buckets` ko'rsatadi
  (`SignatureDoesNotMatch` — secret xato).
- **Kalitni terminalga joylashtirish:** bash «bracketed paste» qiymat boshi/oxiriga ko'rinmas `ESC[200~`/`ESC[201~` (12 belgi) qo'shadi —
  kalit buziladi. Avval `bind 'set enable-bracketed-paste off'`, keyin bitta qatorda `read -s -p "Secret: " SK; echo "${#SK}"`
  (uzunlik: access 20, secret 40) va `.env`ga python bilan yozing (`sed` `&`/`\` belgilarni buzadi). Bir nechta qatorni birga joylashtirmang.
- Shartnoma va fayllar **umrbod** saqlanadi — bucket'larga lifecycle (avto-o'chirish) qoidasi qo'shilmaydi.

**Tiklash** (har oy sinab ko'ring — avval boshqa nomli bazaga):

```bash
sudo ./restore.sh -i ~/key.txt list
sudo ./restore.sh -i ~/key.txt s3:csw-csw_crm-YYYYMMDD-HHMMSS.sql.gz.age csw_restore_check   # tekshiruv
sudo ./restore.sh -i ~/key.txt s3:csw-csw_crm-YYYYMMDD-HHMMSS.sql.gz.age                     # prod bazani almashtirish (api to'xtatilgan holda)
shred -u ~/key.txt
```

## 2. csw-app

**Hostlar** (DNS'da `*.csw.uz` wildcard bor — shuning uchun faqat `.env`dagi nomlar ochiladi, qolgani rad etiladi):

| Host | Vazifa |
|---|---|
| `csw.uz` (`www` → 301) | landing («tez orada»); faqat `/api/v1/public/` (ochiq faktura havolalari) api'ga o'tadi |
| `admin.csw.uz` | admin (`admin-allow.conf`; 2026-11-11 dan `allow all` — ofis IP har kuni o'zgaradi) |
| `manager.csw.uz`, `legal.csw.uz`, `account.csw.uz` | 1-bosqich rol portallari (`PORTAL_HOSTS`) |
| `*.test.csw.uz` (`TEST_HOSTS`) | csw-test'ga proksi; admin testda ochiq |

Har rol faqat o'z subdomenida kiradi (`ROLE_HOSTS`, boshqa rol — `wrong_portal`); cookie'lar host-only.

```bash
cd /opt/csw/deploy/app
cp .env.example .env && chmod 600 .env          # JWT_SECRET: openssl rand -hex 48
cp admin-allow.conf.example admin-allow.conf    # hozir: allow all;  (fayl faqat serverda)
sudo ufw allow 80,443/tcp

./certs.sh <email>                              # Let's Encrypt (HTTP-01) .env'dagi barcha hostlar uchun
../deploy.sh <sha>                              # api + web + edge + certbot (yangilash har 12 soatda)
```

`admin-allow.conf` bo'lmasa `edge` ishga tushmaydi (Docker uning o'rniga papka yaratadi — `rm -rf admin-allow.conf` va nusxani qayta oling).
Cheklovni qayta yoqish: `allow <IP>; ... deny all;` → `../dc exec edge nginx -t && ../dc exec edge nginx -s reload`. Cheklovsiz holatda himoya: login so'rov cheklovi (10/daqiqa), 5 xatodan keyin 15 daqiqa blok, kuchli parol, admin uchun 2FA (pastda).

**Yangi portal ochish** (masalan `call.csw.uz` → operator): `.env`da `PORTAL_HOSTS`, `ROLE_HOSTS`, `CORS_ORIGINS` (va kerak bo'lsa
`ACTIVE_ROLES`) ga qo'shing → `./certs.sh <email>` (sertifikat kengaytiriladi) → `../deploy.sh $(cat .image-tag)`.

**Admin 2FA (TOTP)** — prod'da har admin uchun majburiy (`APP_ENV=demo` test serverda o'chiq).
- `.env`da `TOTP_ENC_KEY` bo'lmasa api ishga tushmaydi (yaratish buyrug'i `.env.example`da). Kalit almashtirilsa barcha adminlar 2FA'ni qayta ulaydi.
- Birinchi kirishda: parol → QR kod (Google/Microsoft Authenticator) → 6 xonali kod → 10 ta zaxira kod (bir marta ko'rsatiladi, «Saqlab oldim»).
- Keyin har login'da kod so'raladi; telefon yo'q bo'lsa — zaxira kod (har biri bir marta, Vaziyat paneliga yoziladi).
- Telefon va zaxira kodlar yo'qolsa: boshqa admin «Xodimlar» → «2FA'ni qayta o'rnatish» (sabab majburiy). Kamida 2 ta faol admin bo'lsin
  (bitta bo'lsa — ogohlantirish; oxirgi adminni faolsizlantirib bo'lmaydi). Oxirgi chora — serverda:
  `../dc exec api python -m app.reset_2fa <login> "<sabab>"`.
- `/api/v1/auth/2fa/*` edge'da login bilan bir xil cheklov (10/daqiqa). Shablon o'zgarganda: `../dc restart edge`.

**Boshlang'ich ma'lumot** (viloyat, tuman, xodimlar) — haqiqiy fayl faqat serverda:

```bash
cp ../bootstrap.example.yaml bootstrap.yaml && chmod 600 bootstrap.yaml   # tahrirlang
../dc exec -T api python -m app.bootstrap /dev/stdin < bootstrap.yaml
```

Vaqtinchalik parollar terminalga **bir marta** chiqadi — xodimlarga xavfsiz kanal orqali bering; birinchi kirishda almashtiriladi.
Qayta ishga tushirish mavjud loginlarni o'zgartirmaydi (yangi xodim qo'shish uchun faylga qo'shib, yana ishga tushiring).

`ACTIVE_ROLES=admin,manager,legal,accountant,gps,driver` (1-bosqich, Angor pilot; `gps` — `dispatch.csw.uz`, `driver` — `driver.csw.uz`): boshqa rollar kira olmaydi (`role_inactive`), ular uchun xodim yaratilmaydi.
Rolni ochish: `.env`ga qo'shing → `../deploy.sh $(cat .image-tag)`.

### Yangi tuman ochish (pilot: Angor, keyin birma-bir)

Kod o'zgarmaydi — har tuman shu tartibda. Haqiqiy ism, telefon, raqamlar faqat serverdagi `bootstrap.yaml`da va admin panelda.

1. **Zaxira:** csw-db'da `backup.sh`.
2. **Tuman va xodimlar:** `bootstrap.yaml`ga tuman (viloyat `districts` ro'yxatiga) va xodimlar (manager/legal/accountant —
   `districts: [...]`, gps/driver — `district: ...`) → `../dc exec -T api python -m app.bootstrap /dev/stdin < bootstrap.yaml`.
   Vaqtinchalik parollar bir marta chiqadi — xavfsiz kanal orqali bering.
3. **Admin panel → «Ta'riflar»:** tuman tarifi (sanasi bilan).
4. **«Mashinalar»:** tuman mashinalari (davlat raqami GPS'dagi bilan bir xil yozilsin — import shu bo'yicha bog'laydi).
5. **«GPS geozonalar»:** shu tuman eksport zip'i → «Tekshirish» (bo'limni CRM tumaniga moslang, sonlarni agent bilan solishtiring) → «Import».
6. **«Sozlamalar»:** tuman radiusi (kerak bo'lsa), printer rejimi.
7. **GPS xodimi** (`dispatch.csw.uz`): «Kunlik ish jadvali» — mashina ↔ haydovchi; haydovchi `driver.csw.uz`da smenani ochadi.
8. **Tekshiruv:** har rol o'z portalida kiradi; bitta sinov murojaati: murojaat → biriktirish → varaqa → yopish → Vaziyat paneli.

## 3. csw-test

Ochiq IP yo'q — GHCR'dan rasm tortish uchun **chiquvchi internet (NAT)** kerak.

```bash
cd /opt/csw/deploy/test
cp .env.example .env && chmod 600 .env          # prod'dan boshqa parollar va JWT_SECRET
sudo ufw allow from <csw-app ichki IP> to any port 8080 proto tcp
../deploy.sh <sha>
../dc exec api python -m app.seed --reset --yes   # demo: 7 ta csw.* login, parollar .env DEMO_CREDENTIALS'da
```

Portallar: `ROLE_HOSTS` — har rol o'z test subdomenida (`legal.test.csw.uz` …), ro'yxat csw-app'dagi `TEST_HOSTS` bilan mos bo'lsin.
Demo rejim (`APP_ENV=demo`): login sahifasida shu portal rolining demo logini chip sifatida (parolsiz), har brauzer tabida boshqa rol (`TAB_SESSIONS=true`).
Parollarni almashtirish: `.env` dagi `DEMO_CREDENTIALS` → `../deploy.sh $(cat .image-tag)` → `seed --reset --yes`.

Test serverga haqiqiy ma'lumot yuklanmaydi.

## Tekshiruv ro'yxati (har serverda)

- `curl -sk https://<csw-app IP>/` va `curl -s https://boshqa.csw.uz/` → ulanish rad etiladi; `admin.csw.uz` — login sahifasi (IP cheklovi o'chiq).
- `ss -tlnp`: csw-app — faqat 22/80/443; csw-db — 3306 faqat ichki IP'da; csw-test — 8080 faqat ichki IP'da.
- `curl -s https://manager.csw.uz/api/v1/health` → `{"status":"ok","db":"ok","version":"<sha>"}`.
- `APP_ENV=production` da xavfsiz bo'lmagan sozlama (standart `JWT_SECRET`, `COOKIE_SECURE=false`, SQLite, ...) bo'lsa api ishga tushmaydi — `../dc logs api`.
