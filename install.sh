#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
ZIP_URL="https://roshd.roshdcollection.ir/sanaei-telegram-bot-final.zip"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() {
    echo -e "${GREEN}[+]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

error() {
    echo -e "${RED}[x]${NC} $1"
    exit 1
}

if [[ "${EUID}" -ne 0 ]]; then
    error "This script must be run as root."
fi

if [[ ! -f /etc/os-release ]]; then
    error "Operating system could not be detected."
fi

source /etc/os-release

if [[ "${ID}" != "ubuntu" ]]; then
    warn "This script is designed for Ubuntu."
fi

info "Operating system: ${PRETTY_NAME}"
info "Project directory: ${PROJECT_DIR}"

echo

cat <<'EOF'
╔════════════════════════════════════════════╗
║       Sanaei Telegram Bot Installer        ║
╠════════════════════════════════════════════╣
║                                            ║
║  Channel   : @roshdcollection              ║
║  Last Update: 2026-10-09                   ║
║                                            ║
╚════════════════════════════════════════════╝
EOF

info "Starting Sanaei Telegram Bot installation..."
echo

echo "Please select an option:"
echo
echo "1) New Installation"
echo "2) Update Bot"
echo

read -r -p "Enter your choice [1-2]: " INSTALL_MODE </dev/tty

case "$INSTALL_MODE" in
    1)
        info "New installation selected."
        ;;
    2)
        info "Bot update selected."
        ;;
    *)
        error "Invalid choice. Please select 1 or 2."
        ;;
esac

echo

echo

if command -v unzip >/dev/null 2>&1; then
    info "unzip is already installed."
else
    info "unzip is not installed; installing..."
    apt-get update
    apt-get install -y unzip
    info "unzip installed successfully."
fi

if command -v docker >/dev/null 2>&1; then
    info "Docker is already installed."
else
    info "Docker is not installed; installing..."

    apt-get update
    apt-get install -y docker.io docker-compose-v2

    systemctl enable --now docker

    info "Docker installed successfully."
fi

if docker compose version >/dev/null 2>&1; then
    info "Docker Compose is ready."
else
    error "Docker Compose is not available."
fi

echo

KEEP_EXISTING_ENV=false

if [[ "$INSTALL_MODE" == "2" ]]; then
    if [[ ! -f "$ENV_FILE" ]]; then
        error "No existing .env found. Update mode requires an existing installation."
    fi

    KEEP_EXISTING_ENV=true
    info "Update mode selected. Existing configuration will be kept."

echo
info "Downloading latest bot version..."

TMP_DIR="$(mktemp -d)"
ZIP_FILE="$TMP_DIR/bot.zip"

if ! curl -fsSL "$ZIP_URL" -o "$ZIP_FILE"; then
    rm -rf "$TMP_DIR"
    error "Failed to download the latest bot version."
fi

info "Latest bot version downloaded."

info "Updating bot files..."

unzip -o "$ZIP_FILE" -d "$TMP_DIR/extracted" >/dev/null

cp "$TMP_DIR/extracted/bot.py" "$PROJECT_DIR/bot.py"
cp "$TMP_DIR/extracted/config.py" "$PROJECT_DIR/config.py"
cp "$TMP_DIR/extracted/database.py" "$PROJECT_DIR/database.py"
cp "$TMP_DIR/extracted/sanaei.py" "$PROJECT_DIR/sanaei.py"
cp "$TMP_DIR/extracted/utils.py" "$PROJECT_DIR/utils.py"
cp "$TMP_DIR/extracted/requirements.txt" "$PROJECT_DIR/requirements.txt"
cp "$TMP_DIR/extracted/Dockerfile" "$PROJECT_DIR/Dockerfile"
cp "$TMP_DIR/extracted/docker-compose.yml" "$PROJECT_DIR/docker-compose.yml"

rm -rf "$TMP_DIR"

info "Bot files updated successfully."

elif [[ -f "$ENV_FILE" ]]; then
    warn ".env already exists."

    read -r -p "Keep existing configuration? [Y/n]: " KEEP_ENV </dev/tty

    if [[ ! "$KEEP_ENV" =~ ^[Nn]$ ]]; then
        KEEP_EXISTING_ENV=true
        info "Existing configuration will be kept."
    else
        info "Existing configuration will be replaced."
    fi
fi

if [[ "$KEEP_EXISTING_ENV" == false ]]; then

    echo
    info "Bot configuration"

    read -r -p "Telegram Bot Token: " BOT_TOKEN </dev/tty
    read -r -p "Sanaei Panel URL: " PANEL_URL </dev/tty
    read -r -p "Sanaei API Token: " PANEL_API_TOKEN </dev/tty
    read -r -p "Sanaei Username: " PANEL_USERNAME </dev/tty
    read -r -p "Sanaei Password: " PANEL_PASSWORD </dev/tty
    read -r -p "Telegram Card Number: " CARD_NUMBER </dev/tty
    read -r -p "Admin Telegram ID(s), comma separated: " ADMIN_IDS </dev/tty

    echo
    info "Initial plan prices"

    read -r -p "500GB price (Toman) [480000]: " PLAN_500_PRICE </dev/tty
    read -r -p "1000GB price (Toman) [970000]: " PLAN_1000_PRICE </dev/tty

    PLAN_500_PRICE="${PLAN_500_PRICE:-480000}"
    PLAN_1000_PRICE="${PLAN_1000_PRICE:-970000}"

    cat > "$ENV_FILE" <<EOF
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

    chmod 600 "$ENV_FILE"
    chown root:root "$ENV_FILE"

    info ".env created successfully."

else
    info "Using existing .env configuration."
fi

if [[ -f "$PROJECT_DIR/.env.example" ]]; then
    info ".env.example found."
else
    warn ".env.example not found."
fi

echo

DATA_DIR="$PROJECT_DIR/data"

if [[ ! -d "$DATA_DIR" ]]; then
    mkdir -p "$DATA_DIR"
    info "data directory created."
else
    info "data directory already exists."
fi

chmod 700 "$DATA_DIR"

REQUIRED_FILES=(
    "bot.py"
    "config.py"
    "database.py"
    "sanaei.py"
    "utils.py"
    "requirements.txt"
    "Dockerfile"
    "docker-compose.yml"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$PROJECT_DIR/$file" ]]; then
        error "Required file not found: $file"
    fi
done

info "All required project files are present."

echo

cd "$PROJECT_DIR"

info "Validating Docker Compose configuration..."

if ! docker compose config >/dev/null; then
    error "docker-compose.yml is invalid."
fi

info "Docker Compose configuration is valid."

echo

info "Building Docker image..."

if ! docker compose build bot; then
    error "Docker image build failed."
fi

info "Docker image built successfully."

echo

info "Starting/updating the bot..."

if ! docker compose up -d bot; then
    error "Failed to start the bot."
fi

info "Bot container started."

echo

info "Initializing database..."

if ! docker compose exec -T bot python3 -c \
'import asyncio; from database import init_db; asyncio.run(init_db())'
then
    error "Database initialization failed."
fi

info "Database initialized successfully."

echo

info "Checking bot status..."

docker compose ps

echo

sleep 3

if docker compose ps --status running --services | grep -qx "bot"; then
    info "Bot is running successfully."
else
    error "Bot container is not running. Check the logs with:"
    echo
    echo "docker compose logs --tail=100 bot"
fi

echo

info "Sanaei Telegram Bot installation/update completed successfully."

echo
info "Useful commands:"
echo "  docker compose logs --tail=100 bot"
echo "  docker compose restart bot"
echo "  docker compose ps"
