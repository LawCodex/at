# LawCodex — Österreich / Austria (`at`)

Austrian legislation as plain Markdown: the complete **consolidated federal law in force**
(*Bundesrecht konsolidiert*) and the complete **consolidated law of the nine Länder**
(*Landesrecht konsolidiert*), taken from the official Legal Information System of the Republic
of Austria (RIS, Rechtsinformationssystem des Bundes), version in force on **2026-10-11**.

Part of [LawCodex](https://github.com/LawCodex) — one repository per jurisdiction.

## Contents

### Bundesrecht (federal law) — 10,690 laws/instruments from 158,867 RIS documents

| Directory | Contents | Files | RIS documents |
|---|---|---:|---:|
| `bundesrecht/verfassung/` | Verfassungsrecht (B-VG, Bundesverfassungsgesetze / Landesverfassungen, L-VG) | 45 | 617 |
| `bundesrecht/gesetze/` | Gesetze (Bundesgesetze BG / Landesgesetze LG) | 1,729 | 57,511 |
| `bundesrecht/verordnungen/` | Verordnungen | 4,100 | 38,931 |
| `bundesrecht/staatsvertraege/` | Staatsverträge (bi- und multilateral) | 3,165 | 56,820 |
| `bundesrecht/vereinbarungen-art-15a/` | Vereinbarungen gem. Art. 15a B-VG | 77 | 1,320 |
| `bundesrecht/kundmachungen/` | Kundmachungen (inkl. Geltungsbereich) | 1,555 | 3,412 |
| `bundesrecht/sonstige/` | Sonstige (Entschließungen, Geschäftsordnungen, Satzungen …) | 19 | 256 |

The Federal Constitutional Act (B-VG) is
[`bundesrecht/verfassung/b-vg.md`](bundesrecht/verfassung/b-vg.md); the other federal
constitutional laws (StGG, Neutralitäts-BVG, BVG Rundfunk, …) sit next to it.

### Landesrecht (law of the Länder) — 8,409 laws/instruments from 110,438 RIS documents

| Land | verfassung | gesetze | verordnungen | staatsvertraege | vereinbarungen-art-15a | kundmachungen | sonstige | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Burgenland (`burgenland/`) | 9 | 241 | 1,029 | 0 | 78 | 95 | 3 | **1,455** |
| Kärnten (`kaernten/`) | 1 | 197 | 518 | 0 | 0 | 59 | 0 | **775** |
| Niederösterreich (`niederoesterreich/`) | 8 | 179 | 400 | 0 | 0 | 445 | 63 | **1,095** |
| Oberösterreich (`oberoesterreich/`) | 13 | 171 | 596 | 0 | 58 | 37 | 10 | **885** |
| Salzburg (`salzburg/`) | 7 | 274 | 733 | 0 | 69 | 108 | 0 | **1,191** |
| Steiermark (`steiermark/`) | 13 | 237 | 823 | 0 | 48 | 11 | 0 | **1,132** |
| Tirol (`tirol/`) | 2 | 193 | 354 | 0 | 0 | 58 | 13 | **620** |
| Vorarlberg (`vorarlberg/`) | 6 | 133 | 591 | 0 | 13 | 16 | 40 | **799** |
| Wien (`wien/`) | 0 | 171 | 225 | 0 | 0 | 61 | 0 | **457** |
| **Summe** | **59** | **1,796** | **5,269** | **0** | **266** | **890** | **129** | **8,409** |

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

## Notes and known limitations

* Categories follow the RIS field *Typ* as recorded by RIS. Re-promulgated laws
  (*Wiederverlautbarungen*) are typed "Kundmachung" in RIS and therefore sit in `kundmachungen/`
  (e.g. the Wiener Stadtverfassung: `landesrecht/wien/kundmachungen/1968/wstv.md`); some
  Länder record Art. 15a agreements as LG or K. Every file carries the original `ris_type`.
* Heading levels are derived from RIS markup (`g1`, `g2`, `g1min`, `art`, `para`), which is
  not applied uniformly across all laws; a few laws therefore have uneven heading levels.
  Paragraph labels in headings come from the RIS field "§/Artikel/Anlage"; the original
  paragraph symbol remains in the text (`§ 1. (1) …`).
* Enumerations (Z 1, lit. a, –) are kept as separate paragraphs with their original symbols,
  not as Markdown lists.

## Not covered

* Repealed law and historical versions (only the version in force on 2026-10-11 is included;
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
* Retrieved: 2026-10-11.

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
