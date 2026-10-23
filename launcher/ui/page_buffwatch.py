"""BuffWatch page: start, stop and find BuffWatch's files."""

import os

import customtkinter as ctk

from core import buffwatch as bw, paths, procs, shell
from . import theme as t
from .widgets import Button, Card, Dot, Page, PageHeader, section_label

MODE_TEXT = {
    bw.SOURCE: "From the source folder (buff_watch\\run.bat's way)",
    bw.EXE: "BuffWatch.exe (buff_watch\\dist\\BuffWatch)",
}


class BuffWatchPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        self.busy = None
        self._live = []
        head = PageHeader(self, "BuffWatch",
                          "Magnified buff and debuff overlay, and ability timers with "
                          "auto-recast.")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        head.add_action("Read me", "doc", "ghost",
                        lambda: shell.open_path(os.path.join(paths.BUFFWATCH_DIR, "README.md")))

        hero = Card(self)
        hero.grid(row=1, column=0, sticky="ew")
        hero.grid_columnconfigure(1, weight=1)
        self.dot = Dot(hero, "grey", 14)
        self.dot.grid(row=0, column=0, rowspan=2, padx=(22, 16), pady=22)
        self.state_label = ctk.CTkLabel(hero, text="", font=t.font(18, "bold"),
                                        text_color=t.TEXT, anchor="w")
        self.state_label.grid(row=0, column=1, sticky="sew", pady=(20, 0))
        self.state_sub = ctk.CTkLabel(hero, text="", font=t.font(12), text_color=t.MUTED,
                                      anchor="w", justify="left")
        self.state_sub.grid(row=1, column=1, sticky="new", pady=(2, 20))
        btns = ctk.CTkFrame(hero, fg_color="transparent")
        btns.grid(row=0, column=2, rowspan=2, padx=20)
        self.restart_btn = Button(btns, "Restart", "restart", command=self.restart)
        self.restart_btn.pack(side="left", padx=(0, 8))
        self.main_btn = Button(btns, "Start", "play", "primary", width=110, height=38,
                               command=self.toggle)
        self.main_btn.pack(side="left")

        section_label(self, "Files").grid(row=2, column=0, sticky="ew", pady=(26, 8))
        files = Card(self)
        files.grid(row=3, column=0, sticky="ew")
        files.grid_columnconfigure(1, weight=1)
        self.mode_value = self._info_row(files, 0, "Runs", None)
        self.data_value = self._info_row(files, 1, "Settings and buffs", self.open_data)
        self._info_row(files, 2, "Program folder", lambda: shell.open_path(paths.BUFFWATCH_DIR),
                       value=_rel(paths.BUFFWATCH_DIR))
        self.note = ctk.CTkLabel(self, text="", font=t.font(12), text_color=t.AMBER,
                                 anchor="w", justify="left", wraplength=760)
        self.note.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        self.refresh()

    def _info_row(self, card, row, label, command, value=""):
        pad = (16 if row == 0 else 6, 16 if row == 2 else 6)
        ctk.CTkLabel(card, text=label, font=t.font(13), text_color=t.MUTED, width=170,
                     anchor="w").grid(row=row, column=0, sticky="w", padx=(20, 0), pady=pad)
        v = ctk.CTkLabel(card, text=value, font=t.font(13), text_color=t.TEXT, anchor="w")
        v.grid(row=row, column=1, sticky="ew", pady=pad)
        if command:
            Button(card, "Open", "folder", "ghost", command=command
                   ).grid(row=row, column=2, padx=14, pady=pad)
        return v

    def mode(self):
        return bw.resolve_mode(self.app.settings.get("buffwatch_mode", "auto"))

    def refresh(self):
        mode = self.mode()
        live = self._live
        if self.busy:
            self.dot.set("amber")
            self.state_label.configure(text=self.busy)
        elif live:
            self.dot.set("green")
            self.state_label.configure(text="Running")
        else:
            self.dot.set("grey")
            self.state_label.configure(text="Not running")
        if live:
            self.state_sub.configure(text="Up for %s   ·   PID %d" % (
                procs.format_uptime(live[0].uptime()), live[0].pid))
        else:
            self.state_sub.configure(text="Its overlays appear over the game once it starts.")
        if live:
            self.main_btn.set("Stop", "stop", "danger")
        else:
            self.main_btn.set("Start", "play", "primary")
        self.main_btn.configure(state="disabled" if self.busy else "normal")
        self.restart_btn.configure(state="normal" if live and not self.busy else "disabled")
        self.mode_value.configure(text=MODE_TEXT[mode])
        self.data_value.configure(text=_rel(bw.data_dir(mode)))
        notes = []
        if bw.needs_setup(mode):
            notes.append("The first start installs BuffWatch's Python packages in a console "
                         "window. That takes a minute or two, once.")
        if len(live) > 1:
            notes.append("%d copies of BuffWatch are running." % len(live))
        self.note.configure(text="\n".join(notes))

    def on_show(self):
        self.refresh()

    def on_tick(self):
        self.refresh()

    def on_processes(self, scripts, buffwatch):
        self._live = list(buffwatch)
        if self.busy == "Starting..." and buffwatch:
            self.busy = None
        self.refresh()

    def toggle(self):
        if self._live:
            self.stop()
        else:
            self.start()

    def start(self, then=None):
        app = self.app
        mode = self.mode()
        try:
            pid = bw.start(mode)
        except OSError as e:
            app.log("Couldn't start BuffWatch: %s" % e, "error")
            return
        app.log("Starting BuffWatch (%s)%s." % (
            "BuffWatch.exe" if mode == bw.EXE else "source",
            "" if pid else ", setting it up first in a console window"), "ok")
        self.busy = "Starting..."
        # Give up waiting for it after a while (first-time setup can be slow).
        self.after(180000 if pid is None else 20000, self._start_timeout)
        app.processes_changed()
        self.refresh()

    def _start_timeout(self):
        if self.busy == "Starting...":
            self.busy = None
            if not self._live:
                self.app.log("BuffWatch didn't start. Try buff_watch\\run.bat to see why.",
                             "warn")
            self.refresh()

    def stop(self, then=None):
        app = self.app
        live = list(self._live)
        self.busy = "Closing..."
        self.refresh()

        def work():
            return all(procs.stop(p.pid, buffwatch=True, timeout=8) for p in live)

        def done(ok, err):
            self.busy = None
            if ok:
                self._live = []
            app.log("BuffWatch closed." if ok else "Couldn't close BuffWatch.",
                    "info" if ok else "error")
            app.processes_changed()
            self.refresh()
            if ok and then:
                then()

        app.run_bg(work, done)

    def restart(self):
        self.stop(then=lambda: self.after(500, self.start))

    def open_data(self):
        d = bw.data_dir(self.mode())
        if not os.path.isdir(d):
            self.app.log("BuffWatch has no data folder yet; it makes one on its first start.",
                         "warn")
            return
        shell.open_path(d)


def _rel(path):
    return os.path.relpath(path, paths.ROOT).replace("/", "\\")
