# Buff icon catalog

`icons/` and `catalog.json` come from Semlar's buff icon list,
<https://semlar.com/buffs>. The icons themselves are Warframe game textures
(© Digital Extremes).

`catalog.json` lists one entry per icon:

```json
{"file": "<png in icons/>", "names": ["Buff A", "Buff B"], "source": "<original url>"}
```

When `names` has several entries, all of those buffs use the same icon in game.

To refresh it after the site is updated:

```
.venv\Scripts\python.exe tools\import_semlar.py
```

Icons that are already downloaded are kept, so a refresh only fetches new ones.
