"""Reusable pieces: cards, buttons, status pills, page headers."""

import customtkinter as ctk

from . import icons, theme as t


def update(widget, **options):
    """configure() only the options that changed. customtkinter redraws a widget on every
    configure(), which flickers when it is done on every refresh."""
    applied = widget.__dict__.setdefault("_applied_options", {})
    changed = {k: v for k, v in options.items() if k not in applied or applied[k] != v}
    if changed:
        widget.configure(**changed)
        applied.update(changed)


class Card(ctk.CTkFrame):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", t.CARD)
        kw.setdefault("corner_radius", 12)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", t.BORDER)
        super().__init__(master, **kw)


_BUTTON_STYLES = {
    # fill, hover, text, border
    "primary": (t.ACCENT, t.ACCENT_HOVER, "#ffffff", t.ACCENT),
    "secondary": (t.CARD_HOVER, "#2a3040", t.TEXT, t.BORDER),
    "ghost": ("transparent", t.CARD_HOVER, t.MUTED, None),
    "danger": (t.RED_BG, "#4a1d1d", t.RED, "#5a2424"),
    "success": (t.GREEN_BG, "#143d30", t.GREEN, "#1d5240"),
}


class Button(ctk.CTkButton):
    """A button with an optional icon on the left. style: primary, secondary, ghost,
    danger, success."""

    def __init__(self, master, text="", icon=None, style="secondary", height=32, **kw):
        self._style = style
        fill, hover, fg, border = _BUTTON_STYLES[style]
        img = icons.get(icon, 15, fg) if icon else None
        super().__init__(
            master, text=text, image=img, compound="left", height=height,
            corner_radius=8, fg_color=fill, hover_color=hover, text_color=fg,
            text_color_disabled=t.FAINT,
            border_width=1 if border else 0, border_color=border or t.BORDER,
            font=t.font(13, "bold" if style == "primary" else "normal"),
            width=kw.pop("width", 0 if text else height), **kw)
        self._icon = icon

    def set(self, text=None, icon=None, style=None):
        """Change the label, icon and style in place."""
        style = style or self._style
        icon = icon or self._icon
        text = self.cget("text") if text is None else text
        if (text, icon, style) == (self.cget("text"), self._icon, self._style):
            return
        fill, hover, fg, border = _BUTTON_STYLES[style]
        self.configure(text=text,
                       image=icons.get(icon, 15, fg) if icon else None,
                       fg_color=fill, hover_color=hover, text_color=fg,
                       border_width=1 if border else 0, border_color=border or t.BORDER,
                       font=t.font(13, "bold" if style == "primary" else "normal"))
        self._style, self._icon = style, icon


class Pill(ctk.CTkLabel):
    """A small rounded status label. tone: green, amber, red, blue, grey."""

    def __init__(self, master, text="", tone="grey", **kw):
        fg, bg = t.TONES[tone]
        super().__init__(master, text=text, fg_color=bg, text_color=fg, corner_radius=10,
                         height=22, font=t.font(11, "bold"), padx=10, **kw)

    def set(self, text, tone):
        if (text, tone) == getattr(self, "_now", None):
            return
        self._now = (text, tone)
        fg, bg = t.TONES[tone]
        self.configure(text=text, fg_color=bg, text_color=fg)


class Dot(ctk.CTkFrame):
    """A small coloured circle."""

    def __init__(self, master, tone="grey", size=9, **kw):
        super().__init__(master, width=size, height=size, corner_radius=size // 2,
                         fg_color=t.TONES[tone][0], **kw)

    def set(self, tone):
        update(self, fg_color=t.TONES[tone][0])


class Chip(ctk.CTkFrame):
    """A hotkey and what it does: [F1] Auto balls."""

    def __init__(self, master, key, label, **kw):
        super().__init__(master, fg_color=t.INPUT, corner_radius=8, border_width=1,
                         border_color=t.BORDER, **kw)
        ctk.CTkLabel(self, text=key, font=t.mono(12, "bold"), text_color=t.BLUE,
                     fg_color=t.BLUE_BG, corner_radius=6, padx=7, height=22
                     ).pack(side="left", padx=(4, 6), pady=4)
        ctk.CTkLabel(self, text=label, font=t.font(12), text_color=t.TEXT, height=22
                     ).pack(side="left", padx=(0, 10), pady=4)


class PageHeader(ctk.CTkFrame):
    """Title and subtitle on the left, action buttons on the right (self.actions)."""

    def __init__(self, master, title, subtitle=""):
        super().__init__(master, fg_color="transparent")
        # Actions first, so a narrow window squeezes the subtitle, not the buttons.
        self.actions = ctk.CTkFrame(self, fg_color="transparent", height=1)
        self.actions.pack(side="right", anchor="n", pady=(4, 0))
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(left, text=title, font=t.font(24, "bold"), text_color=t.TEXT,
                     anchor="w").pack(fill="x")
        self.subtitle = ctk.CTkLabel(left, text=subtitle, font=t.font(13), text_color=t.MUTED,
                                     anchor="w", justify="left")
        self.subtitle.pack(fill="x", pady=(2, 0))

    def add_action(self, text, icon=None, style="secondary", command=None):
        b = Button(self.actions, text=text, icon=icon, style=style, command=command)
        b.pack(side="left", padx=(8, 0))
        return b


class EmptyState(ctk.CTkFrame):
    def __init__(self, master, title, text, icon=None):
        super().__init__(master, fg_color="transparent")
        if icon:
            ctk.CTkLabel(self, text="", image=icons.get(icon, 40, t.FAINT)).pack(pady=(0, 10))
        ctk.CTkLabel(self, text=title, font=t.font(16, "bold"), text_color=t.TEXT).pack()
        ctk.CTkLabel(self, text=text, font=t.font(13), text_color=t.MUTED, justify="center"
                     ).pack(pady=(4, 0))


def section_label(master, text):
    return ctk.CTkLabel(master, text=text.upper(), font=t.font(11, "bold"),
                        text_color=t.FAINT, anchor="w")


class Page(ctk.CTkFrame):
    """A page of the launcher. The app calls the on_* hooks."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

    def on_show(self):
        pass

    def on_tick(self):
        """Every half second while the page is visible."""

    def on_processes(self, scripts, buffwatch):
        """The running scripts or BuffWatch changed (called for every page)."""


def scroll_body(master):
    """A transparent scrolling area for a page's content."""
    body = ctk.CTkScrollableFrame(master, fg_color="transparent",
                                  scrollbar_button_color=t.BORDER,
                                  scrollbar_button_hover_color=t.FAINT)
    body.grid_columnconfigure(0, weight=1)
    return body
