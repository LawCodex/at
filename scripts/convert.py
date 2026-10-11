#!/usr/bin/env python3
"""Convert cached RIS documents (see fetch.py) into one Markdown file per law.

RIS publishes consolidated law as one XML document per paragraph / article /
annex ("Paragraph") plus a header document ("Norm", § 0) per law, all sharing a
Gesetzesnummer. The search listing returns them grouped per law in the
official order; this script reassembles each law in that order.

Usage: convert.py [--raw DIR] [--out DIR] [--scope bund|land|all] [--retrieved YYYY-MM-DD]
"""
import argparse
import collections
import datetime as dt
import html
import json
import os
import re
import sys
import unicodedata

from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch import iter_refs  # noqa: E402

NS = "{http://www.bka.gv.at}"
IMG_BASE = "https://ogd.ris.bka.gv.at"
RIS_WEB = "https://www.ris.bka.gv.at"

LAENDER = {
    "Burgenland": ("burgenland", "at-1"),
    "Kärnten": ("kaernten", "at-2"),
    "Niederösterreich": ("niederoesterreich", "at-3"),
    "Oberösterreich": ("oberoesterreich", "at-4"),
    "Salzburg": ("salzburg", "at-5"),
    "Steiermark": ("steiermark", "at-6"),
    "Tirol": ("tirol", "at-7"),
    "Vorarlberg": ("vorarlberg", "at-8"),
    "Wien": ("wien", "at-9"),
}

MONTHS = {"jänner": 1, "januar": 1, "februar": 2, "feber": 2, "märz": 3, "april": 4, "mai": 5,
          "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
          "november": 11, "dezember": 12}

# section headings ("ueberschrift typ=titel") in RIS documents -> key
SECTIONS = {
    "Text": "text", "Präambel/Promulgationsklausel": "prae", "Ratifikationstext": "ratifikation",
    "Sonstige Textteile": "sonstige", "Anmerkung": "anmerkung", "Beachte": "beachte",
    "Langtitel": "langtitel", "Änderung": "aenderung", "Unterzeichnungsdatum": "unterzeichnung",
    "Sprachen": "sprachen", "Vertragsparteien": "vertragsparteien",
}

STRUCT_ORDER = ["g1", "g2", "g3", "g4", "g5", "art"]

unknown_tags = collections.Counter()


# --------------------------------------------------------------------------- helpers

def slugify(s, maxlen=80):
    s = s.replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    s = s.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    if len(s) > maxlen:
        s = s[:maxlen].rsplit("-", 1)[0]
    return s


def norm_ws(s):
    s = s.replace(" ", " ")
    s = re.sub(r"[ \t\r\n]+", " ", s)
    return s.strip()


def md_escape(s):
    s = s.replace("\\", "\\\\")
    s = re.sub(r"([*_`])", r"\\\1", s)
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    return s


def escape_line_start(s):
    """Prevent paragraph text being parsed as list / heading / quote."""
    m = re.match(r"^(\d{1,9})([.)])(\s|$)", s)
    if m:
        return m.group(1) + "\\" + s[len(m.group(1)):]
    if re.match(r"^([-+#>=]|\*)", s):
        return "\\" + s
    return s


def yaml_str(s):
    return json.dumps(s, ensure_ascii=False)


def local(e):
    return e.tag[len(NS):] if isinstance(e.tag, str) and e.tag.startswith(NS) else e.tag


# --------------------------------------------------------------------------- inline rendering

def inline(e, mode="md"):
    """Render the content of element e (text + children) as inline markdown or html."""
    out = []
    if e.text:
        out.append(md_escape(e.text) if mode == "md" else html.escape(e.text, quote=False))
    for c in e:
        out.append(inline_el(c, mode))
        if c.tail:
            out.append(md_escape(c.tail) if mode == "md" else html.escape(c.tail, quote=False))
    return "".join(out)


def wrap(mode, inner, md_l, md_r, tag):
    if not inner.strip():
        return inner
    if mode == "md":
        lead = inner[: len(inner) - len(inner.lstrip())]
        trail = inner[len(inner.rstrip()):]
        return f"{lead}{md_l}{inner.strip()}{md_r}{trail}"
    return f"<{tag}>{inner}</{tag}>"


def inline_el(c, mode):
    t = local(c)
    if not isinstance(t, str):
        return ""
    if t == "b":
        return wrap(mode, inline(c, mode), "**", "**", "b")
    if t == "i":
        return wrap(mode, inline(c, mode), "*", "*", "i")
    if t == "u":
        return f"<u>{inline(c, mode)}</u>"
    if t == "super":
        return f"<sup>{inline(c, mode)}</sup>"
    if t == "sub":
        return f"<sub>{inline(c, mode)}</sub>"
    if t in ("gldsym", "n", "gs", "span", "feld", "aw", "fnoten", "fnotenref", "kursiv", "fett"):
        return inline(c, mode)
    if t == "symbol":
        return inline(c, mode) + " "
    if t in ("nbsp", "tab"):
        return " "
    if t == "gdash":
        return "–"
    if t == "gt":
        return "&gt;"
    if t == "lt":
        return "&lt;"
    if t == "amp":
        return "&amp;"
    if t == "br":
        return "<br>"
    if t == "link":
        txt = inline(c, mode)
        href = c.get("href", "")
        if href.startswith("http") and mode == "md" and txt.strip():
            return f"[{txt}]({href.replace(' ', '%20').replace(')', '%29')})"
        if href.startswith("http") and mode == "html":
            return f'<a href="{html.escape(href)}">{txt}</a>'
        return txt
    if t == "binary":
        src = c.findtext(NS + "src") or ""
        alt = c.get("alt") or "Abbildung"
        if src:
            url = IMG_BASE + src if src.startswith("/") else src
            if mode == "md":
                return f"![{md_escape(alt)}]({url})"
            return f'<img src="{html.escape(url)}" alt="{html.escape(alt)}">'
        return ""
    if t == "src":
        return ""
    if t == "table":
        return render_table(c)
    unknown_tags[t] += 1
    return inline(c, mode)


def para_text(e, mode="md"):
    s = inline(e, mode)
    s = s.replace(" ", " ")
    if mode == "md":
        # keep <br> as hard line break
        parts = [norm_ws(p) for p in s.split("<br>")]
        return "  \n".join(p for p in parts)
    return norm_ws(s)


# --------------------------------------------------------------------------- tables

def cell_html(td):
    parts = []
    for b in td:
        t = local(b)
        if t in ("absatz", "schluss", "schlussteil", "inhaltsvz", "ueberschrift"):
            parts.append(para_text(b, "html"))
        elif t == "liste":
            for le in b.iter(NS + "listelem", NS + "schluss", NS + "schlussteil"):
                parts.append(para_text(le, "html"))
        elif t == "table":
            parts.append(render_table(b))
        else:
            parts.append(norm_ws(inline_el(b, "html")))
    return "<br>".join(p for p in parts if p)


def cell_md(td):
    parts = []
    for b in td:
        t = local(b)
        if t in ("absatz", "schluss", "schlussteil", "inhaltsvz", "ueberschrift"):
            parts.append(para_text(b, "md").replace("  \n", "<br>"))
        else:
            return None
    s = "<br>".join(p for p in parts if p)
    return s.replace("|", "\\|")


def render_table(tbl):
    rows = [tr for tr in tbl if local(tr) == "tr"]
    if not rows:
        return ""
    cells = [[td for td in tr if local(td) in ("td", "th")] for tr in rows]
    simple = (all(len(r) == len(cells[0]) for r in cells) and len(cells[0]) > 1 and
              not any(td.get("colspan") or td.get("rowspan") for r in cells for td in r))
    if simple:
        md = [[cell_md(td) for td in r] for r in cells]
        if all(x is not None for r in md for x in r):
            ncol = len(md[0])
            lines = ["| " + " | ".join(md[0]) + " |", "|" + "---|" * ncol]
            for r in md[1:]:
                lines.append("| " + " | ".join(r) + " |")
            return "\n".join(lines)
    out = ["<table>"]
    for r in cells:
        out.append("<tr>")
        for td in r:
            attrs = ""
            for a in ("colspan", "rowspan"):
                if td.get(a) and td.get(a) != "1":
                    attrs += f' {a}="{td.get(a)}"'
            out.append(f"<td{attrs}>{cell_html(td)}</td>")
        out.append("</tr>")
    out.append("</table>")
    return "\n".join(out)


# --------------------------------------------------------------------------- document parsing

def parse_doc(path):
    """Return dict section -> list of block elements, in document order."""
    tree = etree.parse(path)
    secs = collections.OrderedDict()
    cur = None
    for ab in tree.getroot().iter(NS + "abschnitt"):
        for b in ab:
            t = local(b)
            if t in ("kzinhalt", "fzinhalt") or not isinstance(t, str):
                continue
            if t == "ueberschrift" and b.get("typ") == "titel":
                cur = SECTIONS.get(norm_ws("".join(b.itertext())), "_meta")
                secs.setdefault(cur, [])
                continue
            if cur is None:
                continue
            secs[cur].append(b)
    return secs


def block_lines(b):
    """Render one non-heading block element as a list of markdown paragraphs."""
    t = local(b)
    if t in ("absatz", "schluss", "schlussteil", "inhaltsvz"):
        if t == "absatz" and b.get("typ") == "abbobj":
            s = para_text(b)
            return [s] if s else []
        if t == "absatz" and b.get("typ") == "pre":
            return ["`" + "".join(b.itertext()) + "`"]
        s = para_text(b)
        return [escape_line_start(s)] if s else []
    if t == "liste":
        out = []
        for c in b:
            ct = local(c)
            if ct in ("schluss", "schlussteil"):
                s = para_text(c)
                if s:
                    out.append(escape_line_start(s))
            elif isinstance(ct, str) and ct.endswith("liste") or ct == "aufzaehlung":
                for le in c:
                    if local(le) == "listelem":
                        s = para_text(le)
                        if s:
                            out.append(escape_line_start(s))
                    else:
                        out.extend(block_lines(le))
            else:
                out.extend(block_lines(c))
        return out
    if isinstance(t, str) and (t.endswith("liste") or t == "aufzaehlung"):
        out = []
        for le in b:
            if local(le) == "listelem":
                s = para_text(le)
                if s:
                    out.append(escape_line_start(s))
            else:
                out.extend(block_lines(le))
        return out
    if t == "listelem":
        s = para_text(b)
        return [escape_line_start(s)] if s else []
    if t == "table":
        s = render_table(b)
        return [s] if s else []
    if t == "abstand":
        return []
    if t == "ueberschrift":
        s = para_text(b)
        return [f"**{s}**"] if s else []
    unknown_tags["block:" + str(t)] += 1
    s = para_text(b)
    return [escape_line_start(s)] if s else []


def plain_lines(blocks):
    out = []
    for b in blocks:
        out.extend(block_lines(b))
    return out


# --------------------------------------------------------------------------- law assembly

def category(scope, typ):
    t = (typ or "").strip().lower()
    if t.startswith("vertrag"):
        return "staatsvertraege"
    if t.startswith("vereinbarung"):
        return "vereinbarungen-art-15a"
    if t in ("bvg", "b-vg", "lvg", "l-vg", "verfassungsgesetz", "landesverfassungsgesetz"):
        return "verfassung"
    if t in ("bg", "lg", "g", "gesetz", "landesgesetz"):
        return "gesetze"
    if t in ("v", "vo", "verordnung", "veordnung"):
        return "verordnungen"
    if t in ("k", "k (geltungsbereich)", "kundmachung", "ku", "bekanntmachung"):
        return "kundmachungen"
    return "sonstige"


DOC_TYPE = {"staatsvertraege": "treaty", "vereinbarungen-art-15a": "agreement",
            "verfassung": "constitution", "gesetze": "act", "verordnungen": "regulation",
            "kundmachungen": "notice", "sonstige": "other"}


def parse_date_from_title(s):
    m = re.search(r"\bvom (\d{1,2})\.\s*([A-Za-zäÄ]+)\s+(\d{4})", s or "")
    if m and m.group(2).lower() in MONTHS:
        try:
            return dt.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


class Law:
    def __init__(self, gesnr, land):
        self.gesnr = gesnr
        self.land = land
        self.refs = []  # (id, meta-dict)


def collect(raw, scope):
    laws = collections.OrderedDict()
    for _, ref in iter_refs(raw, scope):
        md = ref["Data"]["Metadaten"]
        top = md["Bundesrecht"] if scope == "bund" else md["Landesrecht"]
        k = top["BrKons"] if scope == "bund" else top["LrKons"]
        land = top.get("Bundesland") if scope == "land" else None
        key = (land, k["Gesetzesnummer"])
        if key not in laws:
            laws[key] = Law(k["Gesetzesnummer"], land)
        meta = dict(k)
        meta["Kurztitel"] = top.get("Kurztitel", "")
        meta["Titel"] = top.get("Titel", "")
        meta["Eli"] = top.get("Eli") or k.get("Eli")
        meta["ID"] = md["Technisch"]["ID"]
        laws[key].refs.append(meta)
    return laws


def render_law(law, xmldir, retrieved, fassung, scope):
    norm = next((m for m in law.refs if m.get("Dokumenttyp") == "Norm"), None)
    head = norm or law.refs[0]
    title = norm_ws(head.get("Kurztitel") or "") or f"Gesetzesnummer {law.gesnr}"
    abbr = norm_ws(head.get("Abkuerzung") or "")
    typ = norm_ws(head.get("Typ") or "")
    cat = category(scope, typ)

    # header doc sections
    hsecs = {}
    if norm:
        p = os.path.join(xmldir, norm["ID"] + ".xml")
        if os.path.exists(p):
            hsecs = parse_doc(p)
    langtitel = [para_text(b) for b in hsecs.get("langtitel", []) if para_text(b)]
    if not langtitel and head.get("Titel"):
        langtitel = [md_escape(norm_ws(x)) for x in re.split(r"<br\s*/?>", head["Titel"]) if norm_ws(x)]
    aenderung = [para_text(b) for b in hsecs.get("aenderung", []) if para_text(b)]

    # dates
    date = parse_date_from_title(" ".join(langtitel))
    ikras = [m.get("Inkrafttretensdatum") for m in law.refs if m.get("Inkrafttretensdatum")]
    ikras = [d for d in ikras if d <= fassung]
    last = max(ikras) if ikras else None
    last_amend = None
    for a in reversed(aenderung):
        m = re.match(r"^((?:BGBl|LGBl|StGBl|RGBl|GBlÖ|ABl)[^()]*?Nr\.?\s*[\w/.\-]+)", a.replace("\\", ""))
        if m:
            last_amend = m.group(1).strip()
            break

    # body
    struct_used = set()
    docs = []
    for m in law.refs:
        if m is norm:
            continue
        p = os.path.join(xmldir, m["ID"] + ".xml")
        if not os.path.exists(p):
            docs.append((m, None))
            continue
        secs = parse_doc(p)
        for b in secs.get("text", []):
            if local(b) == "ueberschrift" and b.get("typ") in STRUCT_ORDER:
                ty = b.get("typ")
                if ty == "art" and "§" not in (m.get("ArtikelParagraphAnlage") or ""):
                    continue
                struct_used.add(ty)
        docs.append((m, secs))
    levels = {ty: i + 2 for i, ty in enumerate([t for t in STRUCT_ORDER if t in struct_used])}
    art_level = 2 + len(levels)

    def hx(level, text):
        if level <= 6:
            return "#" * level + " " + text
        return f"**{text}**"

    out = []
    out.append(f"# {md_escape(title)}" + (f" ({md_escape(abbr)})" if abbr and abbr not in title else ""))
    out.append("")
    for lt in langtitel:
        out.append(escape_line_start(lt))
        out.append("")
    for key, label in (("unterzeichnung", "Unterzeichnungsdatum"), ("vertragsparteien", "Vertragsparteien"),
                       ("sprachen", "Sprachen")):
        lines = plain_lines(hsecs.get(key, []))
        if lines:
            out.append(f"**{label}:** " + " ".join(lines))
            out.append("")
    if aenderung:
        out.append("<details>\n<summary>Änderungen</summary>\n")
        for a in aenderung:
            out.append(escape_line_start(a) + "  ")
        out.append("\n</details>")
        out.append("")
    for key in ("anmerkung", "beachte"):
        lines = plain_lines(hsecs.get(key, []))
        if lines:
            out.append(f"> **{'Anmerkung' if key == 'anmerkung' else 'Beachte'}:** " + "\n>\n> ".join(lines))
            out.append("")
    prae = hsecs.get("prae", []) + hsecs.get("text", [])
    if prae:
        out.append(hx(2, "Präambel/Promulgationsklausel"))
        out.append("")
        for line in render_text_blocks(prae, None, levels, art_level, hx, header=True):
            out.append(line)
            out.append("")

    last_art = None
    for m, secs in docs:
        label = norm_ws(m.get("ArtikelParagraphAnlage") or "")
        if secs is None:
            out.append(hx(art_level, md_escape(label)))
            out.append("")
            out.append("*(Dokument nicht verfügbar)*")
            out.append("")
            continue
        state = {"last_art": last_art}
        for line in render_text_blocks(secs.get("text", []), m, levels, art_level, hx, state=state):
            out.append(line)
            out.append("")
        last_art = state["last_art"]
        for key, lab in (("ratifikation", "Ratifikationstext"), ("sonstige", "Sonstige Textteile")):
            lines = plain_lines(secs.get(key, []))
            if lines:
                out.append(f"**{lab}:**")
                out.append("")
                for ln in lines:
                    out.append(ln)
                    out.append("")
        for key, lab in (("anmerkung", "Anmerkung"), ("beachte", "Beachte")):
            lines = plain_lines(secs.get(key, []))
            if lines:
                out.append(f"> **{lab}:** " + "\n>\n> ".join(lines))
                out.append("")
    for key, lab in (("ratifikation", "Ratifikationstext"), ("sonstige", "Sonstige Textteile")):
        blocks = hsecs.get(key, [])
        if blocks:
            out.append(hx(2, lab))
            out.append("")
            for ln in plain_lines(blocks):
                out.append(ln)
                out.append("")

    body = "\n".join(out)
    body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"

    # front matter
    if scope == "bund":
        src = f"{RIS_WEB}/GeltendeFassung.wxe?Abfrage=Bundesnormen&Gesetzesnummer={law.gesnr}"
        jur = "at"
    else:
        u = head.get("GesamteRechtsvorschriftUrl") or ""
        src = u.replace("https://ogd.ris.bka.gv.at", RIS_WEB) if u else ""
        jur = LAENDER.get(law.land, ("", "at"))[1]
    fm = ["---", f"title: {yaml_str(title)}"]
    if abbr:
        fm.append(f"abbreviation: {yaml_str(abbr)}")
    fm.append(f"identifier: {yaml_str(law.gesnr)}")
    fm.append(f"type: {DOC_TYPE[cat]}")
    fm.append(f"ris_type: {yaml_str(typ)}")
    fm.append(f"jurisdiction: {jur}")
    if law.land:
        fm.append(f"land: {yaml_str(law.land)}")
    fm.append("language: de")
    stf = norm_ws(f"{head.get('StammnormPublikationsorgan') or ''} {head.get('StammnormBgblnummer') or ''}")
    if not stf and head.get("Kundmachungsorgan"):
        stf = norm_ws(head["Kundmachungsorgan"])
    if stf:
        fm.append(f"promulgation: {yaml_str(stf)}")
    if date:
        fm.append(f"date: {date}")
    if last:
        fm.append(f"last_amended: {last}")
    if last_amend:
        fm.append(f"last_amendment: {yaml_str(last_amend)}")
    fm.append(f"consolidated: {fassung}")
    fm.append("status: in_force")
    if head.get("Eli"):
        fm.append(f"eli: {yaml_str(head['Eli'])}")
    fm.append(f"source: {yaml_str(src)}")
    fm.append(f"retrieved: {retrieved}")
    fm.append(f"documents: {len(law.refs)}")
    fm.append("---")
    return cat, title, abbr, "\n".join(fm) + "\n\n" + body


def render_text_blocks(blocks, m, levels, art_level, hx, header=False, state=None):
    """Yield markdown paragraphs for the Text section of one document."""
    label = norm_ws(m.get("ArtikelParagraphAnlage") or "") if m else ""
    has_para = "§" in label
    pending_titles = []
    art_text = None
    anl_text = None
    started = header  # header docs: no doc heading
    last_struct = None
    out = []

    def emit_heading():
        nonlocal started
        if started:
            return
        main = None
        if art_text and not has_para:
            main = art_text
        elif anl_text and label.startswith("Anl"):
            main = anl_text
        else:
            main = md_escape(label)
            if anl_text:
                pending_titles.insert(0, anl_text)
            if art_text and not has_para:
                pending_titles.insert(0, art_text)
        t = main
        if pending_titles:
            t += " – " + " – ".join(pending_titles)
        out.append(hx(art_level, t.replace("\n", " ")))
        started = True

    for b in blocks:
        t = local(b)
        if t == "ueberschrift":
            ty = b.get("typ")
            txt = para_text(b).replace("  \n", " ")
            if not txt:
                continue
            if ty in ("g1min", "g2min", "g3min", "g4min") and last_struct is not None and out and out[-1] == last_struct[1]:
                merged = last_struct[1] + " — " + txt
                out[-1] = merged
                last_struct = (last_struct[0], merged)
                continue
            if ty in ("g1", "g2", "g3", "g4", "g5") and ty in levels:
                h = hx(levels[ty], txt)
                out.append(h)
                last_struct = (ty, h)
                continue
            if ty == "art" and has_para and not header:
                if state is not None and state.get("last_art") == txt and not started:
                    continue
                if "art" in levels and not started:
                    h = hx(levels["art"], txt)
                    out.append(h)
                    last_struct = ("art", h)
                    if state is not None:
                        state["last_art"] = txt
                    continue
            if not started and not header:
                if ty == "art" and art_text is None and not has_para:
                    art_text = txt
                    continue
                if ty == "anlage" and anl_text is None:
                    anl_text = txt
                    continue
                if ty in ("para", "art", "anlage", "g1min", "g2min"):
                    pending_titles.append(txt)
                    continue
            # heading inside body (or unmapped structural heading)
            emit_heading()
            out.append(f"**{txt}**")
            last_struct = None
            continue
        emit_heading()
        last_struct = None
        out.extend(block_lines(b))
    if not header:
        emit_heading()
    return out


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--raw", default=os.path.join(here, "..", "..", "_raw", "at"))
    ap.add_argument("--out", default=os.path.join(here, ".."))
    ap.add_argument("--scope", default="all", choices=["bund", "land", "all"])
    ap.add_argument("--retrieved", default=dt.date.today().isoformat())
    ap.add_argument("--only", help="comma-separated Gesetzesnummern (debug)")
    a = ap.parse_args()
    scopes = ["bund", "land"] if a.scope == "all" else [a.scope]
    only = set(a.only.split(",")) if a.only else None
    for scope in scopes:
        meta = json.load(open(os.path.join(a.raw, "list", scope, "meta.json")))
        fassung = meta["date"]
        xmldir = os.path.join(a.raw, "xml", scope)
        laws = collect(a.raw, scope)
        root = os.path.join(a.out, "bundesrecht" if scope == "bund" else "landesrecht")
        index = []
        used = collections.defaultdict(set)
        rendered = []
        for (land, gesnr), law in laws.items():
            if only and gesnr not in only:
                continue
            cat, title, abbr, text = render_law(law, xmldir, a.retrieved, fassung, scope)
            head = next((m for m in law.refs if m.get("Dokumenttyp") == "Norm"), law.refs[0])
            yr = re.search(r"/(\d{4})\b", head.get("StammnormBgblnummer") or "") or \
                re.search(r"(\d{4})", head.get("Kundmachungsorgan") or "")
            year = yr.group(1) if yr else "ohne-jahr"
            parts = [root]
            if land:
                parts.append(LAENDER[land][0])
            parts.append(cat)
            if cat != "verfassung":
                parts.append(year)
            d = os.path.join(*parts)
            rendered.append((d, gesnr, title, abbr, text, land, cat))
        # file names: abbreviation if unique within its directory, else gesnr + title slug
        abbr_count = collections.Counter((r[0], slugify(r[3], 60)) for r in rendered if r[3])
        for d, gesnr, title, abbr, text, land, cat in rendered:
            s = slugify(abbr, 60) if abbr else ""
            if s and abbr_count[(d, s)] == 1:
                name = s
            else:
                name = f"{gesnr}-{slugify(title, 70)}".rstrip("-")
            while name in used[d]:
                name += "-x"
            used[d].add(name)
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, name + ".md")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            index.append({"path": os.path.relpath(path, a.out), "gesetzesnummer": gesnr,
                          "title": title, "abbreviation": abbr, "land": land, "category": cat})
        with open(os.path.join(a.raw, f"index-{scope}.json"), "w") as f:
            json.dump(index, f, ensure_ascii=False, indent=0)
        print(f"{scope}: wrote {len(index)} files")
    if unknown_tags:
        print("unknown tags:", unknown_tags.most_common(30), file=sys.stderr)


if __name__ == "__main__":
    main()
