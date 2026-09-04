#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Survival Search — install script for Debian/Ubuntu-based LXC containers
# ---------------------------------------------------------------------------

APP_USER="survival-search"
APP_DIR="/opt/survival-search"
DATA_DIR="/var/lib/survival-search"
REPO_URL="https://github.com/survivalful/survival-search.git"
SERVICE_NAME="survival-search"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# --- 1. Must run as root -------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run as root." >&2
    exit 1
fi

# --- 2. System dependencies ----------------------------------------------------
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl

# --- 3. Dedicated system user --------------------------------------------------
echo "[2/7] Creating system user '${APP_USER}'..."
if ! id -u "${APP_USER}" &>/dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "${APP_USER}"
    echo "      User created."
else
    echo "      User already exists, skipping."
fi

# --- 4. Clone repository -------------------------------------------------------
echo "[3/7] Cloning repository to ${APP_DIR}..."
if [ ! -d "${APP_DIR}/.git" ]; then
    git clone "${REPO_URL}" "${APP_DIR}"
else
    echo "      Directory already exists, pulling latest..."
    git -C "${APP_DIR}" pull
fi

# --- 5. Python virtual environment --------------------------------------------
echo "[4/7] Setting up Python virtual environment..."
if [ ! -d "${APP_DIR}/.venv" ]; then
    python3 -m venv "${APP_DIR}/.venv"
fi

echo "[5/7] Installing Python dependencies..."
"${APP_DIR}/.venv/bin/pip" install --quiet --upgrade pip
"${APP_DIR}/.venv/bin/pip" install --quiet -r "${APP_DIR}/requirements.txt"
"${APP_DIR}/.venv/bin/pip" install --quiet -r "${APP_DIR}/requirements-server.txt"

# --- 6. Persistent data directory ---------------------------------------------
echo "[6/7] Creating persistent data directory ${DATA_DIR}..."
mkdir -p "${DATA_DIR}"
chown "${APP_USER}:${APP_USER}" "${DATA_DIR}"
chmod 750 "${DATA_DIR}"

# Create settings.yml from example if it doesn't exist yet
if [ ! -f "${APP_DIR}/searx/settings.yml" ]; then
    cp "${APP_DIR}/searx/settings.example.yml" "${APP_DIR}/searx/settings.yml"
fi

# Fix userdb path in settings.yml (idempotent)
sed -i 's|userdb_path: "/tmp/searxng_users.db"|userdb_path: "/var/lib/survival-search/users.db"|' \
    "${APP_DIR}/searx/settings.yml"

chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

# --- 7. systemd service -------------------------------------------------------
echo "[7/7] Installing systemd service..."
cat > "${SERVICE_FILE}" << 'EOF'
[Unit]
Description=Survival Search
After=network.target

[Service]
User=survival-search
Group=survival-search
WorkingDirectory=/opt/survival-search
ExecStart=/opt/survival-search/.venv/bin/python -m searx.webapp
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

# --- Done ---------------------------------------------------------------------
echo ""
echo "============================================================"
echo " Installation complete!"
echo "============================================================"
echo ""
echo " Next steps:"
echo "   1. Edit /opt/survival-search/searx/settings.yml"
echo "      - Set your OIDC credentials (oidc.enable, discovery_url,"
echo "        client_id, client_secret)"
echo "      - Set a strong secret_key"
echo "      - Set server.bind_address to 0.0.0.0 for external access"
echo ""
echo "   2. Start the service:"
echo "      systemctl start survival-search"
echo ""
echo "   3. Check status / logs:"
echo "      systemctl status survival-search"
echo "      journalctl -u survival-search -f"
echo "============================================================"
