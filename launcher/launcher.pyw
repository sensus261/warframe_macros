"""Warframe Toolkit launcher. Double-click Launcher.bat in the project folder, or:
python launcher.pyw"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import App  # noqa: E402


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
