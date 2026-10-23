"""Settings page: AutoHotkey path, JSON editor, how BuffWatch runs, quick folders."""

import os
from tkinter import filedialog

import customtkinter as ctk

from core import ahk, buffwatch as bw, paths, shell
from . import theme as t
from .widgets import Button, Card, Page, PageHeader, scroll_body, section_label

MODES = [("Automatic", "auto"), ("Source folder", bw.SOURCE), ("BuffWatch.exe", bw.EXE)]


class SettingsPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        PageHeader(self, "Settings", "Saved in launcher\\settings.json on this PC."
                   ).grid(row=0, column=0, sticky="ew", pady=(0, 18))
        body = scroll_body(self)
        body.grid(row=1, column=0, sticky="nsew")

        section_label(body, "AutoHotkey").grid(row=0, column=0, sticky="ew", pady=(0, 8))
        card = Card(body)
        card.grid(row=1, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        self.ahk_entry = self._path_row(card, 0, "AutoHotkey v1 program (AutoHotkey.exe)",
                                        "Leave empty to find it automatically.",
                                        "ahk_exe", [("AutoHotkey", "AutoHotkey*.exe"),
                                                    ("Programs", "*.exe")])
        self.ahk_status = ctk.CTkLabel(card, text="", font=t.font(12), anchor="w",
                                       justify="left")
        self.ahk_status.grid(row=2, column=0, columnspan=3, sticky="ew", padx=20, pady=(0, 16))

        section_label(body, "Editing").grid(row=2, column=0, sticky="ew", pady=(22, 8))
        card = Card(body)
        card.grid(row=3, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        self._path_row(card, 0, "Editor for macro configs",
                       "Leave empty to use the program Windows opens .json files with.",
                       "editor", [("Programs", "*.exe")])
        ctk.CTkFrame(card, fg_color="transparent", height=8).grid(row=2, column=0)

        section_label(body, "BuffWatch").grid(row=4, column=0, sticky="ew", pady=(22, 8))
        card = Card(body)
        card.grid(row=5, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="Start BuffWatch from", font=t.font(13, "bold"),
                     text_color=t.TEXT, anchor="w").grid(row=0, column=0, sticky="ew",
                                                         padx=20, pady=(16, 0))
        ctk.CTkLabel(card, text="Each has its own settings folder. Automatic uses the source "
                                "folder once it is set up, else BuffWatch.exe if you built it.",
                     font=t.font(12), text_color=t.MUTED, anchor="w", justify="left",
                     wraplength=620).grid(row=1, column=0, sticky="ew", padx=20, pady=(2, 0))
        self.mode = ctk.CTkSegmentedButton(
            card, values=[m[0] for m in MODES], command=self._set_mode, font=t.font(13),
            fg_color=t.INPUT, selected_color=t.ACCENT, selected_hover_color=t.ACCENT_HOVER,
            unselected_color=t.INPUT, unselected_hover_color=t.CARD_HOVER, height=32)
        self.mode.grid(row=0, column=1, rowspan=2, padx=20, pady=16)
        cur = app.settings.get("buffwatch_mode", "auto")
        self.mode.set(next((m[0] for m in MODES if m[1] == cur), MODES[0][0]))

        section_label(body, "Folders").grid(row=6, column=0, sticky="ew", pady=(22, 8))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=7, column=0, sticky="ew", pady=(0, 8))
        for text, path in (("Project", paths.ROOT), ("Macro configs", paths.CONFIGS_DIR),
                           ("Generated scripts", paths.GENERATED_DIR),
                           ("BuffWatch", paths.BUFFWATCH_DIR)):
            Button(row, text, "folder", command=lambda p=path: self._open(p)
                   ).pack(side="left", padx=(0, 8))

    def _path_row(self, card, row, title, hint, key, types):
        box = ctk.CTkFrame(card, fg_color="transparent")
        box.grid(row=row, column=0, sticky="ew", padx=20, pady=(16, 8))
        box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(box, text=title, font=t.font(13, "bold"), text_color=t.TEXT, anchor="w"
                     ).grid(row=0, column=0, columnspan=3, sticky="ew")
        ctk.CTkLabel(box, text=hint, font=t.font(12), text_color=t.MUTED, anchor="w"
                     ).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        var = ctk.StringVar(value=self.app.settings.get(key, ""))
        entry = ctk.CTkEntry(box, textvariable=var, height=34, font=t.mono(12),
                             fg_color=t.INPUT, border_color=t.BORDER, text_color=t.TEXT,
                             placeholder_text="Automatic", placeholder_text_color=t.FAINT)
        entry.grid(row=2, column=0, sticky="ew")

        def changed(*_):
            self.app.settings[key] = var.get().strip()
            self.app.save_settings()
            self.on_show()

        var.trace_add("write", changed)

        def browse():
            p = filedialog.askopenfilename(parent=self, title=title, filetypes=types)
            if p:
                var.set(p)

        Button(box, "Browse...", command=browse).grid(row=2, column=1, padx=(8, 0))
        Button(box, "Clear", style="ghost", command=lambda: var.set("")
               ).grid(row=2, column=2, padx=(4, 0))
        return entry

    def _set_mode(self, label):
        self.app.settings["buffwatch_mode"] = dict(MODES)[label]
        self.app.save_settings()

    def _open(self, path):
        try:
            os.makedirs(path, exist_ok=True)
            shell.open_path(path)
        except OSError as e:
            self.app.log(str(e), "error")

    def on_show(self):
        setting = self.app.settings.get("ahk_exe", "")
        exe = ahk.resolve(setting)
        if setting and exe != setting:
            text, color = "That file doesn't exist. " + (
                "Using the detected one instead: " + exe if exe else ""), t.AMBER
        elif exe:
            text, color = "Using " + exe, t.GREEN
        else:
            text, color = ("AutoHotkey v1 was not found. Install v1.1 from autohotkey.com, "
                           "or pick AutoHotkey.exe above."), t.RED
        self.ahk_status.configure(text=text, text_color=color)
