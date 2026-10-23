"""Running page: every live AutoHotkey script, wherever it was started from."""

import os
import subprocess

import customtkinter as ctk
import psutil

from core import macros, paths, procs
from . import theme as t
from .widgets import Button, Card, Dot, EmptyState, Page, PageHeader, Pill, scroll_body


def _short(path):
    """The path relative to the repository when it is inside it."""
    try:
        rel = os.path.relpath(path, paths.ROOT)
    except ValueError:
        return path
    return path if rel.startswith("..") else rel.replace("\\", "/")


class ScriptRow(Card):
    def __init__(self, master, page, proc, config):
        super().__init__(master)
        self.page, self.proc, self.config = page, proc, config
        self.grid_columnconfigure(1, weight=1)
        Dot(self, "green", 10).grid(row=0, column=0, rowspan=2, padx=(18, 14))
        name = config.title if config else os.path.basename(proc.script)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=1, sticky="ew", pady=(12, 0))
        ctk.CTkLabel(top, text=name, font=t.font(15, "bold"), text_color=t.TEXT).pack(side="left")
        Pill(top, "Macro config" if config else "Other script",
             "blue" if config else "grey").pack(side="left", padx=(10, 0))
        ctk.CTkLabel(self, text=_short(proc.script), font=t.mono(11), text_color=t.FAINT,
                     anchor="w").grid(row=1, column=1, sticky="ew", pady=(2, 12))

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=2, rowspan=2, padx=16)
        self.info = ctk.CTkLabel(right, text="", font=t.font(12), text_color=t.MUTED, width=150,
                                 anchor="e")
        self.info.pack(side="left", padx=(0, 12))
        self.restart_btn = Button(right, "Restart", "restart", command=self.restart)
        self.restart_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = Button(right, "Stop", "stop", "danger", command=self.stop)
        self.stop_btn.pack(side="left")
        self.update_state()

    def update_state(self):
        self.info.configure(text="PID %d   ·   %s" % (
            self.proc.pid, procs.format_uptime(self.proc.uptime())))

    def _busy(self, text):
        self.stop_btn.configure(state="disabled")
        self.restart_btn.configure(state="disabled")
        self.info.configure(text=text)

    def stop(self):
        self._busy("Stopping...")
        self.page.stop([self.proc])

    def restart(self):
        app, proc = self.page.app, self.proc
        try:
            exe = psutil.Process(proc.pid).exe()
        except psutil.Error:
            exe = app.ahk_exe()
        self._busy("Restarting...")

        def work():
            if not procs.stop(proc.pid):
                return False
            subprocess.Popen([exe, proc.script], cwd=os.path.dirname(proc.script))
            return True

        def done(ok, err):
            app.log(("Restarted %s." if ok else "Couldn't restart %s.") % proc.script_name,
                    "ok" if ok and not err else "error")
            app.processes_changed()

        app.run_bg(work, done)


class RunningPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        head = PageHeader(self, "Running scripts",
                          "Every AutoHotkey script running on this PC, including ones you "
                          "started from Explorer.")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        self.stop_all_btn = head.add_action("Stop all", "stop", "danger", self.stop_all)
        self.list = scroll_body(self)
        self.list.grid(row=1, column=0, sticky="nsew")
        self.rows = []
        self.empty = None
        self._configs = {}
        self.on_processes({}, [])

    def on_processes(self, scripts, buffwatch):
        for r in self.rows:
            r.destroy()
        self.rows = []
        if self.empty is not None:
            self.empty.destroy()
            self.empty = None
        self.stop_all_btn.configure(state="normal" if scripts else "disabled")
        if not scripts:
            self.empty = EmptyState(self.list, "Nothing running",
                                    "Start a macro from the Macros page and it shows up here.",
                                    "running")
            self.empty.grid(row=0, column=0, pady=80)
            return
        by_script = {os.path.normcase(c.script): c for c in macros.list_configs()}
        ordered = sorted(scripts.values(), key=lambda p: p.started)
        for i, p in enumerate(ordered):
            row = ScriptRow(self.list, self, p, by_script.get(os.path.normcase(p.script)))
            row.grid(row=i, column=0, sticky="ew", pady=(0, 10), padx=(0, 6))
            self.rows.append(row)

    def on_tick(self):
        for r in self.rows:
            r.update_state()

    def stop(self, plist):
        app = self.app

        def work():
            return [(p, procs.stop(p.pid)) for p in plist]

        def done(res, err):
            for p, ok in res or []:
                app.log(("Stopped %s." if ok else "Couldn't stop %s.") % p.script_name,
                        "info" if ok else "error")
            app.processes_changed()

        app.run_bg(work, done)

    def stop_all(self):
        plist = list(self.app.monitor.scripts.values())
        for r in self.rows:
            r._busy("Stopping...")
        if plist:
            self.stop(plist)
