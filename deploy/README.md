# Deploy: csw-app, csw-db, csw-test (UzCloud)

Bu yerda IP manzillar, parollar va kirish buyruqlari **yo'q** — ular tech lead'ning shaxsiy hujjatlarida.
Hamma serverda: Ubuntu 24.04, faqat kalit bilan SSH, `ufw`, `fail2ban`, Docker (compose plugin bilan). Repo nusxasi: `/opt/csw`.

```
internet ──443──▶ csw-app: edge nginx ─┬─▶ web ─▶ api ──3306──▶ csw-db: mysql
                                       │                └──────▶ UzCloud S3 (csw-files)
                                       └─▶ csw-test:8080 (test.csw.uz; o'z mysql + minio)
csw-db: backup.sh (har tun) ──▶ /var/backups/csw (7 kun) + S3 csw-backups (age bilan shifrlangan)
```

## Reliz oqimi

1. PR `main`ga merge bo'ladi → GitHub Actions testlar + `ghcr.io/uzsaltmine-dev/csw-crm-{api,web}:<to'liq SHA>` rasmlari.
2. **Test:** `cd /opt/csw/deploy/test && ../deploy.sh <sha>` → https://test.csw.uz da sinov.
3. **Prod:** migratsiyali reliz bo'lsa avval csw-db'da `sudo systemctl start csw-backup` → keyin
   `cd /opt/csw/deploy/app && ../deploy.sh <sha>` (aynan testda sinalgan SHA).
4. Muammo bo'lsa: `../deploy.sh --rollback` (faqat rasm qaytadi; migratsiya qaytmaydi — kerak bo'lsa `restore.sh`).

`deploy.sh` rasmni tortadi, `up -d` qiladi va `/api/v1/health` ni kutadi; o'tmasa oldingi tag'ga avtomatik qaytaradi.
Joriy versiya: `cat .image-tag` yoki `curl https://crm.csw.uz/api/v1/health`.

> Birinchi push'dan keyin GitHub → Packages → `csw-crm-api` va `csw-crm-web` → Package settings → **Change visibility → Public**
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

S3 kaliti faqat `csw-backups` bucket'iga yozish huquqli bo'lsin (prod `csw-files` kalitidan alohida).

**Tiklash** (har oy sinab ko'ring — avval boshqa nomli bazaga):

```bash
sudo ./restore.sh -i ~/key.txt list
sudo ./restore.sh -i ~/key.txt s3:csw-csw_crm-YYYYMMDD-HHMMSS.sql.gz.age csw_restore_check   # tekshiruv
sudo ./restore.sh -i ~/key.txt s3:csw-csw_crm-YYYYMMDD-HHMMSS.sql.gz.age                     # prod bazani almashtirish (api to'xtatilgan holda)
shred -u ~/key.txt
```

## 2. csw-app

```bash
cd /opt/csw/deploy/app
cp .env.example .env && chmod 600 .env          # JWT_SECRET: openssl rand -base64 48
sudo ufw allow 80,443/tcp

# Birinchi sertifikat (DNS crm.csw.uz va test.csw.uz → csw-app ochiq IP bo'lgandan keyin)
IMAGE_TAG=none docker compose run --rm -p 80:80 --entrypoint certbot certbot certonly --standalone \
  -d crm.csw.uz -d test.csw.uz --agree-tos -m <email> --no-eff-email

../deploy.sh <sha>                              # api + web + edge + certbot (yangilash har 12 soatda)
```

**Boshlang'ich ma'lumot** (viloyat, tuman, xodimlar) — haqiqiy fayl faqat serverda:

```bash
cp ../bootstrap.example.yaml bootstrap.yaml && chmod 600 bootstrap.yaml   # tahrirlang
docker compose exec -T api python -m app.bootstrap /dev/stdin < bootstrap.yaml
```

Vaqtinchalik parollar terminalga **bir marta** chiqadi — xodimlarga xavfsiz kanal orqali bering; birinchi kirishda almashtiriladi.
Qayta ishga tushirish mavjud loginlarni o'zgartirmaydi (yangi xodim qo'shish uchun faylga qo'shib, yana ishga tushiring).

`ACTIVE_ROLES=admin,manager,legal,accountant` (1-bosqich): boshqa rollar kira olmaydi (`role_inactive`), ular uchun xodim yaratilmaydi.
Rolni ochish: `.env`ga qo'shing → `../deploy.sh $(cat .image-tag)`.

## 3. csw-test

Ochiq IP yo'q — GHCR'dan rasm tortish uchun **chiquvchi internet (NAT)** kerak.

```bash
cd /opt/csw/deploy/test
cp .env.example .env && chmod 600 .env          # prod'dan boshqa parollar va JWT_SECRET
sudo ufw allow from <csw-app ichki IP> to any port 8080 proto tcp
../deploy.sh <sha>
docker compose exec -T api python -m app.bootstrap /dev/stdin < bootstrap.yaml   # yoki: python -m app.seed (demo)
```

Test serverga haqiqiy ma'lumot yuklanmaydi.

## Tekshiruv ro'yxati (har serverda)

- `ss -tlnp`: csw-app — faqat 22/80/443; csw-db — 3306 faqat ichki IP'da; csw-test — 8080 faqat ichki IP'da.
- `curl -s https://crm.csw.uz/api/v1/health` → `{"status":"ok","db":"ok","version":"<sha>"}`.
- `APP_ENV=production` da xavfsiz bo'lmagan sozlama (standart `JWT_SECRET`, `COOKIE_SECURE=false`, SQLite, ...) bo'lsa api ishga tushmaydi — `docker compose logs api`.
