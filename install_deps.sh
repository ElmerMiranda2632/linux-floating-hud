#!/usr/bin/env bash
set -e

echo "=== Instalando dependencias del HUD ==="

# psutil (obligatorio)
if python3 -c "import psutil" 2>/dev/null; then
    echo "[OK] psutil ya está instalado"
else
    echo "[+] Instalando psutil..."
    sudo apt update
    sudo apt install -y python3-psutil
fi

# pynvml (opcional, recomendado)
if python3 -c "import pynvml" 2>/dev/null; then
    echo "[OK] pynvml ya está instalado"
else
    echo "[+] Instalando pynvml (nvidia-ml-py)..."
    pip3 install --user nvidia-ml-py || pip3 install nvidia-ml-py
fi

echo "=== Verificación ==="
python3 -c "import psutil; print('psutil:', psutil.__version__)"
python3 -c "import pynvml; print('pynvml: OK')" 2>/dev/null || echo "pynvml: No instalado (se usará nvidia-smi como fallback)"

echo "=== Listo. Ejecuta: python3 hud.py ==="
