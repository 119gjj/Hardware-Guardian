"""
ergonomics_manager.py
─────────────────────
Tracks user screen time and enforces healthy usage patterns.

Implements:
  • 20-20-20 rule  — every 20 min, look 20 ft away for 20 sec
  • Micro-breaks    — 5-minute rest every 60 minutes
  • Long breaks     — 15-minute rest every 2 hours
  • Daily cap alert — warning when daily usage reaches a configurable limit

All timers run in a background thread and fire callbacks so the UI
layer can decide how to present notifications (toast, modal, sound…).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, List, Optional


# ──────────────────────────────────────────────
# Break types
# ──────────────────────────────────────────────

class BreakType(Enum):
    EYE_BREAK   = auto()   # 20-20-20 rule
    MICRO_BREAK = auto()   # Short posture / stretch break
    LONG_BREAK  = auto()   # Full rest period
    DAILY_CAP   = auto()   # Daily screen-time limit reached


@dataclass
class BreakEvent:
    """Payload emitted when a break is due."""
    break_type:    BreakType
    title:         str
    message:       str
    duration_secs: int          # Recommended break length in seconds
    timestamp:     float = field(default_factory=time.time)


# ──────────────────────────────────────────────
# Schedule configuration
# ──────────────────────────────────────────────

@dataclass
class ErgonomicsConfig:
    # 20-20-20 rule interval (seconds). Default: 20 minutes.
    eye_break_interval:   int = 20 * 60

    # Short break after every N minutes of continuous use.
    micro_break_interval: int = 60 * 60   # 60 min

    # Long break interval (seconds).
    long_break_interval:  int = 2 * 60 * 60  # 2 hours

    # Daily screen time cap in seconds. Default: 11 hours.
    daily_cap_secs:       int = 11 * 60 * 60

    # Duration of each break type (seconds)
    eye_break_duration:   int = 20
    micro_break_duration: int = 5 * 60
    long_break_duration:  int = 15 * 60


# ──────────────────────────────────────────────
# Session statistics
# ──────────────────────────────────────────────

@dataclass
class SessionStats:
    session_start:        float = field(default_factory=time.time)
    total_session_secs:   float = 0.0
    total_daily_secs:     float = 0.0
    eye_breaks_taken:     int   = 0
    micro_breaks_taken:   int   = 0
    long_breaks_taken:    int   = 0
    next_eye_break_in:    float = 0.0   # seconds remaining
    next_micro_break_in:  float = 0.0
    next_long_break_in:   float = 0.0


# ──────────────────────────────────────────────
# Manager class
# ──────────────────────────────────────────────

class ErgonomicsManager:
    """
    Tracks active screen time and schedules break reminders.

    Usage
    -----
    >>> mgr = ErgonomicsManager()
    >>> mgr.on_break(lambda evt: print(evt.title, evt.message))
    >>> mgr.start()
    """

    def __init__(self, config: Optional[ErgonomicsConfig] = None) -> None:
        self._cfg = config or ErgonomicsConfig()

        # Callbacks registered by the UI layer
        self._break_callbacks: List[Callable[[BreakEvent], None]] = []

        # Internal counters (seconds since last break/session start)
        self._elapsed_since_eye:   float = 0.0
        self._elapsed_since_micro: float = 0.0
        self._elapsed_since_long:  float = 0.0
        self._daily_elapsed:       float = 0.0

        # Session stats (read-only from outside)
        self._stats = SessionStats()

        self._lock    = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # Tick resolution (1 second)
        self._TICK = 1.0

    # ── Public API ──────────────────────────────

    def on_break(self, callback: Callable[[BreakEvent], None]) -> None:
        """Register a listener that receives BreakEvent objects."""
        self._break_callbacks.append(callback)

    def start(self) -> None:
        """Begin tracking. Call once when the application starts."""
        if self._running:
            return
        self._running = True
        self._stats.session_start = time.time()
        self._thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Pause tracking (e.g., when user is detected idle)."""
        self._running = False

    def acknowledge_break(self, break_type: BreakType) -> None:
        """
        Call this when the user confirms they've taken the break.
        Resets the appropriate counter.
        """
        with self._lock:
            if break_type == BreakType.EYE_BREAK:
                self._elapsed_since_eye = 0.0
                self._stats.eye_breaks_taken += 1
            elif break_type == BreakType.MICRO_BREAK:
                self._elapsed_since_micro = 0.0
                self._stats.micro_breaks_taken += 1
            elif break_type == BreakType.LONG_BREAK:
                self._elapsed_since_long = 0.0
                self._stats.long_breaks_taken += 1

    @property
    def stats(self) -> SessionStats:
        """Thread-safe snapshot of current session statistics."""
        with self._lock:
            self._stats.total_session_secs  = time.time() - self._stats.session_start
            self._stats.total_daily_secs    = self._daily_elapsed
            self._stats.next_eye_break_in   = max(0, self._cfg.eye_break_interval   - self._elapsed_since_eye)
            self._stats.next_micro_break_in = max(0, self._cfg.micro_break_interval - self._elapsed_since_micro)
            self._stats.next_long_break_in  = max(0, self._cfg.long_break_interval  - self._elapsed_since_long)
            return self._stats

    @staticmethod
    def format_duration(seconds: float) -> str:
        """Convert seconds to a human-readable 'Xh Ym Zs' string."""
        seconds = int(seconds)
        h, remainder = divmod(seconds, 3600)
        m, s = divmod(remainder, 60)
        parts = []
        if h:
            parts.append(f"{h}h")
        if m or h:
            parts.append(f"{m}m")
        parts.append(f"{s}s")
        return " ".join(parts)

    # ── Internal helpers ─────────────────────────

    def _tick_loop(self) -> None:
        """Increment counters every second and trigger breaks as needed."""
        while self._running:
            time.sleep(self._TICK)
            with self._lock:
                self._elapsed_since_eye   += self._TICK
                self._elapsed_since_micro += self._TICK
                self._elapsed_since_long  += self._TICK
                self._daily_elapsed       += self._TICK

            self._evaluate_breaks()

    def _evaluate_breaks(self) -> None:
        """Fire break events when any interval has been reached."""
        cfg = self._cfg
        with self._lock:
            eye_due   = self._elapsed_since_eye   >= cfg.eye_break_interval
            micro_due = self._elapsed_since_micro >= cfg.micro_break_interval
            long_due  = self._elapsed_since_long  >= cfg.long_break_interval
            cap_due   = self._daily_elapsed        >= cfg.daily_cap_secs

            # Reset counters immediately to avoid repeated firing
            if eye_due:
                self._elapsed_since_eye = 0.0
                self._stats.eye_breaks_taken += 1
            if micro_due:
                self._elapsed_since_micro = 0.0
                self._stats.micro_breaks_taken += 1
            if long_due:
                self._elapsed_since_long = 0.0
                self._stats.long_breaks_taken += 1

        # Build and dispatch events (outside the lock)
        if long_due:
            self._fire(BreakEvent(
                break_type    = BreakType.LONG_BREAK,
                title         = "⏸ Long Break Time",
                message       = "You've been working for 2 hours. Take a 15-minute break — stand up, hydrate, and move around.",
                duration_secs = cfg.long_break_duration,
            ))
        elif micro_due:
            self._fire(BreakEvent(
                break_type    = BreakType.MICRO_BREAK,
                title         = "🧘 Micro Break",
                message       = "1 hour of focus done! Rest for 5 minutes. Roll your shoulders and shake out your hands.",
                duration_secs = cfg.micro_break_duration,
            ))
        if eye_due:
            self._fire(BreakEvent(
                break_type    = BreakType.EYE_BREAK,
                title         = "👁 20-20-20 Eye Break",
                message       = "Look at something 20 feet (~6m) away for the next 20 seconds to relax your eye muscles.",
                duration_secs = cfg.eye_break_duration,
            ))
        if cap_due:
            hours = cfg.daily_cap_secs // 3600
            self._fire(BreakEvent(
                break_type    = BreakType.DAILY_CAP,
                title         = f"⚠ {hours}h Daily Limit Reached",
                message       = f"You have been using your computer for {hours} hours today. Consider wrapping up for the day.",
                duration_secs = 0,
            ))

    def _fire(self, event: BreakEvent) -> None:
        for cb in self._break_callbacks:
            try:
                cb(event)
            except Exception as exc:
                print(f"[ErgonomicsManager] callback error: {exc}")
