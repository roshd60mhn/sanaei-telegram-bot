
#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

VERSION="2.0.0"
TAG="v${VERSION}"
REPO="roshd60mhn/sanaei-telegram-bot"
PROJECT_DIR="/opt/sanaei-telegram-bot"
BACKUP_ROOT="/opt/sanaei-telegram-bot-backups"
RELEASE_URL="https://github.com/${REPO}/archive/refs/tags/${TAG}.tar.gz"

info() { printf '[+] %s\n' "$*"; }
die()  { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

[[ "$EUID" -eq 0 ]] || die "Run as root."
[[ -f "$PROJECT_DIR/.env" ]] || die "Existing .env not found."
[[ -d "$PROJECT_DIR/data" ]] || die "Existing data directory not found."
[[ -f "$PROJECT_DIR/data/bot.db" ]] || die "Database not found."
command -v docker >/dev/null || die "Docker is not installed."
docker compose version >/dev/null 2>&1 || die "Docker Compose is unavailable."
command -v curl >/dev/null || die "curl is not installed."
command -v tar >/dev/null || die "tar is not installed."

cd "$PROJECT_DIR"

read -r -p "Update this installation to ${TAG}? Type YES to continue: " CONFIRM </dev/tty
[[ "$CONFIRM" == "YES" ]] || die "Cancelled."

TMP_DIR="$(mktemp -d)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/${STAMP}"
mkdir -p "$BACKUP_DIR/old-files" "$BACKUP_DIR/data"
chmod 700 "$BACKUP_ROOT" "$BACKUP_DIR"

SUCCESS=0
ROLLBACK_NEEDED=0
CONTAINER_WAS_RUNNING=0

cleanup() {
    rc=$?
    if [[ "$SUCCESS" -ne 1 && "$ROLLBACK_NEEDED" -eq 1 ]]; then
        echo "[!] Update failed; attempting rollback..."
        docker compose down >/dev/null 2>&1 || true

        for f in bot.py config.py database.py sanaei.py utils.py requirements.txt Dockerfile docker-compose.yml VERSION .env.example; do
            if [[ -f "$BACKUP_DIR/old-files/$f" ]]; then
                cp -p "$BACKUP_DIR/old-files/$f" "$PROJECT_DIR/$f"
            elif [[ "$f" != ".env.example" && "$f" != "VERSION" ]]; then
                rm -f "$PROJECT_DIR/$f"
            fi
        done

        if [[ -d "$BACKUP_DIR/data" ]]; then
            rm -rf "$PROJECT_DIR/data"
            cp -a "$BACKUP_DIR/data" "$PROJECT_DIR/data"
        fi

        if [[ -f "$BACKUP_DIR/old-files/.env" ]]; then
            cp -p "$BACKUP_DIR/old-files/.env" "$PROJECT_DIR/.env"
        fi

        docker compose build bot >/dev/null 2>&1 || true
        if [[ "$CONTAINER_WAS_RUNNING" -eq 1 ]]; then
            docker compose up -d bot >/dev/null 2>&1 || true
        fi
        echo "[!] Rollback attempted. Inspect logs and backup at: $BACKUP_DIR"
    fi
    rm -rf "$TMP_DIR"
    exit "$rc"
}
trap cleanup EXIT

info "Downloading ${TAG}..."
curl -fsSL --retry 3 "$RELEASE_URL" -o "$TMP_DIR/release.tar.gz"
mkdir "$TMP_DIR/source"
tar -xzf "$TMP_DIR/release.tar.gz" -C "$TMP_DIR/source" --strip-components=1

[[ -f "$TMP_DIR/source/VERSION" ]] || die "VERSION file missing."
[[ "$(tr -d '[:space:]' < "$TMP_DIR/source/VERSION")" == "$VERSION" ]] ||
    die "Archive version does not match ${VERSION}."

FILES=(bot.py config.py database.py sanaei.py utils.py requirements.txt Dockerfile docker-compose.yml VERSION .env.example)
for f in "${FILES[@]}"; do
    [[ -f "$TMP_DIR/source/$f" ]] || {
        [[ "$f" == ".env.example" ]] || die "Release file missing: $f"
    }
done

info "Backing up current code, configuration and database..."
for f in bot.py config.py database.py sanaei.py utils.py requirements.txt Dockerfile docker-compose.yml VERSION .env.example .env; do
    [[ -f "$PROJECT_DIR/$f" ]] && cp -p "$PROJECT_DIR/$f" "$BACKUP_DIR/old-files/$f"
done
cp -a "$PROJECT_DIR/data/." "$BACKUP_DIR/data/"
chmod 600 "$BACKUP_DIR/old-files/.env"
tar -czf "$BACKUP_DIR/full-backup.tar.gz" -C "$PROJECT_DIR" \
    .env data bot.py config.py database.py sanaei.py utils.py requirements.txt Dockerfile docker-compose.yml
chmod 600 "$BACKUP_DIR/full-backup.tar.gz"

if docker compose ps --status running --services | grep -qx bot; then
    CONTAINER_WAS_RUNNING=1
fi

info "Stopping bot..."
docker compose down
ROLLBACK_NEEDED=1

info "Installing release files..."
for f in bot.py config.py database.py sanaei.py utils.py requirements.txt Dockerfile docker-compose.yml VERSION; do
    install -m 0644 "$TMP_DIR/source/$f" "$PROJECT_DIR/$f"
done
if [[ -f "$TMP_DIR/source/.env.example" ]]; then
    install -m 0644 "$TMP_DIR/source/.env.example" "$PROJECT_DIR/.env.example"
fi
chmod 600 "$PROJECT_DIR/.env"
chmod 700 "$PROJECT_DIR/data"

info "Validating Compose..."
docker compose config -q

info "Building image..."
docker compose build --pull bot

info "Starting bot..."
docker compose up -d bot

info "Checking container..."
sleep 5
docker compose ps --status running --services | grep -qx bot ||
    die "Bot is not running."

SUCCESS=1
ROLLBACK_NEEDED=0
info "Update to ${TAG} completed."
echo "Backup: $BACKUP_DIR"
echo "Logs: cd $PROJECT_DIR && docker compose logs --tail=100 bot"

