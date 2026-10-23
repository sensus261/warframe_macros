"""Macros page: one card per macro config, to generate, run, stop and edit it."""

import os
import time

import customtkinter as ctk

from core import ahk, macros, paths, procs, shell
from . import theme as t
from .widgets import Button, Card, Chip, EmptyState, Page, PageHeader, Pill, scroll_body, update

CHIPS_PER_LINE = 4

STATUS_PILL = {
    macros.READY: ("Ready", "blue"),
    macros.STALE: ("Changed since generated", "amber"),
    macros.MISSING: ("Not generated", "grey"),
    macros.BROKEN: ("Invalid JSON", "red"),
}


def _ago(ts):
    s = time.time() - ts
    if s < 60:
        return "just now"
    if s < 3600:
        return "%d min ago" % (s // 60)
    if s < 86400:
        return "%d h ago" % (s // 3600)
    return time.strftime("%d %b %Y", time.localtime(ts))


class ConfigCard(Card):
    def __init__(self, master, page, config):
        super().__init__(master)
        self.page, self.config = page, config
        self.busy = None  # "generating" / "stopping" / None
        self._buttons = None
        self.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        ctk.CTkLabel(top, text=config.title, font=t.font(16, "bold"), text_color=t.TEXT
                     ).pack(side="left")
        self.pill = Pill(top)
        self.pill.pack(side="left", padx=(12, 0))

        self.run_btn = Button(top, "Run", icon="play", style="primary", width=92,
                              command=self.on_run)
        self.run_btn.pack(side="right")
        self.gen_btn = Button(top, "Generate", icon="build", command=self.on_generate)
        self.gen_btn.pack(side="right", padx=(0, 8))
        Button(top, "Edit", icon="edit", style="ghost", command=self.on_edit
               ).pack(side="right", padx=(0, 4))

        chips = ctk.CTkFrame(self, fg_color="transparent")
        chips.grid(row=1, column=0, sticky="ew", padx=14)
        if config.error:
            ctk.CTkLabel(chips, text=config.error, font=t.mono(12), text_color=t.RED,
                         anchor="w", justify="left", wraplength=640).pack(fill="x", padx=4)
        line = None
        for i, (key, name, _desc) in enumerate(config.macros):
            if i % CHIPS_PER_LINE == 0:
                line = ctk.CTkFrame(chips, fg_color="transparent")
                line.pack(fill="x")
            Chip(line, key, name).pack(side="left", padx=4, pady=3)

        self.meta = ctk.CTkLabel(self, text="", font=t.font(12), text_color=t.FAINT,
                                 anchor="w")
        self.meta.grid(row=2, column=0, sticky="ew", padx=18, pady=(6, 12))

    def running(self):
        return procs.scripts_for(self.config.script, self.page.app.monitor.scripts)

    def update_state(self):
        c = self.config
        status = c.status()
        live = self.running()
        if live:
            self.pill.set("Running", "green")
        else:
            self.pill.set(*STATUS_PILL[status])

        if self.busy == "generating":
            buttons = ("Generating...", "disabled", None, "disabled")
        elif self.busy == "stopping":
            buttons = ("Generate", "normal", ("Stopping...", "stop", "danger"), "disabled")
        elif live:
            buttons = ("Generate", "normal", ("Stop", "stop", "danger"), "normal")
        else:
            off = "disabled" if status == macros.BROKEN else "normal"
            buttons = ("Generate", off, ("Run", "play", "primary"), off)
        if buttons != self._buttons:
            self._buttons = buttons
            gen_text, gen_state, run_look, run_state = buttons
            self.gen_btn.configure(text=gen_text, state=gen_state)
            if run_look:
                self.run_btn.set(*run_look)
            self.run_btn.configure(state=run_state)

        bits = ["macros/configs/" + os.path.basename(c.path)]
        n = len(c.macros)
        if n:
            bits.append("%d macro%s" % (n, "" if n == 1 else "s"))
        if c.panic_hotkey:
            bits.append("stop-all key " + str(c.panic_hotkey))
        if live:
            bits.append("running for " + procs.format_uptime(live[0].uptime()))
        elif status in (macros.READY, macros.STALE):
            bits.append("generated " + _ago(os.path.getmtime(c.script)))
        update(self.meta, text="   ·   ".join(bits))

    # ------------------------------------------------------------ actions
    def on_edit(self):
        try:
            shell.edit_file(self.config.path, self.page.app.settings.get("editor", ""))
            self.page.app.log("Opened %s for editing." % os.path.basename(self.config.path))
        except OSError as e:
            self.page.app.log("Couldn't open the editor: %s" % e, "error")

    def on_generate(self, then=None):
        app = self.page.app
        self.busy = "generating"
        self.update_state()
        app.log("Generating %s ..." % os.path.basename(self.config.script))

        def done(res, err):
            self.busy = None
            ok, out = res if res else (False, str(err))
            app.log(out or ("Done." if ok else "Failed."), "ok" if ok else "error")
            self.update_state()
            if ok and then:
                then()

        app.run_bg(lambda: macros.generate(self.config), done)

    def on_run(self):
        if self.running():
            self.stop()
        elif self.config.status() in (macros.MISSING, macros.STALE):
            self.on_generate(then=self.start)
        else:
            self.start()

    def start(self):
        app = self.page.app
        exe = app.ahk_exe()
        try:
            ahk.run_script(self.config.script, exe)
        except OSError as e:
            app.log("Couldn't start %s: %s" % (os.path.basename(self.config.script), e), "error")
            return
        keys = ", ".join("%s %s" % (k, n) for k, n, _ in self.config.macros)
        app.log("Started %s. Hotkeys: %s" % (self.config.title, keys or "none"), "ok")
        app.processes_changed()

    def stop(self):
        app = self.page.app
        live = self.running()
        self.busy = "stopping"
        self.update_state()

        def work():
            return all(procs.stop(p.pid) for p in live)

        def done(ok, err):
            self.busy = None
            app.log("Stopped %s." % self.config.title if ok else
                    "Couldn't stop %s." % self.config.title, "info" if ok else "error")
            app.processes_changed()
            self.update_state()

        app.run_bg(work, done)


class MacrosPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        head = PageHeader(self, "Macros", "AutoHotkey toggle macros from macros/configs.")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        head.add_action("Open folder", "folder", "ghost",
                        lambda: shell.open_path(paths.CONFIGS_DIR))
        head.add_action("Generate all", "build", "secondary", self.generate_all)
        head.add_action("New config", "add", "primary", self.new_config)

        self.list = scroll_body(self)
        self.list.grid(row=1, column=0, sticky="nsew")
        self.cards = []
        self.empty = None
        self._sig = None
        self._ticks = 0
        self.reload()

    def _signature(self):
        try:
            names = sorted(n for n in os.listdir(paths.CONFIGS_DIR) if n.lower().endswith(".json"))
        except OSError:
            return ()
        out = []
        for n in names:
            try:
                out.append((n, os.path.getmtime(os.path.join(paths.CONFIGS_DIR, n))))
            except OSError:
                pass
        return tuple(out)

    def reload(self, force=False):
        sig = self._signature()
        if sig == self._sig and not force:
            return
        self._sig = sig
        busy = {c.config.path: c.busy for c in self.cards if c.busy}
        for c in self.cards:
            c.destroy()
        self.cards = []
        if self.empty is not None:
            self.empty.destroy()
            self.empty = None
        configs = macros.list_configs()
        if not configs:
            self.empty = EmptyState(
                self.list, "No macro configs yet",
                "Create one with New config, or put .json files in macros/configs.", "macros")
            self.empty.grid(row=0, column=0, pady=80)
            return
        for i, cfg in enumerate(configs):
            card = ConfigCard(self.list, self, cfg)
            card.busy = busy.get(cfg.path)
            card.grid(row=i, column=0, sticky="ew", pady=(0, 12), padx=(0, 6))
            card.update_state()
            self.cards.append(card)

    def on_show(self):
        self.reload()

    def on_tick(self):
        self._ticks += 1
        if self._ticks % 4 == 0:
            self.reload()
        if self._ticks % 2 == 0:
            for c in self.cards:
                c.update_state()

    def on_processes(self, scripts, buffwatch):
        for c in self.cards:
            c.update_state()

    def generate_all(self):
        for c in self.cards:
            if not c.busy and c.config.status() != macros.BROKEN:
                c.on_generate()

    def new_config(self):
        d = ctk.CTkInputDialog(title="New macro config",
                               text="Name of the new config (for example: saryn spores):",
                               fg_color=t.CARD, button_fg_color=t.ACCENT,
                               button_hover_color=t.ACCENT_HOVER, entry_fg_color=t.INPUT,
                               entry_border_color=t.BORDER, font=t.font(13))
        name = d.get_input()
        if not name:
            return
        try:
            path = macros.create_config(name)
        except (OSError, ValueError) as e:
            self.app.log(str(e), "error")
            return
        self.app.log("Created macros/configs/%s from the template." % os.path.basename(path), "ok")
        self.reload(force=True)
        try:
            shell.edit_file(path, self.app.settings.get("editor", ""))
        except OSError as e:
            self.app.log("Couldn't open the editor: %s" % e, "error")
