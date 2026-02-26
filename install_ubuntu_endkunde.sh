#!/usr/bin/env bash
set -euo pipefail

# End-customer installer for Ubuntu/Debian.
# Installs dependencies, prepares runtime, creates systemd service and starts it.

SERVICE_NAME="${SERVICE_NAME:-lighttracking}"
SERVICE_USER="${SERVICE_USER:-lighttrack}"
INSTALL_DIR="${INSTALL_DIR:-/opt/lighttracking}"
ENV_FILE="${ENV_FILE:-/etc/lighttracking.env}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
CONTROL_WRAPPER="/usr/local/bin/lighttracking-control"
CONTROL_DESKTOP_FILE="/usr/share/applications/lighttracking-control.desktop"

REPO_URL="${REPO_URL:-https://github.com/dvo001/LightTracker}"
REPO_BRANCH="${REPO_BRANCH:-main}"

MQTT_HOST="${MQTT_HOST:-127.0.0.1}"
MQTT_PORT="${MQTT_PORT:-1883}"
PORT="${PORT:-8000}"
LT_DB_PATH="${LT_DB_PATH:-${INSTALL_DIR}/pi/app/data/lighttracker.db}"
DMX_UART_DEVICE="${DMX_UART_DEVICE:-/dev/ttyUSB0}"
LOG_LEVEL="${LOG_LEVEL:-info}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() {
  printf '[install] %s\n' "$*"
}

fail() {
  printf '[install][error] %s\n' "$*" >&2
  exit 1
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

usage() {
  cat <<'EOF'
LightTracking Ubuntu Endkunden-Installer

Aufruf:
  sudo ./install_ubuntu_endkunde.sh
  sudo SERVICE_NAME=lighttracking INSTALL_DIR=/opt/lighttracking ./install_ubuntu_endkunde.sh

Optionen:
  -h, --help    Hilfe anzeigen

Konfiguration (via Env):
  SERVICE_NAME       (default: lighttracking)
  SERVICE_USER       (default: lighttrack)
  INSTALL_DIR        (default: /opt/lighttracking)
  ENV_FILE           (default: /etc/lighttracking.env)
  REPO_URL           (default: https://github.com/dvo001/LightTracker)
  REPO_BRANCH        (default: main)
  MQTT_HOST          (default: 127.0.0.1)
  MQTT_PORT          (default: 1883)
  PORT               (default: 8000)
  LT_DB_PATH         (default: /opt/lighttracking/pi/app/data/lighttracker.db)
  DMX_UART_DEVICE    (default: /dev/ttyUSB0)
  LOG_LEVEL          (default: info)
EOF
}

parse_args() {
  while (($#)); do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "Unbekannte Option: $1 (nutze --help)"
        ;;
    esac
  done
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fail "Bitte mit sudo/root ausfuehren."
  fi
}

check_os() {
  if [[ ! -r /etc/os-release ]]; then
    fail "/etc/os-release fehlt. Betriebssystem nicht erkannt."
  fi

  # shellcheck disable=SC1091
  . /etc/os-release
  local id_like="${ID_LIKE:-}"
  local id="${ID:-}"

  if [[ "${id}" != "ubuntu" && "${id}" != "debian" && "${id_like}" != *"debian"* ]]; then
    fail "Dieses Skript ist fuer Ubuntu/Debian gedacht (gefunden: ${id})."
  fi
}

ensure_service_user() {
  if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
    log "Erstelle Service-User ${SERVICE_USER}."
    useradd --system --home "${INSTALL_DIR}" --shell /usr/sbin/nologin --user-group --no-create-home "${SERVICE_USER}"
  else
    log "Service-User ${SERVICE_USER} existiert bereits."
  fi

  mkdir -p "${INSTALL_DIR}"
  chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"
  usermod -aG dialout "${SERVICE_USER}" || true
}

install_source_tree() {
  if [[ -f "${INSTALL_DIR}/pi/requirements.txt" ]]; then
    if [[ -d "${INSTALL_DIR}/.git" ]]; then
      log "Aktualisiere bestehendes Git-Checkout in ${INSTALL_DIR}."
      if ! runuser -u "${SERVICE_USER}" -- git -C "${INSTALL_DIR}" pull --ff-only; then
        log "Git-Update fehlgeschlagen, benutze vorhandenen Stand."
      fi
    else
      log "Quellcode in ${INSTALL_DIR} bereits vorhanden (ohne Git)."
    fi
    return
  fi

  if [[ "${SCRIPT_DIR}" == "${INSTALL_DIR}" && -f "${SCRIPT_DIR}/pi/requirements.txt" ]]; then
    log "Verwende bestehendes Checkout in ${INSTALL_DIR}."
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"
    return
  fi

  if [[ -f "${SCRIPT_DIR}/pi/requirements.txt" ]]; then
    log "Kopiere lokales Projekt von ${SCRIPT_DIR} nach ${INSTALL_DIR}."
    mkdir -p "${INSTALL_DIR}"
    tar -C "${SCRIPT_DIR}" --exclude='.git' --exclude='.venv' -cf - . | tar -C "${INSTALL_DIR}" -xf -
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"
    return
  fi

  if [[ -n "$(ls -A "${INSTALL_DIR}" 2>/dev/null || true)" ]]; then
    fail "${INSTALL_DIR} ist nicht leer und kein nutzbares Projekt wurde gefunden."
  fi

  log "Klone Repository (${REPO_BRANCH}) nach ${INSTALL_DIR}."
  runuser -u "${SERVICE_USER}" -- git clone --depth 1 --branch "${REPO_BRANCH}" "${REPO_URL}" "${INSTALL_DIR}"
}

install_system_packages() {
  log "Installiere Systempakete."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y \
    ca-certificates \
    curl \
    git \
    jq \
    policykit-1 \
    python3 \
    python3-tk \
    python3-pip \
    python3-venv \
    sqlite3 \
    mosquitto \
    mosquitto-clients \
    build-essential \
    udev

  systemctl enable --now mosquitto
}

install_python_runtime() {
  if [[ ! -f "${INSTALL_DIR}/pi/requirements.txt" ]]; then
    fail "Datei ${INSTALL_DIR}/pi/requirements.txt fehlt."
  fi

  if [[ ! -x "${INSTALL_DIR}/.venv/bin/python" ]]; then
    log "Erstelle Python venv in ${INSTALL_DIR}/.venv."
    runuser -u "${SERVICE_USER}" -- python3 -m venv "${INSTALL_DIR}/.venv"
  fi

  log "Installiere Python-Abhaengigkeiten."
  runuser -u "${SERVICE_USER}" -- "${INSTALL_DIR}/.venv/bin/python" -m ensurepip --upgrade
  runuser -u "${SERVICE_USER}" -- "${INSTALL_DIR}/.venv/bin/python" -m pip install --upgrade pip
  runuser -u "${SERVICE_USER}" -- "${INSTALL_DIR}/.venv/bin/python" -m pip install -r "${INSTALL_DIR}/pi/requirements.txt"
}

write_env_file() {
  log "Schreibe ${ENV_FILE}."
  mkdir -p "$(dirname "${ENV_FILE}")"
  cat > "${ENV_FILE}" <<EOF
LT_DB_PATH=${LT_DB_PATH}
MQTT_HOST=${MQTT_HOST}
MQTT_PORT=${MQTT_PORT}
DMX_UART_DEVICE=${DMX_UART_DEVICE}
PORT=${PORT}
LOG_LEVEL=${LOG_LEVEL}
PYTHONPATH=${INSTALL_DIR}/pi
EOF
  chmod 0644 "${ENV_FILE}"
}

write_service_file() {
  log "Schreibe ${SERVICE_FILE}."
  cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=LightTracking Service
After=network-online.target mosquitto.service
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${ENV_FILE}
Environment=PYTHONUNBUFFERED=1
ExecStart=${INSTALL_DIR}/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port \${PORT}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
  chmod 0644 "${SERVICE_FILE}"
}

install_desktop_control_app() {
  local app_py="${INSTALL_DIR}/tools/lighttracking_control_app.py"
  local desktop_src="${INSTALL_DIR}/deploy/lighttracking-control.desktop"

  if [[ ! -f "${app_py}" ]]; then
    log "Desktop-App nicht gefunden (${app_py}), ueberspringe Launcher-Installation."
    return
  fi

  log "Installiere Desktop-Control-App."
  install -D -m 0755 /dev/stdin "${CONTROL_WRAPPER}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec /usr/bin/python3 "${app_py}" --service "${SERVICE_NAME}" "\$@"
EOF

  if [[ -f "${desktop_src}" ]]; then
    install -D -m 0644 "${desktop_src}" "${CONTROL_DESKTOP_FILE}"
  else
    install -D -m 0644 /dev/stdin "${CONTROL_DESKTOP_FILE}" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=LightTracking Control
Comment=Start/Stop/Restart des LightTracking Service
Exec=${CONTROL_WRAPPER}
Icon=system-run
Terminal=false
Categories=Utility;System;
StartupNotify=true
EOF
  fi

  if command_exists update-desktop-database; then
    update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
  fi
}

prepare_data_dir() {
  local db_dir
  db_dir="$(dirname "${LT_DB_PATH}")"
  mkdir -p "${db_dir}"
  chown -R "${SERVICE_USER}:${SERVICE_USER}" "${db_dir}"
}

start_service() {
  log "Aktiviere und starte ${SERVICE_NAME}."
  systemctl daemon-reload
  systemctl enable --now "${SERVICE_NAME}"
}

print_summary() {
  printf '\n'
  log "Installation abgeschlossen."
  log "Service-Status:"
  systemctl --no-pager --full status "${SERVICE_NAME}" || true
  printf '\n'

  if command_exists curl; then
    log "API-Healthcheck:"
    if ! curl -fsS "http://127.0.0.1:${PORT}/api/v1/health"; then
      printf '\n'
      log "Healthcheck aktuell nicht erfolgreich. Bitte Logs pruefen:"
      log "journalctl -u ${SERVICE_NAME} -f"
      return
    fi
    printf '\n'
  fi

  log "Nuetzliche Befehle:"
  log "  sudo systemctl restart ${SERVICE_NAME}"
  log "  sudo systemctl status ${SERVICE_NAME}"
  log "  sudo journalctl -u ${SERVICE_NAME} -f"
  log "  ${CONTROL_WRAPPER}  (Desktop-App auch im App-Menue)"
}

main() {
  parse_args "$@"
  require_root
  check_os
  install_system_packages
  ensure_service_user
  install_source_tree
  install_python_runtime
  prepare_data_dir
  write_env_file
  write_service_file
  install_desktop_control_app
  start_service
  print_summary
}

main "$@"
