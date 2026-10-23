"""Export / import of the whole configuration: everything in the data folder, as one zip.

The zip holds the data folder as it is (settings.json, library.json, icons/, skill_icons/,
skill_digits.npz, and whatever later versions add) plus a small manifest. Importing replaces
the data folder with the zip's files; the folder's old contents go to a backup zip first.
Settings missing from an older export get their defaults when loaded, and fields this
version doesn't know are kept in settings.json or skipped in library.json (see
config.load_settings and library.Library.load).
"""

import json
import os
import shutil
import time
import zipfile

from . import __version__, config

MANIFEST = "buffwatch-export.json"
BACKUP_DIR = "backups"  # inside the data folder; never exported or replaced


class BadExport(Exception):
    """The file is not a usable BuffWatch export (the message says why)."""


def _skip(rel):
    """Files that are not configuration: backups, half-written temp files."""
    parts = rel.split("/")
    return parts[0] == BACKUP_DIR or ".tmp" in parts[-1]


def _data_files(data_dir):
    """Relative paths ("/" separated) of every configuration file in the data folder."""
    out = []
    for dirpath, dirs, files in os.walk(data_dir):
        dirs.sort()
        for name in sorted(files):
            rel = os.path.relpath(os.path.join(dirpath, name), data_dir).replace(os.sep, "/")
            if not _skip(rel):
                out.append(rel)
    return out


def _write_zip(path, data_dir, files):
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(MANIFEST, json.dumps({
            "app": "BuffWatch", "version": __version__, "format": 1,
            "exported": time.strftime("%Y-%m-%d %H:%M:%S"), "files": files,
        }, indent=2))
        for rel in files:
            z.write(os.path.join(data_dir, *rel.split("/")), rel)
    os.replace(tmp, path)


def export_config(path, data_dir=None):
    """Write the whole configuration to the zip `path`. Returns the number of files."""
    data_dir = data_dir or config.DATA_DIR
    files = _data_files(data_dir) if os.path.isdir(data_dir) else []
    _write_zip(path, data_dir, files)
    return len(files)


def _members(z):
    """The zip's configuration files, checked to be safe to extract into the data folder."""
    out = []
    for info in z.infolist():
        name = info.filename.replace("\\", "/")
        if info.is_dir() or name == MANIFEST:
            continue
        parts = name.split("/")
        if name.startswith("/") or ":" in parts[0] or ".." in parts or "" in parts:
            raise BadExport("The file contains an unsafe path: %s" % info.filename)
        if not _skip(name):
            out.append((info, name))
    return out


def check_archive(path):
    """Look inside an export before importing it. Returns a short summary dict."""
    try:
        with zipfile.ZipFile(path) as z:
            names = {n for _, n in _members(z)}
            try:
                manifest = json.loads(z.read(MANIFEST).decode("utf-8"))
            except (KeyError, ValueError):
                manifest = {}
            for name in ("settings.json", "library.json"):
                if name in names:
                    try:
                        json.loads(z.read(name).decode("utf-8"))
                    except ValueError:
                        raise BadExport("%s in the file is damaged." % name)
    except zipfile.BadZipFile:
        raise BadExport("This is not a zip file.")
    except OSError as e:
        raise BadExport(str(e))
    if not manifest and not {"settings.json", "library.json"} & names:
        raise BadExport("This is not a BuffWatch export (no settings.json or library.json).")
    return {
        "version": manifest.get("version", "?"),
        "exported": manifest.get("exported", "?"),
        "files": len(names),
        "icons": sum(1 for n in names if n.startswith("icons/")),
    }


def import_config(path, data_dir=None):
    """Replace the configuration with the export `path`. The app must not be writing to
    the data folder meanwhile, and must reload (restart) afterwards. Returns the path of
    the backup of the old configuration, or None when there was nothing to back up."""
    data_dir = data_dir or config.DATA_DIR
    check_archive(path)
    backup = None
    os.makedirs(data_dir, exist_ok=True)
    old = _data_files(data_dir)
    if old:
        bdir = os.path.join(data_dir, BACKUP_DIR)
        os.makedirs(bdir, exist_ok=True)
        backup = os.path.join(bdir, "before-import-%s.zip" % time.strftime("%Y%m%d-%H%M%S"))
        _write_zip(backup, data_dir, old)
    with zipfile.ZipFile(path) as z:
        members = _members(z)
        for name in os.listdir(data_dir):
            if name == BACKUP_DIR:
                continue
            p = os.path.join(data_dir, name)
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
        for info, name in members:
            dest = os.path.join(data_dir, *name.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(info) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
    return backup
