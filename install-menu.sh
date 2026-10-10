
#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPO="roshd60mhn/sanaei-telegram-bot"
PROJECT_DIR="/opt/sanaei-telegram-bot"
BACKUP_ROOT="/opt/sanaei-telegram-bot-backups"

command -v curl >/dev/null || { echo "curl نصب نیست."; exit 1; }
command -v python3 >/dev/null || { echo "python3 نصب نیست."; exit 1; }

echo "در حال دریافت نسخه‌های GitHub..."
TAGS_JSON="$(curl -fsSL "https://api.github.com/repos/${REPO}/tags?per_page=100")" || {
    echo "دریافت نسخه‌ها ناموفق بود."
    exit 1
}

mapfile -t TAGS < <(
    printf '%s' "$TAGS_JSON" |
    python3 -c '
import json,sys
data=json.load(sys.stdin)
for item in data:
    name=item.get("name","")
    if name and not item.get("name","").startswith("refs/"):
        print(name)
'
)

if ((${#TAGS[@]} == 0)); then
    echo "هیچ Tag نسخه‌ای پیدا نشد."
    exit 1
fi

echo
echo "=== انتخاب عملیات ==="
echo "1) نصب جدید"
echo "2) به‌روزرسانی نصب موجود"
echo "0) خروج"
read -r -p "انتخاب: " ACTION

case "$ACTION" in
    1) MODE="new" ;;
    2) MODE="update" ;;
    0) exit 0 ;;
    *) echo "انتخاب نامعتبر است."; exit 1 ;;
esac

echo
echo "=== نسخه‌های موجود ==="
for i in "${!TAGS[@]}"; do
    printf "%d) %s\n" "$((i+1))" "${TAGS[$i]}"
done

read -r -p "شماره نسخه: " VERSION_NUMBER
[[ "$VERSION_NUMBER" =~ ^[0-9]+$ ]] || { echo "شماره نامعتبر است."; exit 1; }
(( VERSION_NUMBER >= 1 && VERSION_NUMBER <= ${#TAGS[@]} )) || {
    echo "شماره خارج از محدوده است."
    exit 1
}

TAG="${TAGS[$((VERSION_NUMBER-1))]}"
RELEASE_URL="https://github.com/${REPO}/archive/refs/tags/${TAG}.tar.gz"

echo
echo "عملیات: $([[ "$MODE" == new ]] && echo 'نصب جدید' || echo 'به‌روزرسانی')"
echo "نسخه انتخاب‌شده: $TAG"
read -r -p "برای ادامه دقیقاً YES بنویسید: " CONFIRM
[[ "$CONFIRM" == "YES" ]] || { echo "لغو شد."; exit 0; }

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "دریافت فایل نسخه..."
curl -fsSL --retry 3 "$RELEASE_URL" -o "$TMP_DIR/release.tar.gz"
mkdir "$TMP_DIR/source"
tar -xzf "$TMP_DIR/release.tar.gz" -C "$TMP_DIR/source" --strip-components=1
SRC="$TMP_DIR/source"

for f in bot.py config.py database.py sanaei.py utils.py requirements.txt Dockerfile docker-compose.yml; do
    [[ -f "$SRC/$f" ]] || { echo "فایل ضروری در نسخه موجود نیست: $f"; exit 1; }
done

if [[ "$MODE" == "new" ]]; then
    if [[ -e "$PROJECT_DIR/.env" || -e "$PROJECT_DIR/data/bot.db" ]]; then
        echo "برای جلوگیری از بازنویسی اطلاعات، مسیر نصب فعلی دارای تنظیمات یا دیتابیس است."
        echo "نصب جدید را در مسیر جداگانه انجام دهید یا ابتدا وضعیت این مسیر را بررسی کنید."
        exit 1
    fi

    mkdir -p "$PROJECT_DIR/data"
    for f in bot.py config.py database.py sanaei.py utils.py requirements.txt Dockerfile docker-compose.yml; do
        install -m 0644 "$SRC/$f" "$PROJECT_DIR/$f"
    done

    [[ -f "$SRC/VERSION" ]] && install -m 0644 "$SRC/VERSION" "$PROJECT_DIR/VERSION"
    [[ -f "$SRC/.env.example" ]] && install -m 0600 "$SRC/.env.example" "$PROJECT_DIR/.env"

    echo "فایل‌های نسخه نصب شدند."
    echo "فایل تنظیمات را در $PROJECT_DIR/.env تکمیل کنید، سپس اجرا کنید:"
    echo "cd $PROJECT_DIR && docker compose up -d --build"
    echo "برای نصب جدید، دیتابیس و سرویس را این اسکریپت خودکار راه‌اندازی نمی‌کند."
    exit 0
fi

[[ -f "$PROJECT_DIR/.env" ]] || { echo "فایل .env نصب فعلی پیدا نشد."; exit 1; }
[[ -f "$PROJECT_DIR/data/bot.db" ]] || { echo "دیتابیس فعلی پیدا نشد."; exit 1; }
command -v docker >/dev/null || { echo "Docker نصب نیست."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose در دسترس نیست."; exit 1; }

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"
mkdir -p "$BACKUP_DIR/data" "$BACKUP_DIR/code"
chmod 700 "$BACKUP_ROOT" "$BACKUP_DIR"

cp -a "$PROJECT_DIR/data/." "$BACKUP_DIR/data/"
for f in .env bot.py config.py database.py sanaei.py utils.py requirements.txt Dockerfile docker-compose.yml VERSION; do
    [[ -f "$PROJECT_DIR/$f" ]] && cp -p "$PROJECT_DIR/$f" "$BACKUP_DIR/code/$f"
done

echo "پشتیبان ساخته شد: $BACKUP_DIR"
echo "توقف سرویس..."
cd "$PROJECT_DIR"
docker compose down

for f in bot.py config.py database.py sanaei.py utils.py requirements.txt Dockerfile docker-compose.yml; do
    install -m 0644 "$SRC/$f" "$PROJECT_DIR/$f"
done
[[ -f "$SRC/VERSION" ]] && install -m 0644 "$SRC/VERSION" "$PROJECT_DIR/VERSION"

docker compose config -q
docker compose up -d --build bot

echo "به‌روزرسانی درخواست شد. وضعیت سرویس:"
docker compose ps
echo "لاگ‌ها: docker compose logs --tail=100 bot"
echo "پشتیبان: $BACKUP_DIR"
