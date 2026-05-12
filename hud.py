#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HUD Flotante para Ubuntu - Monitor de Sistema en Tiempo Real
Autor: Asistente AI

Muestra en tiempo real:
  - CPU: uso % y temperatura
  - RAM: uso %
  - GPU NVIDIA (RTX 5060): uso %, temperatura, potencia W
  - GPU AMD (Radeon 780M): uso % y temperatura
  - DISPLAY: refresh rate nativo del monitor (Hz)

Nota: En Linux, obtener los FPS reales de una aplicación/juego requiere
inyección en su pipeline gráfico (como MangoHud). Este HUD muestra el
refresh rate del monitor como la métrica más fiable disponible sin root.

Controles:
  - Arrastrar con click izquierdo para mover
  - Click derecho o tecla Escape para cerrar
  - Doble click izquierdo para alternar esquina
"""

import tkinter as tk
from tkinter import font as tkfont
import psutil
import subprocess
import os
import time
import re
import signal
import sys

# ---------------------------------------------------------------------------
# CONFIGURACIÓN VISUAL
# ---------------------------------------------------------------------------
COLOR_TEXTO = "#39FF14"          # Verde neón/fosforescente
COLOR_ALERTA = "#FF3333"       # Rojo brillante para alertas
COLOR_ADVERTENCIA = "#FFAA00"  # Naranja para valores medios-altos
COLOR_FONDO = "black"          # Debe coincidir con el usado en widgets
FUENTE_NOMBRE = ("Liberation Mono", "DejaVu Sans Mono", "Noto Mono", "Consolas", "monospace")
FUENTE_TAMANIO = 14
INTERVALO_MS = 500             # Actualización cada 500 ms
ANCHO_VENTANA = 400
ALTO_VENTANA = 170
POS_X_INICIAL = None           # None = esquina superior derecha
POS_Y_INICIAL = 40

# ---------------------------------------------------------------------------
# UTILIDADES HARDWARE
# ---------------------------------------------------------------------------
def detectar_amd_card():
    """Busca la tarjeta AMD (vendor 0x1002) en /sys/class/drm/."""
    base = "/sys/class/drm"
    if not os.path.isdir(base):
        return None
    for entrada in sorted(os.listdir(base)):
        if entrada.startswith("card") and "-" not in entrada:
            vendor_path = os.path.join(base, entrada, "device", "vendor")
            try:
                with open(vendor_path, "r") as f:
                    vendor = f.read().strip()
                if vendor == "0x1002":
                    return os.path.join(base, entrada, "device")
            except Exception:
                continue
    return None


def detectar_nvidia():
    """Verifica si nvidia-smi está disponible en PATH."""
    try:
        subprocess.run(["nvidia-smi"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True, timeout=3)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# RECOLECTOR DE DATOS
# ---------------------------------------------------------------------------
class RecolectorDatos:
    def __init__(self):
        self.amd_path = detectar_amd_card()
        self.tiene_nvidia = detectar_nvidia()
        self._refresh_rate = None
        self._last_refresh_check = 0

        # Intentar cargar pynvml (opcional, más rápido que nvidia-smi)
        self.pynvml = None
        try:
            import pynvml
            pynvml.nvmlInit()
            self.pynvml = pynvml
            self.nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            pass

    # --- CPU ---
    def get_cpu(self):
        uso = psutil.cpu_percent(interval=None)
        temp = None
        try:
            temps = psutil.sensors_temperatures()
            if "k10temp" in temps:
                temp = temps["k10temp"][0].current
            elif "coretemp" in temps:
                temp = temps["coretemp"][0].current
            else:
                for nombre, lista in temps.items():
                    if nombre in ("nvme", "amdgpu", "acpitz"):
                        continue
                    if lista:
                        temp = lista[0].current
                        break
        except Exception:
            pass
        return uso, temp

    # --- RAM ---
    def get_ram(self):
        return psutil.virtual_memory().percent

    # --- NVIDIA ---
    def get_nvidia(self):
        if not self.tiene_nvidia:
            return None, None, None

        if self.pynvml:
            try:
                util = self.pynvml.nvmlDeviceGetUtilizationRates(self.nvml_handle)
                temp = self.pynvml.nvmlDeviceGetTemperature(
                    self.nvml_handle, self.pynvml.NVML_TEMPERATURE_GPU)
                power = self.pynvml.nvmlDeviceGetPowerUsage(self.nvml_handle) / 1000.0
                return util.gpu, temp, power
            except Exception:
                pass

        try:
            salida = subprocess.check_output(
                ["nvidia-smi",
                 "--query-gpu=utilization.gpu,temperature.gpu,power.draw",
                 "--format=csv,noheader,nounits"],
                text=True, timeout=2
            ).strip()
            partes = [p.strip() for p in salida.split(",")]
            return float(partes[0]), float(partes[1]), float(partes[2])
        except Exception:
            return None, None, None

    # --- AMD ---
    def get_amd(self):
        if not self.amd_path:
            return None, None

        uso = None
        temp = None

        try:
            with open(os.path.join(self.amd_path, "gpu_busy_percent"), "r") as f:
                uso = float(f.read().strip())
        except Exception:
            pass

        try:
            hwmon_dir = os.path.join(self.amd_path, "hwmon")
            for entry in os.listdir(hwmon_dir):
                temp_path = os.path.join(hwmon_dir, entry, "temp1_input")
                if os.path.exists(temp_path):
                    with open(temp_path, "r") as f:
                        temp = float(f.read().strip()) / 1000.0
                    break
        except Exception:
            try:
                temps = psutil.sensors_temperatures()
                if "amdgpu" in temps:
                    temp = temps["amdgpu"][0].current
            except Exception:
                pass

        return uso, temp

    # --- Refresh Rate del monitor ---
    def get_refresh_rate(self):
        ahora = time.time()
        if self._refresh_rate is not None and (ahora - self._last_refresh_check) < 5:
            return self._refresh_rate

        try:
            salida = subprocess.check_output(["xrandr", "--current"],
                                             text=True, timeout=2)
            for linea in salida.splitlines():
                if "*" in linea:
                    match = re.search(r'(\d+\.?\d*)\*', linea)
                    if match:
                        self._refresh_rate = float(match.group(1))
                        self._last_refresh_check = ahora
                        return self._refresh_rate
        except Exception:
            pass

        try:
            salida = subprocess.check_output(
                ["nvidia-settings", "-q", "RefreshRate", "-t"],
                text=True, timeout=2
            ).strip()
            self._refresh_rate = float(salida)
            self._last_refresh_check = ahora
            return self._refresh_rate
        except Exception:
            pass

        return None


# ---------------------------------------------------------------------------
# HUD CON TKINTER + TRANSPARENCIA X11
# ---------------------------------------------------------------------------
class HUD(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("System HUD")

        ancho_pantalla = self.winfo_screenwidth()
        x = POS_X_INICIAL if POS_X_INICIAL is not None else (ancho_pantalla - ANCHO_VENTANA - 20)
        y = POS_Y_INICIAL
        self.geometry(f"{ANCHO_VENTANA}x{ALTO_VENTANA}+{x}+{y}")

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=COLOR_FONDO)

        self.fuente = tkfont.Font(family=FUENTE_NOMBRE, size=FUENTE_TAMANIO, weight="bold")

        self.canvas = tk.Canvas(
            self, width=ANCHO_VENTANA, height=ALTO_VENTANA,
            bg=COLOR_FONDO, highlightthickness=0
        )
        self.canvas.pack()

        # Etiquetas estáticas
        y_pos = 12
        esp = 28
        self.canvas.create_text(12, y_pos, text="CPU:", fill=COLOR_TEXTO,
                                font=self.fuente, anchor="nw")
        y_pos += esp
        self.canvas.create_text(12, y_pos, text="RAM:", fill=COLOR_TEXTO,
                                font=self.fuente, anchor="nw")
        y_pos += esp
        self.canvas.create_text(12, y_pos, text="GPU1 (NVIDIA):", fill=COLOR_TEXTO,
                                font=self.fuente, anchor="nw")
        y_pos += esp
        self.canvas.create_text(12, y_pos, text="GPU2 (AMD):", fill=COLOR_TEXTO,
                                font=self.fuente, anchor="nw")
        y_pos += esp
        self.canvas.create_text(12, y_pos, text="DISPLAY:", fill=COLOR_TEXTO,
                                font=self.fuente, anchor="nw")

        # Valores dinámicos
        y_pos = 12
        self.text_cpu = self.canvas.create_text(ANCHO_VENTANA - 12, y_pos,
                                                text="--", fill=COLOR_TEXTO,
                                                font=self.fuente, anchor="ne")
        y_pos += esp
        self.text_ram = self.canvas.create_text(ANCHO_VENTANA - 12, y_pos,
                                                text="--", fill=COLOR_TEXTO,
                                                font=self.fuente, anchor="ne")
        y_pos += esp
        self.text_nv = self.canvas.create_text(ANCHO_VENTANA - 12, y_pos,
                                               text="--", fill=COLOR_TEXTO,
                                               font=self.fuente, anchor="ne")
        y_pos += esp
        self.text_amd = self.canvas.create_text(ANCHO_VENTANA - 12, y_pos,
                                                text="--", fill=COLOR_TEXTO,
                                                font=self.fuente, anchor="ne")
        y_pos += esp
        self.text_disp = self.canvas.create_text(ANCHO_VENTANA - 12, y_pos,
                                                 text="--", fill=COLOR_TEXTO,
                                                 font=self.fuente, anchor="ne")

        self._aplicar_transparencia_x11()

        self.bind("<Button-1>", self._iniciar_arrastre)
        self.bind("<B1-Motion>", self._arrastrar)
        self.bind("<Button-3>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Double-Button-1>", self._alternar_esquina)

        self._offset_x = 0
        self._offset_y = 0
        self._arrastrando = False

        self.recolector = RecolectorDatos()
        self._actualizar()

    def _aplicar_transparencia_x11(self):
        """Usa X11 (ctypes) para hacer transparente el fondo de la ventana y el canvas."""
        try:
            from ctypes import cdll
            x11 = cdll.LoadLibrary("libX11.so.6")

            self.update_idletasks()
            display = x11.XOpenDisplay(None)
            if not display:
                return

            root_id = self.winfo_id()
            x11.XSetWindowBackgroundPixmap(display, root_id, 0)
            x11.XClearWindow(display, root_id)

            canvas_id = self.canvas.winfo_id()
            x11.XSetWindowBackgroundPixmap(display, canvas_id, 0)
            x11.XClearWindow(display, canvas_id)

            x11.XFlush(display)
            x11.XCloseDisplay(display)
        except Exception:
            pass

    def _iniciar_arrastre(self, evento):
        self._offset_x = evento.x
        self._offset_y = evento.y
        self._arrastrando = True

    def _arrastrar(self, evento):
        if self._arrastrando:
            x = self.winfo_x() + evento.x - self._offset_x
            y = self.winfo_y() + evento.y - self._offset_y
            self.geometry(f"+{x}+{y}")

    def _alternar_esquina(self, evento):
        ancho = self.winfo_screenwidth()
        if self.winfo_x() > ancho // 2:
            self.geometry(f"+20+{self.winfo_y()}")
        else:
            self.geometry(f"+{ancho - ANCHO_VENTANA - 20}+{self.winfo_y()}")

    def _color(self, valor, normal=COLOR_TEXTO, adv=COLOR_ADVERTENCIA,
               alerta=COLOR_ALERTA, umbral_adv=70, umbral_alt=85):
        if valor is None:
            return normal
        if valor >= umbral_alt:
            return alerta
        if valor >= umbral_adv:
            return adv
        return normal

    def _actualizar(self):
        try:
            cpu_uso, cpu_temp = self.recolector.get_cpu()
            cpu_str = f"{cpu_uso:5.1f}%"
            if cpu_temp is not None:
                cpu_str += f"  |  {cpu_temp:.0f}°C"
            self.canvas.itemconfig(self.text_cpu, text=cpu_str, fill=self._color(cpu_uso))
        except Exception:
            pass

        try:
            ram_uso = self.recolector.get_ram()
            self.canvas.itemconfig(self.text_ram, text=f"{ram_uso:5.1f}%",
                                   fill=self._color(ram_uso))
        except Exception:
            pass

        try:
            nv_uso, nv_temp, nv_power = self.recolector.get_nvidia()
            if nv_uso is not None:
                nv_str = f"{nv_uso:5.1f}%"
                if nv_temp is not None:
                    nv_str += f"  |  {nv_temp:.0f}°C"
                if nv_power is not None:
                    nv_str += f"  |  {nv_power:.1f} W"
                self.canvas.itemconfig(self.text_nv, text=nv_str,
                                       fill=self._color(nv_uso))
            else:
                self.canvas.itemconfig(self.text_nv, text="No detectada", fill="#666666")
        except Exception:
            pass

        try:
            amd_uso, amd_temp = self.recolector.get_amd()
            if amd_uso is not None or amd_temp is not None:
                amd_str = f"{amd_uso:5.1f}%" if amd_uso is not None else "  --%"
                if amd_temp is not None:
                    amd_str += f"  |  {amd_temp:.0f}°C"
                self.canvas.itemconfig(self.text_amd, text=amd_str,
                                       fill=self._color(amd_uso))
            else:
                self.canvas.itemconfig(self.text_amd, text="No detectada", fill="#666666")
        except Exception:
            pass

        try:
            rr = self.recolector.get_refresh_rate()
            if rr:
                self.canvas.itemconfig(self.text_disp, text=f"{rr:.1f} Hz", fill=COLOR_TEXTO)
            else:
                self.canvas.itemconfig(self.text_disp, text="-- Hz", fill="#666666")
        except Exception:
            pass

        self.after(INTERVALO_MS, self._actualizar)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def _signal_handler(signum, frame):
    print(f"\nSeñal {signum} recibida. Cerrando HUD...")
    sys.exit(0)


if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        print("=" * 60)
        print("ERROR: Falta la biblioteca 'psutil'.")
        print("Instálala con:  sudo apt install python3-psutil")
        print("=" * 60)
        raise SystemExit(1)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    app = HUD()
    app.mainloop()
