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
- **Optional auto-press when a buff expires.** Give a buff a key and BuffWatch taps that key
  until the buff is back. This is opt-in automation; see below.
- **Ability timers.** BuffWatch also watches your four abilities in the bottom right, reads
  the seconds left on each active one, shows them in a second overlay, and can recast an
  ability when it runs out or a few seconds before. See *Abilities* below.

## Is this safe to use with Warframe?

Out of the box, BuffWatch only **looks at the screen**, the same way OBS, Discord screen
share or the Windows Snipping Tool do. Specifically, it:

- does **not** read or write the game's memory, inject anything, or hook into the game
- does **not** read or change game files or network traffic
- uses only ordinary Windows calls on **its own** windows (always on top, click-through,
  hidden from screen capture), plus a call that reads the position of the game window
- does **not** send any keyboard or mouse input **unless you turn on auto-press for a buff
  or an ability**

That puts it in the same category as screen recorders and streaming overlays, not cheats,
and it gives you no information you can't already see on your screen. Neither I nor anyone
outside Digital Extremes can guarantee how their anti-cheat behaves, but this is the
least-invasive kind of tool there is.

**Auto-press is different.** It sends simulated key presses (Windows `SendInput`, the same
thing AutoHotkey uses) in reaction to what is on screen. That's automation. It's still not a
memory hack, but Digital Extremes' rules on macros apply to it, so use it at your own risk.
It stays completely inactive until you assign a key to a buff.

## Auto-press when a buff expires

1. On the *Buffs* tab, select a buff and click **Auto-press key...**.
2. Set the **key** the ability or item is bound to in game. You can type it (`4`, `shift+e`,
   `f5`, `mouse4`...) or click *Record* and press it.
3. **Press every (ms)**: how long to wait between presses. Make it longer than the cast
   animation, because a second press can cancel or re-cast the ability.
4. **Give up after (presses)**: the most presses per expiry (default 5).

What happens in game:

- It starts only after BuffWatch has seen the buff **active** at least once. A buff you
  never cast doesn't trigger anything.
- When the buff disappears, the key is tapped right away, then every *interval* until the
  buff shows up again. "Right away" means after one missed scan (about 0.1s at 8 scans/s);
  the overlay waits longer before greying a buff out, to hide flicker. The *Auto-press* tab
  sets how many scans auto-press waits. The overlay shows `pressing 4 (2/5)` under the buff.
- After the maximum number of presses it gives up (out of energy, in a menu, ability
  blocked...). It re-arms once it sees the buff again.
- By default it only presses while the **Warframe window is focused**, so alt-tabbing to
  Discord or a browser pauses it. Chat windows inside the game still count as focused, so
  switch it off before typing a long message.
- **F8** (configurable on the *Auto-press* tab) turns auto-press on or off from inside the
  game. While it's off, the overlay shows `AUTO-PRESS OFF`. The hotkey uses Windows'
  `RegisterHotKey`, not a keyboard hook.

## Abilities

While an ability is active, Warframe shows the seconds left over its icon ("41", or "9.4"
under ten seconds). The **Skills** tab reads those numbers for all four abilities.

1. **Ability area.** The default fits a 16:9 screen at 100% HUD scale. If the Skills tab
   shows nothing, click **Select ability area...** and drag a box around the four ability
   icons: tight on the left and right (it is cut into four equal slots), tall enough to
   include the numbers.
2. **Cast an ability once.** The first clear timer tells BuffWatch how big the digits are
   on your screen ("HUD scale found"). After a resolution or HUD scale change, click
   **Re-detect HUD scale**.
3. **Capture ready icons** (optional) with every ability ready. BuffWatch then knows when the
   HUD is hidden (menus, cutscenes), so auto-press never fires there. It also captures a
   slot by itself the first time it is ready while another slot shows a timer.

**Skills overlay.** A second overlay shows the four slots magnified with the time left
under each. Drag it by its blue bar; the *Skills overlay* tab has the same size, layout,
font, colour and position options as the buff overlay, kept separately. Untick *In overlay*
on the Skills tab to leave a slot out.

**Auto-press per ability** (Skills tab):

- **Auto-press** on, and the **Key** the ability is bound to (1-4 by default).
- **Press early (s)**: press this many seconds before the timer ends. 0 = press when it ends.
- **Retry every (ms)** and **Give up after**: if no new timer shows up (no energy, blocked,
  in a menu), it presses again every interval, up to the limit. It re-arms once it sees the
  ability's timer again.
- **Hold key (ms)**: how long the key is held, for abilities you hold to cast.

It only presses for an ability after seeing its timer once, never while the HUD is hidden,
and uses the same on/off switch, F8 hotkey and "only while Warframe is focused" check as buff
auto-press. Abilities without a duration (no number) are never pressed.

**How the reading works.** The numbers are matched against digit pictures taken from real
screenshots, and each slot keeps its own countdown, so a misread frame doesn't throw it off.
The bundled digits don't include **3** yet; BuffWatch learns missing digits from your own
running timers (the countdown says what the number must be), and the Skills tab lists the
digits it knows. Until it knows a digit, a timer showing it is kept alive from the countdown
for up to 3 seconds instead of being treated as ended.

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
4. **Overlay tab.** Drag the overlay by its blue bar to where you want it (or use the
   snap-to-corner buttons), then tick **Lock overlay** so mouse clicks go through it to the
   game. The tab also sets the zoom, a vertical, horizontal or grid layout, spacing, font,
   name position, colours, opacity and how dim off buffs look. Every change shows at once.
   **Corner that stays put** decides which corner of the overlay keeps its place while buffs
   come and go: pick bottom-right for an overlay in the bottom-right of the screen.

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
- **Organising the Buffs list.** Drag rows to reorder them; the overlay shows pinned buffs
  in the same order. *New group...* makes a collapsible group (the selected buffs go into
  it), and you can drag buffs between groups or drag a group's header to move the whole
  group. Select a header to rename or delete it. Groups only tidy the list, they don't
  change what the overlay shows.
- The live preview at the top of the window draws boxes around icons: green for known buffs,
  grey for ignored icons, yellow for new ones.

## Testing without the game

`tests/test_skills.py` checks the ability-timer reader on HUD crops from real screenshots:

```
.venv\Scripts\python.exe tests\test_skills.py
```

To run the whole app on screenshots instead of the screen:

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
