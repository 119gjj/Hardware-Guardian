# ⚡ Hardware & Ergonomics Guardian

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-00E5FF?style=for-the-badge&logo=python&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-00E5FF?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-00E676?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Active-00E676?style=for-the-badge)
![Stars](https://img.shields.io/github/stars/YOUR_USERNAME/hardware-ergonomics-guardian?style=for-the-badge&color=FFD740)

**A professional-grade system monitoring & ergonomics companion — built for enthusiasts who work hard and want to stay healthy doing it.**

*Real-time hardware telemetry + 20-20-20 eye care + smart break scheduling, all wrapped in a tactical dark-mode UI.*

</div>

---

<!-- SCREENSHOT PLACEHOLDER -->
<!-- Add a screenshot here: ![App Screenshot](docs/screenshot_main.png) -->
> 📸 **[Screenshot — Main Dashboard]** *(add `docs/screenshot_main.png`)*

---

## 🎯 Why This Project?

Spending **11+ hours a day** in front of a screen is the reality for many developers, gamers, and students.  
Most monitoring tools focus only on hardware. Most wellness apps ignore hardware entirely.  

**Hardware & Ergonomics Guardian** fuses both worlds into a single Python application:

| Without this app | With this app |
|---|---|
| 🔥 CPU overheats silently | 🟡 Threshold alert fired at 75°C, critical at 90°C |
| 👁 Eyes strained after hours of work | 👁 20-20-20 reminder every 20 minutes |
| 💾 Disk fills up unnoticed | 💾 Storage health tracked & warned |
| ⏱ No sense of time spent working | 📊 Session, daily & break counters always visible |

---

## ✨ Features

### 🖥 Hardware Telemetry Module
- **CPU** — real-time usage %, clock speed, core count and temperature (Intel coretemp / AMD k10temp / ARM)
- **GPU** — NVIDIA load, VRAM used/total and temperature (via GPUtil)
- **RAM** — used / total GB and usage percentage with colour-coded status
- **Disk** — per-mount usage, free space and a three-tier health badge (`OK` / `WARNING` / `CRITICAL`)
- **Configurable thresholds** — edit `AlertThresholds` to match your hardware
- **Alert log** — timestamped log of every threshold breach inside the app

### 🧘 Ergonomics & Health Module
- **20-20-20 eye break** — every 20 min, prompted to look 20 ft away for 20 seconds
- **Micro-break** — 5-minute rest reminder every hour
- **Long break** — 15-minute full rest every 2 hours
- **Daily cap warning** — alert when you reach your configured daily screen-time limit (default: 11 h)
- **Countdown popups** — modal window with live countdown during each break

### 🎨 UI / UX
- **Tactical dark theme** — electric-cyan accent on a near-black background
- **Metric cards** — colour changes from green → amber → red as values enter danger zones
- **Live clock** in the header
- **Zero config launch** — sensible defaults, works out of the box

---

## 📁 Project Structure

```
hardware_ergonomics_guardian/
│
├── main.py                         # Entry point
├── requirements.txt
│
├── core/
│   ├── __init__.py
│   ├── hardware_monitor.py         # HardwareMonitor + dataclasses + thresholds
│   └── ergonomics_manager.py       # ErgonomicsManager + break scheduling
│
└── ui/
    ├── __init__.py
    └── main_window.py              # MainWindow, MetricCard, BreakPopup
```

All modules follow **OOP principles** with clear separation of concerns:
- `core/` — pure business logic, zero UI imports
- `ui/`   — pure presentation, delegates all logic to `core/`

---

## 🚀 Installation

### Prerequisites
- Python **3.10** or newer
- Windows 10/11, macOS 12+, or Linux (Ubuntu 20.04+)
- NVIDIA GPU owners: ensure drivers are installed for GPU monitoring

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/hardware-ergonomics-guardian.git
cd hardware-ergonomics-guardian

# 2. (Recommended) Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch
python main.py
```

> **No NVIDIA GPU?**  
> Remove or comment out `GPUtil` in `requirements.txt`. The app gracefully shows "No GPU detected" instead of crashing.

---

## ⚙️ Configuration

All thresholds live in plain Python dataclasses — no config files to hunt for.

**Hardware thresholds** (`core/hardware_monitor.py`):
```python
AlertThresholds(
    cpu_temp_warning  = 75.0,   # °C
    cpu_temp_critical = 90.0,
    gpu_temp_warning  = 80.0,
    gpu_temp_critical = 95.0,
    ram_usage_warning = 80.0,   # %
    disk_usage_warning= 85.0,
)
```

**Break schedule** (`core/ergonomics_manager.py`):
```python
ErgonomicsConfig(
    eye_break_interval   = 20 * 60,    # seconds
    micro_break_interval = 60 * 60,
    long_break_interval  = 2 * 60 * 60,
    daily_cap_secs       = 11 * 60 * 60,
)
```

---

## 🗺 Roadmap

- [ ] System tray icon (minimize to tray)
- [ ] Historical graphs (matplotlib integration)
- [ ] AMD GPU support (via `pyadl`)
- [ ] Sound alerts
- [ ] YAML/JSON config file
- [ ] macOS native notifications

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

```bash
# Fork → clone → create branch → commit → push → PR
git checkout -b feature/my-awesome-feature
```

Please keep code style consistent with the existing modules:
- Type hints on every function signature
- Docstrings on every class
- Descriptive variable names (no single-letter abbreviations outside loops)

---

## 📚 Dependencies & Credits

| Library | Purpose | License |
|---|---|---|
| [psutil](https://github.com/giampaolo/psutil) | CPU / RAM / Disk metrics | BSD-3 |
| [GPUtil](https://github.com/anderskm/gputil) | NVIDIA GPU metrics | MIT |
| [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) | Modern dark-mode UI | MIT |
| [Pillow](https://python-pillow.org/) | Image support for CTk | HPND |
| [plyer](https://github.com/kivy/plyer) | Desktop notifications | MIT |

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

---

<div align="center">

Made with ❤️ and ☕ by **YOUR_USERNAME**  
*A bilişim lisesi student passionate about systems, performance and health.*

**If this helped you — drop a ⭐ and share it with a friend who also needs to take more breaks.**

</div>
