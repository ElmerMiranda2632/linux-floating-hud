# 🖥️ Linux Floating HUD

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Linux-orange.svg)](https://www.kernel.org/)

> **HUD flotante transparente** para Linux (Ubuntu/Debian) con monitoreo en tiempo real de CPU, RAM, GPU NVIDIA/AMD y refresh rate del monitor.

![preview](https://img.shields.io/badge/Estilo-Cyberpunk%20%7C%20Verde%20Neón-39FF14)

## ✨ Características

| Métrica | Fuente de datos | Detalle |
|---------|----------------|---------|
| **CPU** | `psutil` + `k10temp` | Uso % y temperatura (optimizado para AMD Ryzen) |
| **RAM** | `psutil` | Porcentaje de uso total |
| **GPU NVIDIA** | `nvidia-smi` / `pynvml` | Uso %, temperatura y **potencia en vatios** (W) |
| **GPU AMD** | `sysfs` (`/sys/class/drm/`) | Uso % y temperatura vía drivers amdgpu |
| **Display** | `xrandr` | Refresh rate nativo del monitor en Hz |

### 🎨 Aspecto visual

- ✅ Fondo **completamente transparente** (vía X11 ctypes)
- ✅ Texto **verde neón fosforescente** (`#39FF14`)
- ✅ Ventana **sin bordes** y **siempre encima**
- ✅ Colores de alerta: naranja/rojo para valores críticos (>70% / >85%)
- ✅ Arrastrable con el mouse
- ✅ Doble click para cambiar de esquina

---

## 🚀 Instalación rápida

### 1. Clonar o descargar

```bash
git clone https://github.com/ElmerMiranda2632/linux-floating-hud.git
cd linux-floating-hud
```

### 2. Dependencias obligatorias

```bash
sudo apt update
sudo apt install python3-psutil
```

### 3. Dependencia opcional (recomendada)

```bash
pip3 install --user nvidia-ml-py
```

> Si no instalas `nvidia-ml-py`, el HUD usará `nvidia-smi` como fallback. Funciona igual, pero crear un subproceso cada 500 ms consume ligeramente más recursos.

### 4. Iniciar

```bash
python3 hud.py
```

---

## 🔧 Inicio automático (systemd)

El proyecto incluye un **servicio de systemd user** para que el HUD inicie automáticamente con tu sesión y se mantenga siempre activo (se reinicia si se cierra accidentalmente).

```bash
# Copiar servicio
mkdir -p ~/.config/systemd/user
cp systemd/hud.service ~/.config/systemd/user/

# Habilitar e iniciar
systemctl --user daemon-reload
systemctl --user enable --now hud.service
```

### Controlar el servicio

```bash
./hud-ctl status     # Ver estado
./hud-ctl stop       # Detener temporalmente
./hud-ctl start      # Iniciar ahora
./hud-ctl restart    # Reiniciar
./hud-ctl disable    # Desactivar inicio automático
./hud-ctl logs       # Ver logs en tiempo real
```

### Autostart de escritorio (alternativa)

```bash
mkdir -p ~/.config/autostart
cp autostart/hud-system.desktop ~/.config/autostart/
```

---

## 🎮 Controles

| Acción | Resultado |
|--------|-----------|
| 🖱️ Click izquierdo + arrastrar | Mover el HUD |
| 🖱️🖱️ Doble click izquierdo | Alternar entre esquina izquierda/derecha |
| 🖱️ Click derecho | Cerrar ventana *(systemd la reinicia en 3s)* |
| ⌨️ `Escape` | Cerrar ventana *(systemd la reinicia en 3s)* |

> 💡 **Tip**: Para cerrar el HUD permanentemente sin que systemd lo reinicie, ejecuta `./hud-ctl stop`.

---

## 📁 Estructura del proyecto

```
linux-floating-hud/
├── hud.py                  # Script principal (PyQt6/Tkinter + monitoreo)
├── hud-wrapper.sh          # Wrapper que espera al entorno gráfico
├── hud-ctl                 # Script de control (start/stop/status/logs)
├── install_deps.sh         # Instalador de dependencias
├── systemd/
│   └── hud.service         # Unidad systemd user
├── autostart/
│   └── hud-system.desktop  # Entrada de autostart para GNOME/KDE
└── README.md               # Este archivo
```

---

## 🐧 Requisitos del sistema

| Componente | Requisito |
|------------|-----------|
| **OS** | Linux con X11 o XWayland (Ubuntu 22.04+ recomendado) |
| **Python** | >= 3.8 |
| **GPU NVIDIA** | Drivers propietarios con `nvidia-smi` en PATH |
| **GPU AMD** | Drivers `amdgpu` con sysfs expuesto |
| **Compositor** | Cualquier compositor moderno (Mutter, KWin, Picom, etc.) |

---

## 🛠️ Personalización

Edita las constantes al inicio de `hud.py`:

```python
COLOR_TEXTO = "#39FF14"       # Verde neón
COLOR_ALERTA = "#FF3333"      # Rojo crítico
COLOR_ADVERTENCIA = "#FFAA00" # Naranja medio
FUENTE_TAMANIO = 14           # Tamaño de fuente
INTERVALO_MS = 500            # Frecuencia de actualización
POS_X_INICIAL = None          # None = esquina superior derecha
POS_Y_INICIAL = 40
```

---

## 📌 Nota sobre "FPS"

En Linux, medir los **FPS reales de una aplicación/juego específico** requiere inyección en su pipeline de renderizado (como hacen [MangoHud](https://github.com/flightlessmango/MangoHud) o el Steam Overlay).

Este HUD muestra el **refresh rate nativo del monitor** (Hz) vía `xrandr`, que es la métrica más fiable y útil disponible sin privilegios de root ni hooks gráficos invasivos.

---

## 📜 Licencia

MIT © [ElmerMiranda2632](https://github.com/ElmerMiranda2632)
