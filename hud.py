#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import font as tkfont
import psutil
import subprocess
import os
import time
import re
import signal
import sys

COLOR_TEXTO = "#39FF14"
UPDATE_MS = 500
MARGEN_X = 10
MARGEN_Y = 10

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


class HUD(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HUD")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="black")
        self.attributes("-alpha", 0.85)

        self.fuente = tkfont.Font(family="Liberation Mono", size=10, weight="bold")

        self.label = tk.Label(self, text="Iniciando...", font=self.fuente,
                              fg=COLOR_TEXTO, bg="black")
        self.label.pack(padx=6, pady=2)

        self.bind("<Button-1>", self._start_drag)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Button-3>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())

        self._drag_x = 0
        self._drag_y = 0
        self._dragging = False

        self.collector = DataCollector()
        self._update()

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
            s = f"C:{cpu_pct:.0f}%"
            if cpu_ghz is not None:
                s += f"@{cpu_ghz:.1f}G"
            if cpu_temp is not None:
                s += f"|{cpu_temp:.0f}C"
            parts.append(s)
        except Exception:
            parts.append("C:--")

        try:
            _, used_gb, total_gb = self.collector.ram()
            parts.append(f"R:{used_gb:.1f}/{total_gb:.1f}G")
        except Exception:
            parts.append("R:--")

        try:
            nv_u, nv_t, nv_p = self.collector.nvidia()
            if nv_u is not None:
                s = f"N:{nv_u:.0f}%"
                if nv_t is not None:
                    s += f"|{nv_t:.0f}C"
                if nv_p is not None:
                    s += f"|{nv_p:.1f}W"
                parts.append(s)
            else:
                parts.append("N:--")
        except Exception:
            parts.append("N:--")

        try:
            amd_u, amd_t = self.collector.amd()
            if amd_u is not None or amd_t is not None:
                s = "A:"
                if amd_u is not None:
                    s += f"{amd_u:.0f}%"
                else:
                    s += "--%"
                if amd_t is not None:
                    s += f"|{amd_t:.0f}C"
                parts.append(s)
            else:
                parts.append("A:--")
        except Exception:
            parts.append("A:--")

        try:
            rr = self.collector.refresh_rate()
            if rr:
                parts.append(f"D:{rr:.0f}Hz")
            else:
                parts.append("D:--")
        except Exception:
            parts.append("D:--")

        text = " | ".join(parts)
        self.label.config(text=text)
        self.label.update_idletasks()

        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = sw - w - MARGEN_X
        y = sh - h - MARGEN_Y
        self.geometry(f"+{x}+{y}")

        self.after(UPDATE_MS, self._update)


def _sig(signum, frame):
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)
    app = HUD()
    app.mainloop()
