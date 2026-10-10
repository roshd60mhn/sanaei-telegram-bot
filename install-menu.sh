#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPO="roshd60mhn/sanaei-telegram-bot"
PROJECT_DIR="/opt/sanaei-telegram-bot"
BACKUP_ROOT="/opt/sanaei-telegram-bot-backups"

MANAGED_FILES=(
  bot.py config.py database.py sanaei.py utils.py
  requirements.txt Dockerfile docker-compose.yml VERSION .env.example
)
REQUIRED_FILES=(
  bot.py config.py database.py sanaei.py utils.py
  requirements.txt Dockerfile docker-compose.yml
)

info() { echo "[+] $*"; }
warn() { echo "[!] $*" >&2; }
die() { echo "[ERROR] $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run this script as root."
command -v curl >/dev/null || die "curl is not installed."
command -v python3 >/dev/null || die "python3 is not installed."
command -v tar >/dev/null || die "tar is not installed."

mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

echo
echo "========================================"
echo "     Sanaei Telegram Bot Installer"
echo "========================================"
echo "1) New installation"
echo "2) Update existing installation"
echo "0) Exit"
read -r -p "Choose an option: " ACTION </dev/tty

case "$ACTION" in
  1) MODE="new" ;;
  2) MODE="update" ;;
  0) exit 0 ;;
  *) die "Invalid selection." ;;
esac

info "Fetching available GitHub versions..."
TAGS_JSON="$(curl -fsSL --retry 3   "https://api.github.com/repos/${REPO}/tags?per_page=100")"   || die "Could not fetch GitHub versions."

mapfile -t TAGS < <(
  printf '%s' "$TAGS_JSON" | python3 -c '
import json, sys
for item in json.load(sys.stdin):
    name = item.get("name", "")
    if name and not any(c in name for c in "\r\n/"):
        print(name)
' | sort -Vr
)

((${#TAGS[@]} > 0)) || die "No release tags were found."

echo
echo "Available versions:"
for i in "${!TAGS[@]}"; do
  printf "%d) %s\n" "$((i+1))" "${TAGS[$i]}"
done

read -r -p "Select version number: " VERSION_NUMBER </dev/tty
[[ "$VERSION_NUMBER" =~ ^[0-9]+$ ]] || die "Invalid version number."
(( VERSION_NUMBER >= 1 && VERSION_NUMBER <= ${#TAGS[@]} ))   || die "Version number is out of range."

TAG="${TAGS[$((VERSION_NUMBER-1))]}"
RELEASE_URL="https://github.com/${REPO}/archive/refs/tags/${TAG}.tar.gz"

echo
echo "Operation: $([[ "$MODE" == new ]] && echo 'New installation' || echo 'Update existing installation')"
echo "Selected version: $TAG"
read -r -p "Type YES to continue: " CONFIRM </dev/tty
[[ "$CONFIRM" == "YES" ]] || { echo "Cancelled."; exit 0; }

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

info "Downloading release archive..."
curl -fsSL --retry 3 "$RELEASE_URL" -o "$TMP_DIR/release.tar.gz"
mkdir "$TMP_DIR/source"
tar -xzf "$TMP_DIR/release.tar.gz" -C "$TMP_DIR/source" --strip-components=1
SRC="$TMP_DIR/source"

for f in "${REQUIRED_FILES[@]}"; do
  [[ -f "$SRC/$f" ]] || die "Required release file is missing: $f"
done

ensure_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    command -v apt-get >/dev/null || die "Install Docker and Docker Compose first."
    apt-get update
    apt-get install -y docker.io docker-compose-v2
  fi
  systemctl enable --now docker
  docker compose version >/dev/null 2>&1     || die "Docker Compose is unavailable."
}

install_release_files() {
  local f
  for f in "${MANAGED_FILES[@]}"; do
    if [[ -f "$SRC/$f" ]]; then
      install -m 0644 "$SRC/$f" "$PROJECT_DIR/$f"
    fi
  done
}

configure_new_installation() {
  local BOT_TOKEN PANEL_URL PANEL_API_TOKEN PANEL_USERNAME PANEL_PASSWORD
  local CARD_NUMBER ADMIN_IDS PLAN_500_PRICE PLAN_1000_PRICE

  echo
  echo "Enter bot configuration."
  echo "Sensitive values will not be shown while typing."

  read -r -s -p "Telegram Bot Token: " BOT_TOKEN </dev/tty; echo
  read -r -p "Sanaei Panel URL: " PANEL_URL </dev/tty
  read -r -s -p "Sanaei API Token: " PANEL_API_TOKEN </dev/tty; echo
  read -r -p "Sanaei Username: " PANEL_USERNAME </dev/tty
  read -r -s -p "Sanaei Password: " PANEL_PASSWORD </dev/tty; echo
  read -r -p "Telegram Card Number: " CARD_NUMBER </dev/tty
  read -r -p "Admin Telegram ID(s), comma-separated: " ADMIN_IDS </dev/tty
  read -r -p "500GB plan price [480000]: " PLAN_500_PRICE </dev/tty
  read -r -p "1000GB plan price [970000]: " PLAN_1000_PRICE </dev/tty

  PLAN_500_PRICE="${PLAN_500_PRICE:-480000}"
  PLAN_1000_PRICE="${PLAN_1000_PRICE:-970000}"

  [[ -n "$BOT_TOKEN" && -n "$PANEL_URL" && -n "$PANEL_API_TOKEN" ]]     || die "Bot token, panel URL and API token are required."
  [[ -n "$PANEL_USERNAME" && -n "$PANEL_PASSWORD" && -n "$ADMIN_IDS" ]]     || die "Panel credentials and at least one admin ID are required."
  [[ "$PLAN_500_PRICE" =~ ^[0-9]+$ && "$PLAN_1000_PRICE" =~ ^[0-9]+$ ]]     || die "Plan prices must be integers."

  for value in "$BOT_TOKEN" "$PANEL_URL" "$PANEL_API_TOKEN"                "$PANEL_USERNAME" "$PANEL_PASSWORD" "$CARD_NUMBER" "$ADMIN_IDS"; do
    [[ "$value" != *$'\n'* && "$value" != *$'\r'* ]]       || die "Configuration values must not contain newline characters."
  done

  cat > "$PROJECT_DIR/.env" <<EOF
BOT_TOKEN=${BOT_TOKEN}
PANEL_URL=${PANEL_URL}
PANEL_API_TOKEN=${PANEL_API_TOKEN}
PANEL_USERNAME=${PANEL_USERNAME}
PANEL_PASSWORD=${PANEL_PASSWORD}

DB_PATH=/app/data/bot.db

CARD_NUMBER=${CARD_NUMBER}
PLAN_500_PRICE=${PLAN_500_PRICE}
PLAN_1000_PRICE=${PLAN_1000_PRICE}

ADMIN_IDS=${ADMIN_IDS}
EOF
  chmod 600 "$PROJECT_DIR/.env"
}

validate_and_start() {
  cd "$PROJECT_DIR"
  docker compose config -q
  docker compose build bot
  docker compose up -d bot

  info "Initializing database..."
  docker compose exec -T bot python3 -c     'import asyncio; from database import init_db; asyncio.run(init_db())'

  sleep 3
  docker compose ps

  if ! docker compose ps --status running --services | grep -qx bot; then
    docker compose logs --tail=100 bot || true
    return 1
  fi
}

if [[ "$MODE" == "new" ]]; then
  if [[ -e "$PROJECT_DIR/.env" || -e "$PROJECT_DIR/data/bot.db" ]]; then
    die "An existing .env or database was found. New installation stopped to protect your data."
  fi

  ensure_docker
  install -d -m 700 "$PROJECT_DIR/data"
  install_release_files
  configure_new_installation

  if validate_and_start; then
    info "New installation of $TAG completed successfully."
  else
    die "Installation failed. Configuration and files were preserved. Check Docker logs."
  fi
  exit 0
fi

[[ -f "$PROJECT_DIR/.env" ]] || die "Existing .env file was not found."
[[ -f "$PROJECT_DIR/data/bot.db" ]] || die "Existing database was not found."
[[ -f "$PROJECT_DIR/docker-compose.yml" ]] || die "Existing docker-compose.yml was not found."

ensure_docker

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"
install -d -m 700 "$BACKUP_DIR/code" "$BACKUP_DIR/data"
cp -p "$PROJECT_DIR/.env" "$BACKUP_DIR/.env"
cp -a "$PROJECT_DIR/data/." "$BACKUP_DIR/data/"

for f in "${MANAGED_FILES[@]}"; do
  [[ ! -f "$PROJECT_DIR/$f" ]] || cp -p "$PROJECT_DIR/$f" "$BACKUP_DIR/code/$f"
done

info "Backup created: $BACKUP_DIR"
read -r -p "Type YES to stop the bot and start the update: " CONFIRM </dev/tty
[[ "$CONFIRM" == "YES" ]] || { echo "Cancelled."; exit 0; }

rollback() {
  warn "Update failed. Attempting rollback..."
  cd "$PROJECT_DIR"
  docker compose down || true

  cp -p "$BACKUP_DIR/.env" "$PROJECT_DIR/.env"
  rm -rf "$PROJECT_DIR/data"
  mkdir -p "$PROJECT_DIR/data"
  cp -a "$BACKUP_DIR/data/." "$PROJECT_DIR/data/"

  local f
  for f in "${MANAGED_FILES[@]}"; do
    rm -f "$PROJECT_DIR/$f"
    [[ ! -f "$BACKUP_DIR/code/$f" ]]       || cp -p "$BACKUP_DIR/code/$f" "$PROJECT_DIR/$f"
  done

  if docker compose config -q && docker compose up -d --build bot; then
    warn "Previous files and database have been restored."
  else
    warn "Automatic rollback did not fully start the bot."
    warn "Backup retained at: $BACKUP_DIR"
  fi
}

cd "$PROJECT_DIR"
docker compose down || die "Could not stop the bot. No release files were changed."

install_release_files

if validate_and_start; then
  info "Update to $TAG completed successfully."
  info "Backup retained at: $BACKUP_DIR"
  echo "Logs: cd $PROJECT_DIR && docker compose logs --tail=100 bot"
else
  rollback
  exit 1
fi
