#!/usr/bin/env bash
set -euo pipefail

# install-backup-timer.sh
# Copia las unidades systemd de `contrib/systemd` a /etc/systemd/system y las habilita.

if [[ $EUID -ne 0 ]]; then
  echo "This script requires root. Re-run with sudo." >&2
  exit 1
fi

ROOT_DIR="/opt/cognito-stack"
SRC_DIR="${ROOT_DIR}/contrib/systemd"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "Source systemd files not found at $SRC_DIR" >&2
  exit 2
fi

echo "Installing systemd units from $SRC_DIR to /etc/systemd/system"
cp "$SRC_DIR"/*.service /etc/systemd/system/
cp "$SRC_DIR"/*.timer /etc/systemd/system/

echo "Reloading systemd daemon and enabling timer"
systemctl daemon-reload
systemctl enable --now cognito-backup.timer

echo "Installed and enabled cognito-backup.timer"
