#!/usr/bin/env python3
"""Regenerate README.md with counts from the generated corpus."""
import collections
import datetime as dt
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CATS = [
    ("verfassung", "Verfassungsrecht (B-VG, Bundesverfassungsgesetze / Landesverfassungen, L-VG)"),
    ("gesetze", "Gesetze (Bundesgesetze BG / Landesgesetze LG)"),
    ("verordnungen", "Verordnungen"),
    ("staatsvertraege", "Staatsverträge (bi- und multilateral)"),
    ("vereinbarungen-art-15a", "Vereinbarungen gem. Art. 15a B-VG"),
    ("kundmachungen", "Kundmachungen (inkl. Geltungsbereich)"),
    ("sonstige", "Sonstige (Entschließungen, Geschäftsordnungen, Satzungen …)"),
]
LAENDER = [("burgenland", "Burgenland"), ("kaernten", "Kärnten"), ("niederoesterreich", "Niederösterreich"),
           ("oberoesterreich", "Oberösterreich"), ("salzburg", "Salzburg"), ("steiermark", "Steiermark"),
           ("tirol", "Tirol"), ("vorarlberg", "Vorarlberg"), ("wien", "Wien")]


def count(path):
    n = 0
    docs = 0
    if not os.path.isdir(path):
        return 0, 0
    for dp, _, fns in os.walk(path):
        for fn in fns:
            if fn.endswith(".md"):
                n += 1
                with open(os.path.join(dp, fn), encoding="utf-8") as f:
                    head = f.read(3000)
                m = re.search(r"^documents: (\d+)$", head, re.M)
                docs += int(m.group(1)) if m else 0
    return n, docs


def main():
    retrieved = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
    rows_b = []
    tb = td = 0
    for c, label in CATS:
        n, d = count(os.path.join(ROOT, "bundesrecht", c))
        if n:
            rows_b.append(f"| `bundesrecht/{c}/` | {label} | {n:,} | {d:,} |")
            tb += n
            td += d
    rows_l = []
    tl = tld = 0
    land_cats = collections.Counter()
    for slug, name in LAENDER:
        cells = []
        tot = 0
        for c, _ in CATS:
            n, d = count(os.path.join(ROOT, "landesrecht", slug, c))
            cells.append(f"{n:,}")
            tot += n
            tld += d
            land_cats[c] += n
        tl += tot
        rows_l.append(f"| {name} (`{slug}/`) | " + " | ".join(cells) + f" | **{tot:,}** |")
    rows_l.append("| **Summe** | " + " | ".join(f"**{land_cats[c]:,}**" for c, _ in CATS) + f" | **{tl:,}** |")

    text = f"""# LawCodex — Österreich / Austria (`at`)

Austrian legislation as plain Markdown: the complete **consolidated federal law in force**
(*Bundesrecht konsolidiert*) and the complete **consolidated law of the nine Länder**
(*Landesrecht konsolidiert*), taken from the official Legal Information System of the Republic
of Austria (RIS, Rechtsinformationssystem des Bundes), version in force on **{retrieved}**.

Part of [LawCodex](https://github.com/LawCodex) — one repository per jurisdiction.

## Contents

### Bundesrecht (federal law) — {tb:,} laws/instruments from {td:,} RIS documents

| Directory | Contents | Files | RIS documents |
|---|---|---:|---:|
{chr(10).join(rows_b)}

The Federal Constitutional Act (B-VG) is
[`bundesrecht/verfassung/b-vg.md`](bundesrecht/verfassung/b-vg.md); the other federal
constitutional laws (StGG, Neutralitäts-BVG, BVG Rundfunk, …) sit next to it.

### Landesrecht (law of the Länder) — {tl:,} laws/instruments from {tld:,} RIS documents

| Land | {" | ".join(c for c, _ in CATS)} | Total |
|---|{"---:|" * (len(CATS) + 1)}
{chr(10).join(rows_l)}

## Structure

```
bundesrecht/
  verfassung/<abbr>.md                      B-VG and other Bundesverfassungsgesetze (RIS type BVG)
  gesetze/<year>/<abbr-or-id>.md            Bundesgesetze (BG)
  verordnungen/<year>/<abbr-or-id>.md       Verordnungen (V)
  staatsvertraege/<year>/<id>-<title>.md    Staatsverträge (Vertrag – …)
  vereinbarungen-art-15a/<year>/...         Vereinbarungen gem. Art. 15a B-VG
  kundmachungen/<year>/...                  Kundmachungen (K, K (Geltungsbereich), Bekanntmachung)
  sonstige/<year>/...                       other RIS types
landesrecht/<land>/<same categories>/...
```

* `<year>` is the year of the original publication (*Stammfassung*, e.g. `BGBl. Nr. 60/1974` → `1974`);
  this keeps every directory under 1,000 entries.
* File names are the official abbreviation (*Abkürzung*, e.g. `stgb.md`, `abgb.md`) when RIS gives
  one and it is unique in its directory; otherwise `<Gesetzesnummer>-<short-title-slug>.md`.
  The RIS **Gesetzesnummer** (stable identifier of a consolidated law) is always in the front matter
  (`identifier`).
* Each file is assembled from the RIS documents of one Gesetzesnummer (one document per §,
  Artikel or Anlage, plus the header document "§ 0") in the official RIS order:
  title, *Langtitel* and *Stammfassung*, list of amendments (collapsed), *Präambel/Promulgationsklausel*,
  then the text. Structural headings (Teil, Hauptstück, Abschnitt …) become `##`/`###` headings;
  each §/Artikel/Anlage is a heading at the deepest level (`§ 1 – Überschrift`). Per-paragraph
  *Anmerkung* and *Beachte* notes from RIS are kept as block quotes.
* Tables are kept as HTML when they have merged cells, otherwise Markdown. Images (formulas, signs,
  forms) are linked to the official RIS server (`ogd.ris.bka.gv.at`), not copied.
* Front matter: `title`, `abbreviation`, `identifier` (Gesetzesnummer), `type`
  (constitution/act/regulation/treaty/agreement/notice/other), `ris_type` (RIS "Typ"),
  `jurisdiction` (`at`, or `at-1` … `at-9` = ISO 3166-2 code of the Land), `promulgation`
  (Stammfassung), `date` (date in the Langtitel, when present), `last_amended` (latest
  in-force date of any of its documents), `last_amendment` (latest amending Gazette),
  `consolidated` (RIS version date), `eli`, `source` (RIS "Gesamte Rechtsvorschrift" page),
  `retrieved`, `documents` (number of RIS documents merged).

## Not covered

* Repealed law and historical versions (only the version in force on {retrieved} is included;
  RIS has full point-in-time history — re-run the scripts with another `--date`).
* Gazettes (BGBl./LGBl. authentic PDF publications), case law (Judikatur), Gemeinderecht,
  Erlässe, Begutachtungsentwürfe, EU law.
* Images are not mirrored (linked to RIS); a few legacy documents in RIS consist only of images.
* The *consolidated* RIS text is informative; only the Bundesgesetzblatt / Landesgesetzblätter
  are legally authentic.

## Source and licence

* Source: RIS — Rechtsinformationssystem des Bundes, Bundeskanzleramt, via the open-data
  API (OGD) <https://data.bka.gv.at/ris/api/v2.6/> (applications `BrKons` and `LrKons`) and the
  document server <https://ogd.ris.bka.gv.at/>. Web: <https://www.ris.bka.gv.at/>.
* Legal texts are not subject to copyright in Austria (§ 7 UrhG: "Gesetze, Verordnungen, amtliche
  Erlässe und Bekanntmachungen … genießen keinen urheberrechtlichen Schutz"). RIS OGD data is
  published under **Creative Commons Attribution 4.0 (CC BY 4.0)** — attribution:
  "Datenquelle: Rechtsinformationssystem des Bundes (RIS), Bundeskanzleramt, data.bka.gv.at".
* Retrieved: {retrieved}.

## Regenerate

```sh
pip install -r scripts/requirements.txt
python scripts/fetch.py list --date YYYY-MM-DD   # search API -> ../_raw/at/list/  (~2,700 pages)
python scripts/fetch.py docs                     # one XML per document -> ../_raw/at/xml/ (~270k files, ~5 h at 4 connections)
python scripts/convert.py --retrieved YYYY-MM-DD # -> bundesrecht/, landesrecht/
python scripts/readme.py YYYY-MM-DD              # refresh this README
```

The fetcher uses a descriptive User-Agent, at most 4 parallel connections, retries with
exponential backoff and caches everything under `../_raw/at/` so re-runs only fetch what is
missing. Delete the old `list/` directory before refreshing to a new date.
"""
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"bund {tb} files, land {tl} files")


if __name__ == "__main__":
    main()
