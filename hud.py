#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Linux Floating HUD - Tkinter + X11 transparency
Una sola linea, esquina inferior derecha, fondo transparente.
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
from ctypes import cdll

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
COLOR_TEXTO = "#39FF14"
COLOR_ALERTA = "#FF3333"
COLOR_ADVERTENCIA = "#FFAA00"
UPDATE_MS = 500
MARGEN_X = 20
MARGEN_Y = 20

# ---------------------------------------------------------------------------
# DATA COLLECTORS
# ---------------------------------------------------------------------------
class DataCollector:
    def __init__(self):
        self.amd_path = self._find_amd_card()
        self.has_nvidia = self._has_nvidia()
        self._refresh_rate = None
        self._refresh_ts = 0
        self.pynvml = None
        try:
            import pynvml
            pynvml.nvmlInit()
            self.pynvml = pynvml
            self.nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            pass

    def _find_amd_card(self):
        base = "/sys/class/drm"
        if not os.path.isdir(base):
            return None
        for ent in sorted(os.listdir(base)):
            if ent.startswith("card") and "-" not in ent:
                try:
                    with open(os.path.join(base, ent, "device", "vendor")) as f:
                        if f.read().strip() == "0x1002":
                            return os.path.join(base, ent, "device")
                except Exception:
                    pass
        return None

    def _has_nvidia(self):
        try:
            subprocess.run(["nvidia-smi"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True, timeout=3)
            return True
        except Exception:
            return False

    def cpu(self):
        pct = psutil.cpu_percent(interval=None)
        temp = None
        freq_ghz = None
        try:
            f = psutil.cpu_freq()
            if f:
                freq_ghz = f.current / 1000.0
        except Exception:
            pass
        try:
            temps = psutil.sensors_temperatures()
            if "k10temp" in temps:
                temp = temps["k10temp"][0].current
            elif "coretemp" in temps:
                temp = temps["coretemp"][0].current
            else:
                for name, lst in temps.items():
                    if name in ("nvme", "amdgpu", "acpitz"):
                        continue
                    if lst:
                        temp = lst[0].current
                        break
        except Exception:
            pass
        return pct, freq_ghz, temp

    def ram(self):
        mem = psutil.virtual_memory()
        used_gb = mem.used / (1024 ** 3)
        total_gb = mem.total / (1024 ** 3)
        return mem.percent, used_gb, total_gb

    def nvidia(self):
        if not self.has_nvidia:
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
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu,power.draw",
                 "--format=csv,noheader,nounits"], text=True, timeout=2
            ).strip()
            parts = [p.strip() for p in out.split(",")]
            return float(parts[0]), float(parts[1]), float(parts[2])
        except Exception:
            return None, None, None

    def amd(self):
        if not self.amd_path:
            return None, None
        uso = None
        temp = None
        try:
            with open(os.path.join(self.amd_path, "gpu_busy_percent")) as f:
                uso = float(f.read().strip())
        except Exception:
            pass
        try:
            hw = os.path.join(self.amd_path, "hwmon")
            for e in os.listdir(hw):
                tp = os.path.join(hw, e, "temp1_input")
                if os.path.exists(tp):
                    with open(tp) as f:
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

    def refresh_rate(self):
        now = time.time()
        if self._refresh_rate is not None and (now - self._refresh_ts) < 5:
            return self._refresh_rate
        try:
            out = subprocess.check_output(["xrandr", "--current"], text=True, timeout=2)
            for line in out.splitlines():
                if "*" in line:
                    m = re.search(r'(\d+\.?\d*)\*', line)
                    if m:
                        self._refresh_rate = float(m.group(1))
                        self._refresh_ts = now
                        return self._refresh_rate
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# HUD
# ---------------------------------------------------------------------------
class HUD(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("System HUD")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="black")

        self.fuente = tkfont.Font(family="Liberation Mono", size=12, weight="bold")

        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0, height=30)
        self.canvas.pack(fill="both", expand=True)

        self.text_id = self.canvas.create_text(10, 15, text="Iniciando...",
                                               fill=COLOR_TEXTO, font=self.fuente,
                                               anchor="w")

        self.bind("<Button-1>", self._start_drag)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Button-3>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())

        self._drag_x = 0
        self._drag_y = 0
        self._dragging = False

        self.collector = DataCollector()

        # Aplicar transparencia X11
        self.after(100, self._apply_transparency)

        self._update()

    def _apply_transparency(self):
        try:
            x11 = cdll.LoadLibrary("libX11.so.6")
            self.update_idletasks()
            dpy = x11.XOpenDisplay(None)
            if not dpy:
                return

            root_id = self.winfo_id()
            x11.XSetWindowBackgroundPixmap(dpy, root_id, 0)
            x11.XClearWindow(dpy, root_id)

            canvas_id = self.canvas.winfo_id()
            x11.XSetWindowBackgroundPixmap(dpy, canvas_id, 0)
            x11.XClearWindow(dpy, canvas_id)

            x11.XFlush(dpy)
            x11.XCloseDisplay(dpy)
        except Exception:
            pass

    def _start_drag(self, ev):
        self._drag_x = ev.x
        self._drag_y = ev.y
        self._dragging = True

    def _drag(self, ev):
        if self._dragging:
            x = self.winfo_x() + ev.x - self._drag_x
            y = self.winfo_y() + ev.y - self._drag_y
            self.geometry(f"+{x}+{y}")

    def _update(self):
        parts = []

        try:
            cpu_pct, cpu_ghz, cpu_temp = self.collector.cpu()
            s = f"CPU: {cpu_pct:4.1f}%"
            if cpu_ghz is not None:
                s += f" @ {cpu_ghz:.1f}GHz"
            if cpu_temp is not None:
                s += f" | {cpu_temp:.0f}C"
            parts.append(s)
        except Exception:
            parts.append("CPU: --")

        try:
            ram_pct, used_gb, total_gb = self.collector.ram()
            parts.append(f"RAM: {used_gb:.1f}/{total_gb:.1f}GB")
        except Exception:
            parts.append("RAM: --")

        try:
            nv_u, nv_t, nv_p = self.collector.nvidia()
            if nv_u is not None:
                s = f"NVIDIA: {nv_u:.0f}%"
                if nv_t is not None:
                    s += f" | {nv_t:.0f}C"
                if nv_p is not None:
                    s += f" | {nv_p:.1f}W"
                parts.append(s)
            else:
                parts.append("NVIDIA: --")
        except Exception:
            parts.append("NVIDIA: --")

        try:
            amd_u, amd_t = self.collector.amd()
            if amd_u is not None or amd_t is not None:
                s = "AMD:"
                if amd_u is not None:
                    s += f" {amd_u:.0f}%"
                else:
                    s += " --%"
                if amd_t is not None:
                    s += f" | {amd_t:.0f}C"
                parts.append(s)
            else:
                parts.append("AMD: --")
        except Exception:
            parts.append("AMD: --")

        try:
            rr = self.collector.refresh_rate()
            if rr:
                parts.append(f"DISP: {rr:.1f}Hz")
            else:
                parts.append("DISP: --")
        except Exception:
            parts.append("DISP: --")

        text = "  |  ".join(parts)
        self.canvas.itemconfig(self.text_id, text=text)

        # Medir ancho y posicionar en esquina inferior derecha
        bbox = self.canvas.bbox(self.text_id)
        if bbox:
            w = bbox[2] - bbox[0] + 20
            h = 30
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = sw - w - MARGEN_X
            y = sh - h - MARGEN_Y
            self.geometry(f"{w}x{h}+{x}+{y}")
            self.canvas.config(width=w, height=h)
            self.canvas.coords(self.text_id, 10, h // 2)

        self.after(UPDATE_MS, self._update)


def _sig(signum, frame):
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)
    app = HUD()
    app.mainloop()
