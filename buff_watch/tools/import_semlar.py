"""Builds buff_watch/catalog/ from the buff icon list at https://semlar.com/buffs.

    python tools/import_semlar.py            # download page + icons
    python tools/import_semlar.py --html F   # parse a saved copy of the page instead

Writes catalog/icons/<texture name>.png and catalog/catalog.json:
    [{"file": "...png", "names": ["Tenno Affinity", ...], "source": "<url>"}, ...]
Icons already downloaded are kept, so re-running only fetches new ones.
"""

import argparse
import html.parser
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

PAGE = "https://semlar.com/buffs"
HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(os.path.dirname(HERE), "catalog")
UA = {"User-Agent": "BuffWatch catalog importer"}


class _Parser(html.parser.HTMLParser):
    """Each icon is a <div class="thumbnail"> holding an <img> and a caption list
    whose <li> items are the buffs that use that icon."""

    def __init__(self):
        super().__init__()
        self.items = []
        self._depth = 0  # div depth inside the current thumbnail, 0 = outside
        self._cur = None
        self._li = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div":
            if self._depth:
                self._depth += 1
            elif "thumbnail" in (a.get("class") or "").split():
                self._depth = 1
                self._cur = {"src": None, "names": []}
        elif not self._depth:
            return
        elif tag == "img" and a.get("src") and self._cur["src"] is None:
            self._cur["src"] = a["src"]
        elif tag == "li":
            self._li = []

    def handle_endtag(self, tag):
        if not self._depth:
            return
        if tag == "li" and self._li is not None:
            name = re.sub(r"\s+", " ", "".join(self._li)).strip()
            if name:
                self._cur["names"].append(name)
            self._li = None
        elif tag == "div":
            self._depth -= 1
            if not self._depth:
                if self._cur["src"]:
                    self.items.append(self._cur)
                self._cur = None

    def handle_data(self, data):
        if self._li is not None:
            self._li.append(data)


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="saved copy of %s to parse instead of downloading" % PAGE)
    args = ap.parse_args()
    if args.html:
        with open(args.html, encoding="utf-8") as f:
            page = f.read()
    else:
        page = fetch(PAGE).decode("utf-8", "replace")

    p = _Parser()
    p.feed(page)
    icon_dir = os.path.join(CATALOG, "icons")
    os.makedirs(icon_dir, exist_ok=True)

    out, failed = [], 0
    for it in p.items:
        url = urllib.parse.urljoin(PAGE, it["src"])
        fname = os.path.basename(urllib.parse.urlparse(url).path)
        if not fname.lower().endswith(".png"):
            continue
        path = os.path.join(icon_dir, fname)
        if not os.path.exists(path):
            try:
                data = fetch(url)
            except OSError as ex:
                print("skip %s: %s" % (fname, ex), file=sys.stderr)
                failed += 1
                continue
            with open(path, "wb") as f:
                f.write(data)
            time.sleep(0.05)  # be polite to the site
        out.append({"file": fname, "names": it["names"] or [fname[:-4]], "source": url})

    with open(os.path.join(CATALOG, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print("%d icons in catalog, %d failed downloads" % (len(out), failed))


if __name__ == "__main__":
    main()
