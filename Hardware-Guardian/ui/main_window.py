"""
main_window.py
──────────────
Primary application window built with CustomTkinter.

Design language: "Tactical Dashboard" – inspired by high-end PC monitoring
software.  Every colour is drawn from a tight dark palette with a single
electric-cyan accent so the UI never feels cluttered.

Layout
------
┌──────────────────────────────────────────────────────┐
│  Header (title + live clock)                         │
├──────────────┬───────────────────────────────────────┤
│  LEFT PANEL  │  RIGHT PANEL                          │
│  Hardware    │  Ergonomics & Breaks                  │
│  metrics     │  (session stats + next break timers)  │
├──────────────┴───────────────────────────────────────┤
│  Alert log (scrollable)                              │
└──────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import time
import threading
from typing import Optional

import customtkinter as ctk

from core.hardware_monitor  import HardwareMonitor, HardwareSnapshot, AlertThresholds
from core.ergonomics_manager import ErgonomicsManager, BreakEvent, BreakType, ErgonomicsConfig


# ──────────────────────────────────────────────
# Colour palette (single source of truth)
# ──────────────────────────────────────────────

PALETTE = {
    "bg_deep":     "#0D0F14",   # Deepest background
    "bg_panel":    "#13161D",   # Card / panel background
    "bg_widget":   "#1A1E28",   # Input / inner widget
    "bg_hover":    "#1F2435",
    "accent":      "#00E5FF",   # Electric cyan
    "accent_dim":  "#007A8C",
    "ok":          "#00E676",   # Green
    "warn":        "#FFD740",   # Amber
    "crit":        "#FF3D00",   # Red-orange
    "text_primary":"#E8EAF0",
    "text_muted":  "#6B7280",
    "border":      "#1E2538",
}


# ──────────────────────────────────────────────
# Reusable card widget
# ──────────────────────────────────────────────

class MetricCard(ctk.CTkFrame):
    """
    A labelled tile that shows a large value and a subtitle.
    The value colour changes based on the 'status' parameter.
    """

    STATUS_COLORS = {
        "ok":       PALETTE["ok"],
        "warn":     PALETTE["warn"],
        "critical": PALETTE["crit"],
        "neutral":  PALETTE["accent"],
    }

    def __init__(self, master, label: str, **kwargs) -> None:
        super().__init__(
            master,
            fg_color    = PALETTE["bg_panel"],
            corner_radius=12,
            border_width=1,
            border_color=PALETTE["border"],
            **kwargs,
        )

        self._label_text = ctk.CTkLabel(
            self, text=label.upper(),
            font=("Courier New", 10, "bold"),
            text_color=PALETTE["text_muted"],
        )
        self._label_text.pack(anchor="w", padx=14, pady=(10, 0))

        self._value_label = ctk.CTkLabel(
            self, text="—",
            font=("Courier New", 28, "bold"),
            text_color=PALETTE["accent"],
        )
        self._value_label.pack(anchor="w", padx=14)

        self._sub_label = ctk.CTkLabel(
            self, text="",
            font=("Courier New", 11),
            text_color=PALETTE["text_muted"],
        )
        self._sub_label.pack(anchor="w", padx=14, pady=(0, 10))

    def update(self, value: str, subtitle: str = "", status: str = "neutral") -> None:
        colour = self.STATUS_COLORS.get(status, PALETTE["accent"])
        self._value_label.configure(text=value, text_color=colour)
        self._sub_label.configure(text=subtitle)


# ──────────────────────────────────────────────
# Break notification popup
# ──────────────────────────────────────────────

class BreakPopup(ctk.CTkToplevel):
    """Modal-style window shown when a break is due."""

    ICON = {
        BreakType.EYE_BREAK:   "👁",
        BreakType.MICRO_BREAK: "🧘",
        BreakType.LONG_BREAK:  "⏸",
        BreakType.DAILY_CAP:   "⚠",
    }

    def __init__(self, master, event: BreakEvent) -> None:
        super().__init__(master)
        self.title("Break Reminder")
        self.geometry("420x260")
        self.resizable(False, False)
        self.configure(fg_color=PALETTE["bg_deep"])
        self.attributes("-topmost", True)

        icon = self.ICON.get(event.break_type, "⏱")
        ctk.CTkLabel(
            self, text=f"{icon}  {event.title}",
            font=("Courier New", 18, "bold"),
            text_color=PALETTE["accent"],
        ).pack(pady=(28, 8), padx=24)

        ctk.CTkLabel(
            self, text=event.message,
            font=("Courier New", 12),
            text_color=PALETTE["text_primary"],
            wraplength=360,
            justify="left",
        ).pack(padx=24, pady=(0, 20))

        if event.duration_secs > 0:
            self._countdown = event.duration_secs
            self._timer_label = ctk.CTkLabel(
                self, text=f"⏳  {event.duration_secs}s remaining",
                font=("Courier New", 13),
                text_color=PALETTE["warn"],
            )
            self._timer_label.pack(pady=(0, 12))
            self._tick()
        
        ctk.CTkButton(
            self, text="Got it  ✓",
            fg_color    = PALETTE["accent"],
            hover_color = PALETTE["accent_dim"],
            text_color  = "#000000",
            font        = ("Courier New", 13, "bold"),
            corner_radius=8,
            command=self.destroy,
        ).pack(pady=8)

    def _tick(self) -> None:
        if not self.winfo_exists():
            return
        if self._countdown > 0:
            self._countdown -= 1
            self._timer_label.configure(text=f"⏳  {self._countdown}s remaining")
            self.after(1000, self._tick)
        else:
            self._timer_label.configure(text="✅  Break complete!", text_color=PALETTE["ok"])


# ──────────────────────────────────────────────
# Main application window
# ──────────────────────────────────────────────

class MainWindow(ctk.CTk):
    """
    Root application window.
    Wires together HardwareMonitor and ErgonomicsManager,
    then renders their data into the UI every 2 seconds.
    """

    def __init__(self) -> None:
        super().__init__()

        # ── Window setup ──────────────────────────
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Hardware & Ergonomics Guardian")
        self.geometry("960x720")
        self.minsize(840, 640)
        self.configure(fg_color=PALETTE["bg_deep"])

        # ── Backend services ──────────────────────
        self._hw_monitor  = HardwareMonitor(
            poll_interval=2.0,
            thresholds=AlertThresholds(),
        )
        self._ergo_mgr = ErgonomicsManager(config=ErgonomicsConfig())

        # Register callbacks
        self._hw_monitor.on_snapshot(self._on_hw_snapshot)
        self._hw_monitor.on_alert(self._on_alert)
        self._ergo_mgr.on_break(self._on_break_due)

        # Latest snapshot (updated from background thread)
        self._last_snapshot: Optional[HardwareSnapshot] = None
        self._snapshot_lock = threading.Lock()

        # Alert log buffer
        self._alerts: list[str] = []

        # ── Build UI ──────────────────────────────
        self._build_ui()

        # ── Start background services ─────────────
        self._hw_monitor.start()
        self._ergo_mgr.start()

        # Periodic UI refresh (runs on main thread via .after())
        self._schedule_ui_refresh()

    # ── UI construction ──────────────────────────

    def _build_ui(self) -> None:
        self._build_header()

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=3)
        content.rowconfigure(1, weight=2)

        self._build_hardware_panel(content)
        self._build_ergonomics_panel(content)
        self._build_alert_log(content)

    def _build_header(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color=PALETTE["bg_panel"], height=64, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr, text="⚡  HARDWARE & ERGONOMICS GUARDIAN",
            font=("Courier New", 16, "bold"),
            text_color=PALETTE["accent"],
        ).pack(side="left", padx=20, pady=16)

        self._clock_label = ctk.CTkLabel(
            hdr, text="",
            font=("Courier New", 14),
            text_color=PALETTE["text_muted"],
        )
        self._clock_label.pack(side="right", padx=20)
        self._update_clock()

    def _build_hardware_panel(self, parent) -> None:
        panel = ctk.CTkFrame(parent, fg_color=PALETTE["bg_widget"], corner_radius=12)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(8, 8))

        ctk.CTkLabel(
            panel, text="◈  HARDWARE TELEMETRY",
            font=("Courier New", 12, "bold"),
            text_color=PALETTE["accent"],
        ).pack(anchor="w", padx=16, pady=(12, 4))

        # Grid of metric cards
        grid = ctk.CTkFrame(panel, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=12, pady=8)
        grid.columnconfigure((0, 1), weight=1)

        self._card_cpu_usage = MetricCard(grid, "CPU Usage")
        self._card_cpu_usage.grid(row=0, column=0, padx=4, pady=4, sticky="nsew")

        self._card_cpu_temp = MetricCard(grid, "CPU Temp")
        self._card_cpu_temp.grid(row=0, column=1, padx=4, pady=4, sticky="nsew")

        self._card_gpu_usage = MetricCard(grid, "GPU Usage")
        self._card_gpu_usage.grid(row=1, column=0, padx=4, pady=4, sticky="nsew")

        self._card_gpu_temp = MetricCard(grid, "GPU Temp")
        self._card_gpu_temp.grid(row=1, column=1, padx=4, pady=4, sticky="nsew")

        self._card_ram = MetricCard(grid, "RAM")
        self._card_ram.grid(row=2, column=0, padx=4, pady=4, sticky="nsew")

        self._card_disk = MetricCard(grid, "Primary Disk")
        self._card_disk.grid(row=2, column=1, padx=4, pady=4, sticky="nsew")

    def _build_ergonomics_panel(self, parent) -> None:
        panel = ctk.CTkFrame(parent, fg_color=PALETTE["bg_widget"], corner_radius=12)
        panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(8, 8))

        ctk.CTkLabel(
            panel, text="◈  ERGONOMICS & HEALTH",
            font=("Courier New", 12, "bold"),
            text_color=PALETTE["accent"],
        ).pack(anchor="w", padx=16, pady=(12, 4))

        grid = ctk.CTkFrame(panel, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=12, pady=8)
        grid.columnconfigure((0, 1), weight=1)

        self._card_session   = MetricCard(grid, "Session Time")
        self._card_session.grid(row=0, column=0, padx=4, pady=4, sticky="nsew")

        self._card_daily     = MetricCard(grid, "Daily Total")
        self._card_daily.grid(row=0, column=1, padx=4, pady=4, sticky="nsew")

        self._card_eye_break = MetricCard(grid, "Next Eye Break")
        self._card_eye_break.grid(row=1, column=0, padx=4, pady=4, sticky="nsew")

        self._card_micro     = MetricCard(grid, "Next Micro Break")
        self._card_micro.grid(row=1, column=1, padx=4, pady=4, sticky="nsew")

        self._card_long      = MetricCard(grid, "Next Long Break")
        self._card_long.grid(row=2, column=0, padx=4, pady=4, sticky="nsew")

        self._card_breaks_taken = MetricCard(grid, "Eye Breaks Taken")
        self._card_breaks_taken.grid(row=2, column=1, padx=4, pady=4, sticky="nsew")

    def _build_alert_log(self, parent) -> None:
        log_frame = ctk.CTkFrame(parent, fg_color=PALETTE["bg_panel"], corner_radius=12)
        log_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 0))

        ctk.CTkLabel(
            log_frame, text="◈  ALERT LOG",
            font=("Courier New", 12, "bold"),
            text_color=PALETTE["warn"],
        ).pack(anchor="w", padx=16, pady=(10, 4))

        self._alert_log = ctk.CTkTextbox(
            log_frame,
            fg_color    = PALETTE["bg_widget"],
            text_color  = PALETTE["text_primary"],
            font        = ("Courier New", 11),
            corner_radius=8,
            state="disabled",
        )
        self._alert_log.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # ── UI refresh ───────────────────────────────

    def _schedule_ui_refresh(self) -> None:
        self._refresh_ui()
        self.after(2000, self._schedule_ui_refresh)

    def _refresh_ui(self) -> None:
        with self._snapshot_lock:
            snap = self._last_snapshot

        if snap:
            self._refresh_hardware(snap)

        self._refresh_ergonomics()

    def _refresh_hardware(self, snap: HardwareSnapshot) -> None:
        # CPU
        if snap.cpu:
            cpu = snap.cpu
            usage_status = (
                "critical" if cpu.usage_percent >= 90
                else "warn" if cpu.usage_percent >= 70
                else "ok"
            )
            self._card_cpu_usage.update(
                f"{cpu.usage_percent:.1f}%",
                f"{cpu.frequency_mhz:.0f} MHz  •  {cpu.core_count} cores",
                usage_status,
            )
            if cpu.temperature_celsius > 0:
                temp_status = (
                    "critical" if cpu.temperature_celsius >= 90
                    else "warn" if cpu.temperature_celsius >= 75
                    else "ok"
                )
                self._card_cpu_temp.update(
                    f"{cpu.temperature_celsius:.1f}°C",
                    status=temp_status,
                )
            else:
                self._card_cpu_temp.update("N/A", "Sensor unavailable", "neutral")

        # GPU
        if snap.gpus:
            gpu = snap.gpus[0]
            self._card_gpu_usage.update(
                f"{gpu.usage_percent:.1f}%",
                gpu.name[:28],
            )
            temp_status = (
                "critical" if gpu.temperature_celsius >= 95
                else "warn" if gpu.temperature_celsius >= 80
                else "ok"
            )
            self._card_gpu_temp.update(f"{gpu.temperature_celsius:.1f}°C", status=temp_status)
        else:
            self._card_gpu_usage.update("N/A", "No GPU detected")
            self._card_gpu_temp.update("N/A")

        # RAM
        if snap.ram:
            ram = snap.ram
            status = "critical" if ram.usage_percent >= 90 else "warn" if ram.usage_percent >= 80 else "ok"
            self._card_ram.update(
                f"{ram.usage_percent:.1f}%",
                f"{ram.used_gb:.1f} / {ram.total_gb:.1f} GB",
                status,
            )

        # Disk
        if snap.disks:
            d = snap.disks[0]
            status = "critical" if d.health_status == "CRITICAL" else "warn" if d.health_status == "WARNING" else "ok"
            self._card_disk.update(
                f"{d.usage_percent:.1f}%",
                f"{d.free_gb:.1f} GB free  •  {d.path}",
                status,
            )

    def _refresh_ergonomics(self) -> None:
        stats = self._ergo_mgr.stats
        fmt   = ErgonomicsManager.format_duration

        self._card_session.update(fmt(stats.total_session_secs))
        daily_status = "warn" if stats.total_daily_secs >= 8 * 3600 else "neutral"
        self._card_daily.update(fmt(stats.total_daily_secs), status=daily_status)
        self._card_eye_break.update(fmt(stats.next_eye_break_in))
        self._card_micro.update(fmt(stats.next_micro_break_in))
        self._card_long.update(fmt(stats.next_long_break_in))
        self._card_breaks_taken.update(str(stats.eye_breaks_taken))

    # ── Clock ─────────────────────────────────────

    def _update_clock(self) -> None:
        now = time.strftime("%Y-%m-%d   %H:%M:%S")
        self._clock_label.configure(text=now)
        self.after(1000, self._update_clock)

    # ── Callbacks from background threads ─────────

    def _on_hw_snapshot(self, snap: HardwareSnapshot) -> None:
        """Called from the HardwareMonitor thread; store snapshot safely."""
        with self._snapshot_lock:
            self._last_snapshot = snap

    def _on_alert(self, message: str) -> None:
        """Log hardware alerts to the alert panel (thread-safe via .after)."""
        self.after(0, lambda: self._append_alert(message))

    def _on_break_due(self, event: BreakEvent) -> None:
        """Show a break popup on the main thread."""
        self.after(0, lambda: self._show_break_popup(event))

    def _append_alert(self, message: str) -> None:
        timestamp = time.strftime("[%H:%M:%S]")
        line = f"{timestamp}  {message}\n"
        self._alert_log.configure(state="normal")
        self._alert_log.insert("end", line)
        self._alert_log.see("end")
        self._alert_log.configure(state="disabled")

    def _show_break_popup(self, event: BreakEvent) -> None:
        popup = BreakPopup(self, event)
        popup.grab_set()
