#!/usr/bin/env bash
HUD_SCRIPT="/home/coreas/linux-floating-hud/hud.py"
MAX_ESPERA=30

esperar_display() {
    local c=0
    while [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ]; do
        sleep 1
        c=$((c + 1))
        if [ "$c" -ge "$MAX_ESPERA" ]; then
            echo "[HUD] Timeout esperando entorno grafico" >&2
            exit 1
        fi
    done
}

esperar_display

if [ -n "$DISPLAY" ]; then
    c=0
    while ! xset q &>/dev/null; do
        sleep 1
        c=$((c + 1))
        if [ "$c" -ge "$MAX_ESPERA" ]; then
            echo "[HUD] Timeout esperando X11" >&2
            exit 1
        fi
    done
fi

export QT_QPA_PLATFORM=xcb
exec python3 "$HUD_SCRIPT"
