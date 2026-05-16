#!/usr/bin/env bash
# Run as root on the Pi. Assumes:
# - repo is checked out at /opt/algoro
# - Python 3.11+, pip, unbound, dnscrypt-proxy are installed
set -euo pipefail

INSTALL_DIR=/opt/algoro/firmware
DATA_DIR=/var/lib/algoro

echo "==> Installing Python package..."
pip install -e "$INSTALL_DIR"

echo "==> Creating data directory..."
mkdir -p "$DATA_DIR"

echo "==> Initialising database..."
python3 -c "
from pathlib import Path
from algoro.db import init_db
import os
os.environ['ALGORO_DB_PATH'] = '/var/lib/algoro/algoro.db'
init_db(Path('/var/lib/algoro/algoro.db'))
"

echo "==> Installing systemd units..."
cp "$INSTALL_DIR/systemd/algoro-admin.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable algoro-admin
systemctl start algoro-admin

echo "==> Done. Admin UI running at http://$(hostname -I | awk '{print $1}')"
echo "    Set your router's DNS server to that IP."
