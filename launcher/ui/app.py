"""The launcher window: sidebar, pages, activity log, and the background work behind them."""

import queue
import sys
import threading
import time
import traceback

import customtkinter as ctk

from core import ahk, procs, settings as settings_mod
from . import icons, theme as t
from .page_buffwatch import BuffWatchPage
from .page_macros import MacrosPage
from .page_running import RunningPage
from .page_settings import SettingsPage
from .widgets import Dot, update

POLL_S = 1.5  # how often running processes are checked


def report_exception():
    """Print the current exception when there is a console (pythonw has none)."""
    if sys.stderr is not None:
        traceback.print_exc()

NAV = [
    ("macros", "Macros", "macros"),
    ("running", "Running", "running"),
    ("buffwatch", "BuffWatch", "buffwatch"),
]


class Monitor(threading.Thread):
    """Checks the running AutoHotkey scripts and BuffWatch in the background."""

    def __init__(self):
        super().__init__(daemon=True)
        self.scripts, self.buffwatch = {}, []
        self.version = 0
        self._wake = threading.Event()

    def poke(self):
        self._wake.set()

    def run(self):
        while True:
            try:
                scripts, bw = procs.snapshot()
            except Exception:
                scripts, bw = self.scripts, self.buffwatch
            if (set(scripts) != set(self.scripts) or
                    [p.pid for p in bw] != [p.pid for p in self.buffwatch]):
                self.scripts, self.buffwatch = scripts, bw
                self.version += 1
            self._wake.wait(POLL_S)
            self._wake.clear()


class App(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        super().__init__(fg_color=t.BG)
        t.init(self)
        self.settings = settings_mod.load()
        self.title("Warframe Toolkit")
        self.minsize(920, 620)
        self.geometry(self.settings.get("geometry") or "1120x740")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._results = queue.Queue()
        self.monitor = Monitor()
        self._seen_version = -1

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()

        main = ctk.CTkFrame(self, fg_color=t.BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=1)
        self._page_host = ctk.CTkFrame(main, fg_color="transparent")
        self._page_host.grid(row=0, column=0, sticky="nsew", padx=28, pady=(24, 12))
        self._page_host.grid_columnconfigure(0, weight=1)
        self._page_host.grid_rowconfigure(0, weight=1)
        self._build_log(main)

        self.pages = {
            "macros": MacrosPage(self._page_host, self),
            "running": RunningPage(self._page_host, self),
            "buffwatch": BuffWatchPage(self._page_host, self),
            "settings": SettingsPage(self._page_host, self),
        }
        self.current = None
        self.show(self.settings.get("page") if self.settings.get("page") in self.pages
                  else "macros")

        exe = self.ahk_exe()
        self.log("Ready. " + ("AutoHotkey: " + exe if exe else
                              "AutoHotkey v1 was not found; set its path in Settings."),
                 "ok" if exe else "warn")
        self.monitor.start()
        self.after(150, self._tick)

    # ------------------------------------------------------------------ layout
    def _build_sidebar(self):
        bar = ctk.CTkFrame(self, fg_color=t.SIDEBAR, corner_radius=0, width=228)
        bar.grid(row=0, column=0, sticky="nsw")
        bar.grid_propagate(False)
        bar.pack_propagate(False)

        brand = ctk.CTkFrame(bar, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(24, 26))
        ctk.CTkLabel(brand, text="WARFRAME", font=t.font(11, "bold"), text_color=t.ACCENT,
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(brand, text="Toolkit", font=t.font(22, "bold"), text_color=t.TEXT,
                     anchor="w").pack(fill="x")

        self._nav = {}
        for key, label, icon in NAV:
            self._nav[key] = self._nav_button(bar, key, label, icon)
        ctk.CTkFrame(bar, fg_color="transparent").pack(fill="both", expand=True)
        self._nav["settings"] = self._nav_button(bar, "settings", "Settings", "settings")

        foot = ctk.CTkFrame(bar, fg_color="transparent")
        foot.pack(fill="x", padx=20, pady=(10, 18))
        self._foot_ahk = ctk.CTkLabel(foot, text="", font=t.font(11), text_color=t.FAINT,
                                      anchor="w", justify="left", wraplength=190)
        self._foot_ahk.pack(fill="x")

    def _nav_button(self, bar, key, label, icon):
        row = ctk.CTkFrame(bar, fg_color="transparent", corner_radius=8, height=40)
        row.pack(fill="x", padx=12, pady=2)
        row.pack_propagate(False)
        btn = ctk.CTkButton(row, text="  " + label, anchor="w", height=40, corner_radius=8,
                            image=icons.get(icon, 17, t.MUTED), compound="left",
                            fg_color="transparent", hover_color=t.CARD, text_color=t.MUTED,
                            font=t.font(14), command=lambda: self.show(key))
        btn.pack(fill="both", expand=True)
        badge = ctk.CTkLabel(row, text="", font=t.font(11, "bold"), fg_color=t.ACCENT_DIM,
                             text_color=t.BLUE, corner_radius=9, height=20, width=24)
        dot = Dot(row, "grey", 8)
        return {"row": row, "button": btn, "badge": badge, "dot": dot, "icon": icon}

    def set_badge(self, key, text):
        b = self._nav[key]["badge"]
        if text:
            b.configure(text=text)
            b.place(relx=1.0, rely=0.5, x=-12, anchor="e")
        else:
            b.place_forget()

    def set_nav_dot(self, key, tone):
        d = self._nav[key]["dot"]
        if tone:
            d.set(tone)
            d.place(relx=1.0, rely=0.5, x=-16, anchor="e")
        else:
            d.place_forget()

    def _build_log(self, main):
        wrap = ctk.CTkFrame(main, fg_color=t.SIDEBAR, corner_radius=0, border_width=0)
        wrap.grid(row=1, column=0, sticky="ew")
        head = ctk.CTkFrame(wrap, fg_color="transparent", height=36)
        head.pack(fill="x", padx=20, pady=(6, 0))
        ctk.CTkLabel(head, text="ACTIVITY", font=t.font(11, "bold"), text_color=t.FAINT
                     ).pack(side="left")
        self._log_last = ctk.CTkLabel(head, text="", font=t.font(12), text_color=t.MUTED,
                                      anchor="w")
        self._log_last.pack(side="left", padx=12, fill="x", expand=True)
        self._log_toggle = ctk.CTkButton(
            head, text="", width=28, height=26, fg_color="transparent", hover_color=t.CARD,
            image=icons.get("collapse", 14, t.MUTED), command=self._toggle_log)
        self._log_toggle.pack(side="right")
        ctk.CTkButton(head, text="", width=28, height=26, fg_color="transparent",
                      hover_color=t.CARD, image=icons.get("clear", 14, t.MUTED),
                      command=self._clear_log).pack(side="right", padx=4)
        self._log_box = ctk.CTkTextbox(wrap, height=110, fg_color=t.INPUT, text_color=t.TEXT,
                                       font=t.mono(12), corner_radius=8, border_width=1,
                                       border_color=t.BORDER, wrap="word")
        tb = self._log_box._textbox
        tb.tag_config("time", foreground=t.FAINT)
        tb.tag_config("ok", foreground=t.GREEN)
        tb.tag_config("warn", foreground=t.AMBER)
        tb.tag_config("error", foreground=t.RED)
        tb.tag_config("info", foreground=t.TEXT)
        self._log_box.configure(state="disabled")
        self._log_open = bool(self.settings.get("log_open", True))
        self._apply_log_open()

    def _apply_log_open(self):
        if self._log_open:
            self._log_box.pack(fill="x", padx=20, pady=(2, 14))
            self._log_last.configure(text="")
        else:
            self._log_box.pack_forget()
        self._log_toggle.configure(
            image=icons.get("collapse" if self._log_open else "expand", 14, t.MUTED))

    def _toggle_log(self):
        self._log_open = not self._log_open
        self.settings["log_open"] = self._log_open
        self._apply_log_open()

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")
        self._log_last.configure(text="")

    def log(self, text, level="info"):
        """Add a line to the activity log. level: info, ok, warn, error."""
        self._log_box.configure(state="normal")
        lines = text.rstrip().splitlines() or [""]
        self._log_box._textbox.insert("end", time.strftime("%H:%M:%S  "), "time")
        self._log_box._textbox.insert("end", lines[0] + "\n", level)
        for line in lines[1:]:
            self._log_box._textbox.insert("end", "          " + line + "\n", level)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")
        if not self._log_open:
            self._log_last.configure(text=lines[0], text_color={
                "ok": t.GREEN, "warn": t.AMBER, "error": t.RED}.get(level, t.MUTED))

    # ------------------------------------------------------------------ pages
    def show(self, key):
        if self.current == key:
            return
        if self.current:
            self.pages[self.current].grid_forget()
        for k, n in self._nav.items():
            active = k == key
            n["button"].configure(
                fg_color=t.CARD if active else "transparent",
                text_color=t.TEXT if active else t.MUTED,
                font=t.font(14, "bold" if active else "normal"),
                image=icons.get(n["icon"], 17, t.ACCENT if active else t.MUTED))
        self.current = key
        self.settings["page"] = key
        page = self.pages[key]
        page.grid(row=0, column=0, sticky="nsew")
        page.on_show()

    # ------------------------------------------------------------------ work
    def ahk_exe(self):
        """The AutoHotkey v1 to run scripts with ("" when none), re-checked every 10 s."""
        setting = self.settings.get("ahk_exe", "")
        now = time.time()
        cache = getattr(self, "_ahk_cache", None)
        if not cache or cache[0] != setting or now - cache[2] > 10:
            cache = self._ahk_cache = (setting, ahk.resolve(setting), now)
        return cache[1]

    def run_bg(self, fn, done=None):
        """Run fn() on a worker thread; then done(result, error) on the UI thread."""
        def work():
            try:
                res, err = fn(), None
            except Exception as e:
                res, err = None, e
                report_exception()
            self._results.put((done, res, err))
        threading.Thread(target=work, daemon=True).start()

    def processes_changed(self):
        """Check the processes again right away (after starting or stopping one)."""
        self.monitor.poke()

    def _tick(self):
        try:
            while True:
                done, res, err = self._results.get_nowait()
                if done:
                    try:
                        done(res, err)
                    except Exception:
                        report_exception()
        except queue.Empty:
            pass
        m = self.monitor
        if m.version != self._seen_version:
            self._seen_version = m.version
            n = len(m.scripts)
            self.set_badge("running", str(n) if n else "")
            self.set_nav_dot("buffwatch", "green" if m.buffwatch else None)
            for page in self.pages.values():
                page.on_processes(m.scripts, m.buffwatch)
        if self.current:
            self.pages[self.current].on_tick()
        exe = self.ahk_exe()
        update(self._foot_ahk, text=("AutoHotkey v1 found" if exe else
                                       "AutoHotkey v1 not found") +
                                 "\nScripts keep running after you close this window.")
        self.after(500, self._tick)

    def report_callback_exception(self, exc, val, tb):
        """A button handler failed: show it in the activity log instead of losing it."""
        self.log("Something went wrong: %s" % (val or exc.__name__), "error")
        if sys.stderr is not None:
            traceback.print_exception(exc, val, tb)

    def save_settings(self):
        settings_mod.save(self.settings)

    def on_close(self):
        if self.state() == "normal":
            self.settings["geometry"] = self.geometry()
        self.save_settings()
        self.destroy()
