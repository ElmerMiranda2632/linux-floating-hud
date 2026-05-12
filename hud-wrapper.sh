#!/usr/bin/env bash
# Wrapper para iniciar el HUD asegurando que el entorno gráfico esté listo

HUD_SCRIPT="/home/coreas/hud-system/hud.py"
MAX_ESPERA=30  # segundos máximos de espera

esperar_display() {
    local contador=0
    while [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ]; do
        sleep 1
        contador=$((contador + 1))
        if [ "$contador" -ge "$MAX_ESPERA" ]; then
            echo "[HUD] Timeout esperando entorno gráfico" >&2
            exit 1
        fi
    done
    echo "[HUD] Display detectado: DISPLAY=$DISPLAY WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
}

# Esperar a que el compositor esté activo (solo en X11 por ahora)
esperar_display

# Si hay X11, verificar que responda
if [ -n "$DISPLAY" ]; then
    contador=0
    while ! xset q &>/dev/null; do
        sleep 1
        contador=$((contador + 1))
        if [ "$contador" -ge "$MAX_ESPERA" ]; then
            echo "[HUD] Timeout esperando servidor X11" >&2
            exit 1
        fi
    done
fi

# Iniciar HUD
echo "[HUD] Iniciando HUD..."
exec python3 "$HUD_SCRIPT"
