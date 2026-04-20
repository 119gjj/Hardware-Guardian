"""
hardware_monitor.py
───────────────────
Real-time hardware telemetry engine.

Polls CPU, GPU, RAM and disk metrics at a configurable interval,
exposes them as typed dataclasses and fires callbacks when any
reading exceeds a configured threshold.

Dependencies: psutil, GPUtil (optional – gracefully degrades when absent)
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import psutil

# GPUtil is optional; GPU metrics are skipped if the library is absent.
try:
    import GPUtil
    _GPUTIL_AVAILABLE = True
except ImportError:
    _GPUTIL_AVAILABLE = False


# ──────────────────────────────────────────────
# Data models
# ──────────────────────────────────────────────

@dataclass
class CpuMetrics:
    usage_percent: float          # 0-100 %
    temperature_celsius: float    # -1 when unavailable
    frequency_mhz: float
    core_count: int


@dataclass
class GpuMetrics:
    name: str
    usage_percent: float
    temperature_celsius: float
    vram_used_mb: float
    vram_total_mb: float


@dataclass
class RamMetrics:
    total_gb: float
    used_gb: float
    available_gb: float
    usage_percent: float


@dataclass
class DiskMetrics:
    path: str
    total_gb: float
    used_gb: float
    free_gb: float
    usage_percent: float
    health_status: str            # "OK" | "WARNING" | "CRITICAL"


@dataclass
class HardwareSnapshot:
    """A complete point-in-time snapshot of all monitored hardware."""
    timestamp: float = field(default_factory=time.time)
    cpu: CpuMetrics = None
    gpus: List[GpuMetrics] = field(default_factory=list)
    ram: RamMetrics = None
    disks: List[DiskMetrics] = field(default_factory=list)


# ──────────────────────────────────────────────
# Threshold configuration
# ──────────────────────────────────────────────

@dataclass
class AlertThresholds:
    cpu_temp_warning:  float = 75.0   # °C
    cpu_temp_critical: float = 90.0
    gpu_temp_warning:  float = 80.0
    gpu_temp_critical: float = 95.0
    ram_usage_warning: float = 80.0   # %
    disk_usage_warning: float = 85.0


# ──────────────────────────────────────────────
# Monitor class
# ──────────────────────────────────────────────

class HardwareMonitor:
    """
    Background polling engine that collects hardware metrics and
    notifies registered listeners via callbacks.

    Usage
    -----
    >>> monitor = HardwareMonitor(poll_interval=2.0)
    >>> monitor.on_snapshot(lambda snap: print(snap.cpu.usage_percent))
    >>> monitor.on_alert(lambda msg: print("ALERT:", msg))
    >>> monitor.start()
    """

    def __init__(
        self,
        poll_interval: float = 2.0,
        thresholds: Optional[AlertThresholds] = None,
    ) -> None:
        self._interval   = poll_interval
        self._thresholds = thresholds or AlertThresholds()

        # Registered callbacks
        self._snapshot_callbacks: List[Callable[[HardwareSnapshot], None]] = []
        self._alert_callbacks:    List[Callable[[str], None]]              = []

        self._thread: Optional[threading.Thread] = None
        self._running = False

    # ── Public API ──────────────────────────────

    def on_snapshot(self, callback: Callable[[HardwareSnapshot], None]) -> None:
        """Register a function to be called with every new HardwareSnapshot."""
        self._snapshot_callbacks.append(callback)

    def on_alert(self, callback: Callable[[str], None]) -> None:
        """Register a function to be called whenever a threshold is breached."""
        self._alert_callbacks.append(callback)

    def start(self) -> None:
        """Begin background polling in a daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the polling thread gracefully."""
        self._running = False

    def get_snapshot(self) -> HardwareSnapshot:
        """Return a single, immediate hardware snapshot (blocking)."""
        return self._collect()

    # ── Internal helpers ─────────────────────────

    def _poll_loop(self) -> None:
        while self._running:
            snapshot = self._collect()
            self._dispatch_snapshot(snapshot)
            self._check_thresholds(snapshot)
            time.sleep(self._interval)

    def _collect(self) -> HardwareSnapshot:
        return HardwareSnapshot(
            cpu   = self._collect_cpu(),
            gpus  = self._collect_gpus(),
            ram   = self._collect_ram(),
            disks = self._collect_disks(),
        )

    def _collect_cpu(self) -> CpuMetrics:
        usage = psutil.cpu_percent(interval=None)
        freq  = psutil.cpu_freq()
        temp  = self._read_cpu_temperature()

        return CpuMetrics(
            usage_percent        = usage,
            temperature_celsius  = temp,
            frequency_mhz        = freq.current if freq else 0.0,
            core_count           = psutil.cpu_count(logical=True),
        )

    @staticmethod
    def _read_cpu_temperature() -> float:
        """
        Try several psutil sensor keys used across different platforms.
        Returns -1.0 if temperature data is unavailable.
        """
        try:
            sensors = psutil.sensors_temperatures()
            if not sensors:
                return -1.0
            # Key priority: coretemp (Intel), k10temp (AMD), cpu_thermal (ARM)
            for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz"):
                if key in sensors:
                    readings = sensors[key]
                    if readings:
                        return readings[0].current
        except (AttributeError, NotImplementedError):
            pass
        return -1.0

    @staticmethod
    def _collect_gpus() -> List[GpuMetrics]:
        if not _GPUTIL_AVAILABLE:
            return []
        try:
            gpus = GPUtil.getGPUs()
            return [
                GpuMetrics(
                    name                 = g.name,
                    usage_percent        = g.load * 100,
                    temperature_celsius  = g.temperature,
                    vram_used_mb         = g.memoryUsed,
                    vram_total_mb        = g.memoryTotal,
                )
                for g in gpus
            ]
        except Exception:
            return []

    @staticmethod
    def _collect_ram() -> RamMetrics:
        vm = psutil.virtual_memory()
        gb = 1024 ** 3
        return RamMetrics(
            total_gb     = vm.total     / gb,
            used_gb      = vm.used      / gb,
            available_gb = vm.available / gb,
            usage_percent= vm.percent,
        )

    @staticmethod
    def _collect_disks() -> List[DiskMetrics]:
        disks = []
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except PermissionError:
                continue
            pct = usage.percent
            health = (
                "CRITICAL" if pct >= 95
                else "WARNING" if pct >= 85
                else "OK"
            )
            gb = 1024 ** 3
            disks.append(DiskMetrics(
                path          = partition.mountpoint,
                total_gb      = usage.total / gb,
                used_gb       = usage.used  / gb,
                free_gb       = usage.free  / gb,
                usage_percent = pct,
                health_status = health,
            ))
        return disks

    def _dispatch_snapshot(self, snap: HardwareSnapshot) -> None:
        for cb in self._snapshot_callbacks:
            try:
                cb(snap)
            except Exception as exc:
                print(f"[HardwareMonitor] snapshot callback error: {exc}")

    def _check_thresholds(self, snap: HardwareSnapshot) -> None:
        t = self._thresholds
        alerts = []

        # CPU temperature
        if snap.cpu and snap.cpu.temperature_celsius > 0:
            cpu_t = snap.cpu.temperature_celsius
            if cpu_t >= t.cpu_temp_critical:
                alerts.append(f"🔴 CRITICAL — CPU temperature {cpu_t:.1f}°C (limit {t.cpu_temp_critical}°C)")
            elif cpu_t >= t.cpu_temp_warning:
                alerts.append(f"🟡 WARNING — CPU temperature {cpu_t:.1f}°C (limit {t.cpu_temp_warning}°C)")

        # GPU temperature
        for gpu in snap.gpus:
            if gpu.temperature_celsius >= t.gpu_temp_critical:
                alerts.append(f"🔴 CRITICAL — GPU '{gpu.name}' at {gpu.temperature_celsius:.1f}°C")
            elif gpu.temperature_celsius >= t.gpu_temp_warning:
                alerts.append(f"🟡 WARNING — GPU '{gpu.name}' at {gpu.temperature_celsius:.1f}°C")

        # RAM usage
        if snap.ram and snap.ram.usage_percent >= t.ram_usage_warning:
            alerts.append(f"🟡 WARNING — RAM usage {snap.ram.usage_percent:.1f}% (limit {t.ram_usage_warning}%)")

        # Disk health
        for disk in snap.disks:
            if disk.health_status != "OK":
                alerts.append(
                    f"{'🔴' if disk.health_status == 'CRITICAL' else '🟡'} "
                    f"{disk.health_status} — Disk '{disk.path}' at {disk.usage_percent:.1f}%"
                )

        for msg in alerts:
            for cb in self._alert_callbacks:
                try:
                    cb(msg)
                except Exception as exc:
                    print(f"[HardwareMonitor] alert callback error: {exc}")
