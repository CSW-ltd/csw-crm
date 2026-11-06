#!/usr/bin/env bash
# Rasmni (GHCR, tag = commit SHA) yangilash. Serverda, kerakli papkada ishga tushiriladi:
#   cd /opt/csw/deploy/test && ../deploy.sh <sha>     # avval test
#   cd /opt/csw/deploy/app  && ../deploy.sh <sha>     # keyin aynan o'sha SHA prod'ga
#   ../deploy.sh --rollback                           # oldingi tag'ga qaytish
# Eslatma: migratsiyalar faqat oldinga ishlaydi. Migratsiyali relizdan oldin csw-db'da backup.sh ni qo'lda ishga tushiring.
set -euo pipefail

[[ -f compose.yml ]] || { echo "compose.yml topilmadi — deploy/app yoki deploy/test papkasida ishga tushiring" >&2; exit 2; }
[[ -f .env ]] || { echo ".env topilmadi (.env.example'dan nusxa oling)" >&2; exit 2; }

TAG_FILE=.image-tag
PREV_FILE=.image-tag.prev
current=$(cat "$TAG_FILE" 2>/dev/null || true)

if [[ "${1:-}" == "--rollback" ]]; then
  new=$(cat "$PREV_FILE" 2>/dev/null || true)
  [[ -n "$new" ]] || { echo "Oldingi tag yo'q" >&2; exit 2; }
elif [[ "${1:-}" =~ ^[0-9a-f]{7,40}$ ]]; then
  new=$1
else
  echo "Foydalanish: $0 <commit-sha> | --rollback" >&2; exit 2
fi
if [[ ${#new} -ne 40 ]]; then
  echo "To'liq 40 belgili SHA kerak (GHCR tag'i to'liq SHA): git rev-parse $new" >&2; exit 2
fi

compose() { IMAGE_TAG="$1" docker compose "${@:2}"; }

health() {
  local tag=$1
  for _ in $(seq 1 30); do
    if compose "$tag" exec -T api python -c \
      "import json,urllib.request as u; d=json.load(u.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)); assert d['status']=='ok'" \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 3
  done
  return 1
}

echo "→ $new rasmlari tortilmoqda"
compose "$new" pull api web
echo "→ ishga tushirilmoqda (eski: ${current:-—})"
compose "$new" up -d --remove-orphans

if health "$new"; then
  [[ -n "$current" && "$current" != "$new" ]] && echo "$current" > "$PREV_FILE"
  echo "$new" > "$TAG_FILE"
  echo "✓ $new ishlayapti: $(compose "$new" exec -T api python -c "import urllib.request as u; print(u.urlopen('http://127.0.0.1:8000/api/v1/health').read().decode())")"
  docker image prune -f >/dev/null
else
  echo "✗ health tekshiruvi o'tmadi. Loglar:" >&2
  compose "$new" logs api --tail 50 >&2 || true
  if [[ -n "$current" ]]; then
    echo "→ $current ga qaytarilmoqda" >&2
    compose "$current" up -d --remove-orphans
  fi
  exit 1
fi
