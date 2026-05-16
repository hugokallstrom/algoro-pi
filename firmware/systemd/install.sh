#!/usr/bin/env bash
# Run as root on the Pi. Assumes:
# - repo is checked out at /opt/algoro
# - Python 3.11+, python3-venv, unbound, dnscrypt-proxy are installed
set -euo pipefail

INSTALL_DIR=/opt/algoro/firmware
DATA_DIR=/var/lib/algoro
VENV=/opt/algoro/venv

echo "==> Creating virtualenv..."
python3 -m venv "$VENV"

echo "==> Installing Python package..."
"$VENV/bin/pip" install -e "$INSTALL_DIR"

echo "==> Creating data directory..."
mkdir -p "$DATA_DIR"

echo "==> Initialising database..."
"$VENV/bin/python" -c "
from pathlib import Path
from algoro.db import init_db
init_db(Path('/var/lib/algoro/algoro.db'))
"

echo "==> Installing systemd units..."
ln -sf "$INSTALL_DIR/systemd/algoro-admin.service" /etc/systemd/system/algoro-admin.service
systemctl daemon-reload
systemctl enable algoro-admin
systemctl start algoro-admin

echo "==> Done. Admin UI running at http://$(hostname -I | awk '{print $1}')"
echo "    Set your router's DNS server to that IP."
