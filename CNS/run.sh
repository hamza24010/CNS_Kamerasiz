#!/bin/bash
set -euo pipefail

APP_DIR="/opt/CNS"
VENV_DIR="$APP_DIR/venv"
PY="$VENV_DIR/bin/python"
[ -x "$PY" ] || PY="/usr/bin/python3"

ARCH="$(dpkg --print-architecture 2>/dev/null || echo arm64)"
if [ "$ARCH" = "arm64" ]; then
  export QT_QPA_PLATFORM_PLUGIN_PATH="/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms"
else
  export QT_QPA_PLATFORM_PLUGIN_PATH="/usr/lib/arm-linux-gnueabihf/qt5/plugins/platforms"
fi


exec "$PY" "$APP_DIR/mainS.py"
