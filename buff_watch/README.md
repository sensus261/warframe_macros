# BuffWatch

Warframe shows a lot of buff and debuff icons in the top-right corner, and finding the one
you care about (Eclipse, Roar, an arcane stack...) in that pile is hard. BuffWatch watches that
corner of the screen, recognises the icons you taught it, and shows the ones you pick
**magnified in a small overlay** wherever you put it, with the number under each icon included.

- **Live magnified view.** The overlay shows the real pixels from the game, so stack counts,
  percentages and timers stay current without any OCR.
- **"Off" state.** A pinned buff that isn't active stays in the overlay, dimmed. Tick
  *Warn when missing* and its name turns red with a red border, so a buff that runs out is
  easy to spot. The border also flashes yellow briefly when a buff turns on or off.
- **Built-in catalog of ~270 buff icons** (from [semlar.com/buffs](https://semlar.com/buffs)).
  When a new icon shows up, BuffWatch looks it up in the catalog:
  - **Certain match:** it's named automatically, for example "Recognised: Mod: Growing
    Power" in the status bar.
  - **Possible matches:** the *New icons* tab shows the top candidates as one-click buttons.
  - **No match:** you type a name, or mark it "not a buff". The catalog is from around 2020,
    so newer arcanes and Incarnon/Citrine-era buffs often aren't in it.
- **Add buffs before you see them.** *Buffs → Add from catalog...* lets you search by name
  and pin a buff right away. The first time it appears in game, BuffWatch confirms it and
  switches to how the icon really looks on your screen.
- **You choose what to magnify.** On the *Buffs* tab, double-click rows (or select several
  and press *Show / hide in overlay*) to choose which buffs appear big in the overlay.

## Is this safe to use with Warframe?

BuffWatch only **looks at the screen**, the same way OBS, Discord screen share or the
Windows Snipping Tool do. Specifically, it:

- does **not** read or write the game's memory, inject anything, or hook into the game
- does **not** send any keyboard or mouse input (it doesn't automate anything)
- does **not** read or change game files or network traffic
- uses only ordinary Windows calls on **its own** windows (always on top, click-through,
  hidden from screen capture), plus a call that reads the position of the game window

That puts it in the same category as screen recorders and streaming overlays, not cheats,
and it gives you no information you can't already see on your screen. Neither I nor anyone
outside Digital Extremes can guarantee how their anti-cheat behaves, but this is the
least-invasive kind of tool there is.

## Install & run (Windows 10/11)

1. Install **Python 3.9 or newer** from <https://www.python.org/downloads/> and tick
   *"Add python.exe to PATH"* during setup.
2. Double-click **`run.bat`**. The first run creates a private `.venv` folder and installs
   the dependencies (numpy, opencv-python, mss, Pillow). Later runs start right away.
3. Optional: run **`build_exe.bat`** to get a standalone `dist\BuffWatch\BuffWatch.exe`.

In Warframe, set **Display Mode to Borderless Fullscreen** (or Windowed). Windows can't draw
other windows on top of exclusive fullscreen, and capturing it may give a black image.

## First-time setup

1. **Capture.** Pick the monitor Warframe runs on. You can also pick *Window* to follow the
   game window by its title (useful for windowed mode).
2. **Select buff area.** Drag a box around the buff icons in the top right. Make it wider
   than you need on the left, because the list grows leftwards as more buffs stack up. Stop
   it before the health/shield numbers. You only need to do this again if you change
   resolution or HUD scale.
3. **Teach icons.** Most common buffs get named by themselves once they appear. For the
   rest, or to pin buffs ahead of time, *Add from catalog...* on the Buffs tab is quickest.
   Other ways:
   - Wait. Icons that stay still for a moment show up in **New icons**. Type a name and
     click *Save + show in overlay*. If the box cuts off the icon or includes the number,
     click *Fix the box...* first. For things that aren't buffs, click
     *Not a buff (ignore forever)* and you won't be asked again.
   - Click **Teach icon...** at the top, drag a tight box around one icon (just the symbol,
     not the number), and name it. It's easiest with the buff active and the game paused
     or with you standing still.
4. **Overlay tab.** Drag the overlay by its blue bar to where you want it, set the zoom,
   then tick **Lock overlay** so mouse clicks go through it to the game.

Your icons and settings are saved in the `data` folder next to the program. To back them
up or share them, copy that folder.

## Tuning

- **Detection tab: Default match threshold** (0.70). Raise it if one buff gets mistaken
  for a similar-looking one. Lower it if a buff isn't found. You can also set a threshold
  per buff on the *Buffs* tab.
- **Detection tab, catalog options.** *Name new icons by myself* turns the automatic naming
  on or off. *Only ask about icons that are in the catalog* stops BuffWatch asking about
  anything the catalog doesn't know. That cuts false alarms, but it also hides newer buffs.
- **Coloured icon** (Buffs tab). Matching normally looks only at white/grey pixels so the
  scenery behind the HUD doesn't interfere. Turn this on for an icon that isn't white.
- **Frames a buff may be unseen before it counts as off.** Stops the overlay flickering
  when an icon is briefly covered by a damage number or a flash.
- **Scans per second.** 8 is plenty and costs very little CPU, because only the small buff
  area is captured.
- The live preview at the top of the window draws boxes around icons: green for known buffs,
  grey for ignored icons, yellow for new ones.

## Testing without the game

```
.venv\Scripts\python.exe buffwatch.pyw --image path\to\screenshot.png
```

This uses a screenshot (or a folder of screenshots) instead of the screen. It's handy for
teaching icons from screenshots you took earlier (F6 in Warframe).

## Limitations

- **Shared icons.** Many buffs share one icon. For example, one generic icon is used by
  ~57 arcanes and another by ~17 mods (Berserker, Gorgon Frenzy...). BuffWatch can tell that
  "one of them" is active, but not which. When you name one, pick the buff you actually use
  from the drop-down list.

- Icons are matched at the size they were taught. If you change resolution or the HUD
  scale, teach them again (or keep separate `data` folders).
- Some icons share the same symbol and differ only by colour or number. White-only matching
  can't tell those apart; try *Coloured icon* for them.
- Automatic discovery is a best guess. Buff icons overlap their numbers and each other, so
  the suggested box sometimes needs *Fix the box...*.
