"""Opening files and folders in their Windows programs."""

import os
import subprocess
import sys

IS_WIN = sys.platform == "win32"


def open_path(path):
    """Show a file or folder in its default program (Explorer for folders)."""
    if IS_WIN:
        os.startfile(path)
    else:
        subprocess.Popen(["xdg-open", path])


def edit_file(path, editor=""):
    """Open a text file for editing: in `editor` when set, else in the program Windows
    uses for its type, else in Notepad."""
    if editor:
        subprocess.Popen([editor, path])
        return
    if not IS_WIN:
        subprocess.Popen(["xdg-open", path])
        return
    try:
        os.startfile(path, "edit")
    except OSError:
        try:
            os.startfile(path)
        except OSError:
            subprocess.Popen(["notepad.exe", path])
