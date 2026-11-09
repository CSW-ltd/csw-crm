#!/usr/bin/env bash
# Let's Encrypt sertifikati (HTTP-01) .env'dagi barcha hostlar uchun: SITE_HOST (+ www), ADMIN_HOST, PORTAL_HOSTS, TEST_HOSTS.
# Birinchi marta ham, portal qo'shilganda/olib tashlanganda ham shu buyruq (ro'yxat o'zgarsa sertifikat yangilanadi):
#   cd /opt/csw/deploy/app && ./certs.sh <email>
# edge ishlamayotgan bo'lsa — standalone (80-port), ishlayotgan bo'lsa — webroot + nginx reload.
set -euo pipefail
cd "$(dirname "$0")"
email=${1:?Foydalanish: ./certs.sh <email>}
[[ -f .env ]] || { echo ".env topilmadi" >&2; exit 2; }

val() { grep -E "^$1=" .env | tail -1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//; s/^"//; s/"$//'; }
site=$(val SITE_HOST); cert=$(val CERT_NAME); cert=${cert:-csw.uz}
[[ -n "$site" ]] || { echo "SITE_HOST bo'sh" >&2; exit 2; }
hosts="$site www.$site $(val ADMIN_HOST) $(val PORTAL_HOSTS) $(val TEST_HOSTS)"
args=(); for h in $hosts; do args+=(-d "$h"); done
echo "→ sertifikat «$cert» ($(( ${#args[@]} / 2 )) ta nom): $hosts"

dc() { IMAGE_TAG=none docker compose "$@"; }
common=(certonly --cert-name "$cert" "${args[@]}" --agree-tos -m "$email" --no-eff-email --non-interactive --expand)
if dc ps --status running --services 2>/dev/null | grep -qx edge; then
  dc run --rm --no-deps --entrypoint certbot certbot "${common[@]}" --webroot -w /var/www/certbot
  dc exec edge nginx -s reload
else
  dc run --rm --no-deps -p 80:80 --entrypoint certbot certbot "${common[@]}" --standalone
fi
echo "✓ tayyor"
