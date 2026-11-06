#!/usr/bin/env bash
# csw-db: tungi zaxira. mysqldump → gzip → age (ochiq kalit bilan shifr) → /var/backups/csw (7 kun) + S3 csw-backups.
# Maxfiy kalit serverda SAQLANMAYDI — faqat tiklash paytida keltiriladi (restore.sh).
# Systemd timer: deploy/db/systemd/csw-backup.{service,timer}. Qo'lda: sudo /opt/csw/deploy/db/backup.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
set -a; source "$DIR/.env"; source "$DIR/backup.env"; set +a

: "${AGE_RECIPIENT:?AGE_RECIPIENT kerak (age ochiq kaliti, age1...)}"
: "${MYSQL_DATABASE:?}"
LOCAL_DIR=${BACKUP_LOCAL_DIR:-/var/backups/csw}
KEEP_DAYS=${BACKUP_LOCAL_KEEP_DAYS:-7}
S3_KEEP_DAYS=${BACKUP_S3_KEEP_DAYS:-90}
REMOTE=${BACKUP_REMOTE:-uzs3:csw-backups/db}

umask 077
mkdir -p "$LOCAL_DIR"
name="csw-${MYSQL_DATABASE}-$(date +%Y%m%d-%H%M%S).sql.gz.age"
tmp="$LOCAL_DIR/.$name.part"
trap 'rm -f "$tmp"' EXIT

cd "$DIR"
# --single-transaction: InnoDB'ni bloklamasdan izchil nusxa. --databases ishlatilmaydi — boshqa nomli bazaga tiklash mumkin bo'lsin.
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -uroot \
    --single-transaction --quick --routines --triggers --events --hex-blob --set-gtid-purged=OFF \
    --default-character-set=utf8mb4 "$MYSQL_DATABASE"' \
  | gzip -6 | age -r "$AGE_RECIPIENT" > "$tmp"

# Bo'sh yoki juda kichik fayl — xato (dump to'liq bo'lmagan)
size=$(stat -c %s "$tmp")
(( size > 1024 )) || { echo "Zaxira juda kichik ($size bayt) — to'xtatildi" >&2; exit 1; }
mv "$tmp" "$LOCAL_DIR/$name"
trap - EXIT

rclone copyto "$LOCAL_DIR/$name" "$REMOTE/$name" --s3-no-check-bucket
find "$LOCAL_DIR" -maxdepth 1 -name 'csw-*.sql.gz.age' -mtime +"$KEEP_DAYS" -delete
rclone delete "$REMOTE" --min-age "${S3_KEEP_DAYS}d" --include 'csw-*.sql.gz.age'

echo "✓ $name ($(numfmt --to=iec "$size")) — lokal va $REMOTE"
