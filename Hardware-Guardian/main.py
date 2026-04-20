"""
main.py
───────
Hardware & Ergonomics Guardian — entry point.

Run with:
    python main.py

Requirements:
    pip install -r requirements.txt
"""

import sys
from ui.main_window import MainWindow


def main() -> None:
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
