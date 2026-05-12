#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Linux Floating HUD - PyQt6 + XCB (transparencia real)
Una linea, esquina inferior derecha, fondo transparente.
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import sys
import time
import re
import subprocess
import signal

import psutil
from PyQt6.QtWidgets import QApplication, QWidget, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

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


class HUD(QWidget):
    def __init__(self):
        super().__init__()
        self.collector = DataCollector()
        self._build_ui()
        self._update()

    def _build_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        font = QFont("Liberation Mono", 10)
        font.setBold(True)
        font.setStyleHint(QFont.StyleHint.Monospace)

        self.label = QLabel("HUD...")
        self.label.setFont(font)
        self.label.setStyleSheet(f"""
            color: {COLOR_TEXTO};
            background-color: transparent;
            padding: 2px 8px;
        """)
        self.label.setParent(self)
        self.label.move(0, 0)

        screen = QApplication.primaryScreen().geometry()
        self._screen_w = screen.width()
        self._screen_h = screen.height()

        self._drag_pos = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update)
        self.timer.start(UPDATE_MS)

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
        self.label.setText(text)
        self.label.adjustSize()
        self.resize(self.label.size())

        x = self._screen_w - self.width() - MARGEN_X
        y = self._screen_h - self.height() - MARGEN_Y
        self.move(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()


def _sig(signum, frame):
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)
    app = QApplication(sys.argv)
    hud = HUD()
    hud.show()
    sys.exit(app.exec())
