# Warframe toolkit

Three tools for Warframe on Windows, and one window to drive them:

| Folder | What it is |
| --- | --- |
| `Launcher.bat`, `launcher/` | **Start here.** One window to generate, run, watch and stop the macros, and to start BuffWatch. |
| `macros/` | AutoHotkey v1 toggle macros, written as JSON and turned into `.ahk` scripts by `ahkgen.ps1`. |
| `buff_watch/` | **BuffWatch**: magnified buff/debuff overlay and ability timers with auto-recast. See [buff_watch/README.md](buff_watch/README.md). |

```
warframe_macros/
├─ Launcher.bat            double-click to open the launcher
├─ launcher/               the launcher (Python, customtkinter)
├─ macros/
│  ├─ ahkgen.ps1           the generator (ahkgen.bat = drag a JSON onto it)
│  ├─ ahkgen.schema.json   what a config may contain (editors use it for hints)
│  ├─ configs/             one JSON per set of macros
│  └─ generated/           the .ahk scripts made from them (not in git)
├─ buff_watch/             BuffWatch, with its own README
└─ TODO.md                 things to do later
```

## The launcher

Needs Python 3.9+ (the same one BuffWatch uses) and, to run macros,
[AutoHotkey **v1.1**](https://www.autohotkey.com/download/). Double-click **`Launcher.bat`**.
The first time it makes a private `launcher\.venv` and installs its three packages
(customtkinter, psutil, Pillow); after that it opens straight away.

- **Macros**: one card per file in `macros/configs`, with its hotkeys and whether its script
  is generated, out of date (the JSON changed since) or running. *Run* regenerates first when
  needed. *Edit* opens the JSON; *New config* starts one from a template.
- **Running**: every AutoHotkey script running on the PC, including ones started by
  double-clicking an `.ahk`, with *Restart*, *Stop* and *Stop all*.
- **BuffWatch**: start, stop or restart it, and open its settings folder. Stopping closes it
  the normal way, so it saves its settings first.
- **Settings**: where AutoHotkey is (found automatically when installed normally), which
  editor opens the JSON files, and whether BuffWatch runs from its source folder or from a
  built `BuffWatch.exe`.

Scripts and BuffWatch keep running when you close the launcher. Its own settings are in
`launcher\settings.json`.

## Macros without the launcher

Drag a JSON from `macros\configs` onto `macros\ahkgen.bat`; the script is written next to the
JSON. Or from a terminal:

```
powershell -ExecutionPolicy Bypass -File macros\ahkgen.ps1 macros\configs\vauban_auto.json -Output macros\generated\vauban_auto.ahk
```

Each macro has a toggle hotkey and a list of steps (`tap`, `hold`, `wait`, `down`, `up`,
`send`), optionally with random `jitter`. Macros that share a `channel` never run at the same
time. `macros/ahkgen.schema.json` documents every field; VS Code shows those notes while you
edit a config.

## Tests

```
cd launcher   &&  python -m pytest tests
cd buff_watch &&  python -m pytest tests
```
