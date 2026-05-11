#!/usr/bin/env bash
# Run as root on the Pi. Assumes:
# - repo is checked out at /opt/slopstop
# - Python 3.11+, pip, unbound, dnscrypt-proxy are installed
set -euo pipefail

INSTALL_DIR=/opt/slopstop/firmware
DATA_DIR=/var/lib/slopstop

echo "==> Installing Python package..."
pip install -e "$INSTALL_DIR"

echo "==> Creating data directory..."
mkdir -p "$DATA_DIR"

echo "==> Initialising database..."
python3 -c "
from pathlib import Path
from slopstop.db import init_db
import os
os.environ['SLOPSTOP_DB_PATH'] = '/var/lib/slopstop/slopstop.db'
init_db(Path('/var/lib/slopstop/slopstop.db'))
"

echo "==> Installing systemd units..."
cp "$INSTALL_DIR/systemd/slopstop-admin.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable slopstop-admin
systemctl start slopstop-admin

echo "==> Done. Admin UI running at http://$(hostname -I | awk '{print $1}')"
echo "    Set your router's DNS server to that IP."
