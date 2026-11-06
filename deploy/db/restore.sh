#!/usr/bin/env bash
# Zaxiradan tiklash (csw-db yoki csw-test'da).
#   ./restore.sh -i /path/key.txt list                       # S3 va lokal zaxiralar ro'yxati
#   ./restore.sh -i /path/key.txt <fayl|s3:nom> [baza_nomi]  # tiklash (standart: MYSQL_DATABASE)
# -i — age maxfiy kaliti (faqat tiklash paytida keltiriladi, keyin o'chiring: shred -u key.txt).
# Maqsadli baza TO'LIQ almashtiriladi — tasdiq so'raladi. Avval boshqa nomga tiklab tekshirish tavsiya etiladi (masalan csw_restore_check).
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
set -a; source "$DIR/.env"; [[ -f "$DIR/backup.env" ]] && source "$DIR/backup.env"; set +a
LOCAL_DIR=${BACKUP_LOCAL_DIR:-/var/backups/csw}
REMOTE=${BACKUP_REMOTE:-uzs3:csw-backups/db}

key=""
while getopts "i:" o; do case $o in i) key=$OPTARG ;; *) exit 2 ;; esac; done
shift $((OPTIND - 1))
src=${1:-}
[[ -n "$src" ]] || { sed -n 2,6p "$0"; exit 2; }

if [[ "$src" == "list" ]]; then
  echo "Lokal ($LOCAL_DIR):"; ls -1t "$LOCAL_DIR"/csw-*.sql.gz.age 2>/dev/null || echo "  yo'q"
  echo "S3 ($REMOTE):"; rclone lsl "$REMOTE" | sort -k2,3 -r | head -30
  exit 0
fi
[[ -f "$key" ]] || { echo "-i <age maxfiy kaliti> kerak" >&2; exit 2; }

target=${2:-$MYSQL_DATABASE}
[[ "$target" =~ ^[A-Za-z0-9_]+$ ]] || { echo "Baza nomi faqat harf, raqam, _" >&2; exit 2; }

tmpdir=$(mktemp -d); trap 'rm -rf "$tmpdir"' EXIT
if [[ "$src" == s3:* ]]; then
  file="$tmpdir/${src#s3:}"
  rclone copyto "$REMOTE/${src#s3:}" "$file"
else
  file=$src
fi
[[ -f "$file" ]] || { echo "Fayl topilmadi: $file" >&2; exit 2; }

# Tiklashdan oldin shifr va arxiv butunligini tekshiramiz
age -d -i "$key" "$file" | gzip -t || { echo "Fayl buzilgan yoki kalit noto'g'ri" >&2; exit 1; }

echo "Manba:  $(basename "$file")"
echo "Baza:   $target  (mavjud bo'lsa O'CHIRILIB qayta yaratiladi)"
read -r -p "Davom etish uchun baza nomini yozing: " confirm
[[ "$confirm" == "$target" ]] || { echo "Bekor qilindi"; exit 1; }

cd "$DIR"
sql() { docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot -N --default-character-set=utf8mb4 "$@"' sh "$@"; }

printf 'DROP DATABASE IF EXISTS `%s`; CREATE DATABASE `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON `%s`.* TO '"'"'%s'"'"'@'"'"'%%'"'"';\n' \
  "$target" "$target" "$target" "$MYSQL_USER" | sql
age -d -i "$key" "$file" | gunzip | sql "$target"

tables=$(printf "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='%s';\n" "$target" | sql)
version=$(printf 'SELECT version_num FROM `%s`.alembic_version;\n' "$target" | sql)
echo "✓ Tiklandi: $target — $tables ta jadval, alembic: $version"
