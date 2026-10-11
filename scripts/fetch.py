#!/usr/bin/env python3
"""Fetch consolidated Austrian law (RIS OGD API v2.6) into a raw cache.

Phase 1 ("list"): page through the search API for all documents in force on a
given date (Bundesrecht konsolidiert = BrKons, Landesrecht konsolidiert = LrKons)
and store each result page as JSON.
Phase 2 ("docs"): download the XML of every listed document (one per paragraph /
article / annex, plus the "§ 0" header document of every law).

Usage:
  fetch.py list  [--raw DIR] [--date YYYY-MM-DD] [--scope bund|land|all]
  fetch.py docs  [--raw DIR] [--scope bund|land|all]

Everything is cached under --raw (default ../_raw/at); re-runs skip what exists.
Be polite: <= 4 concurrent connections, retries with exponential backoff.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import sys
import threading
import time

import requests

API = "https://data.bka.gv.at/ris/api/v2.6/"
DOC = "https://ogd.ris.bka.gv.at/Dokumente/{coll}/{id}/{id}.xml"
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
WORKERS = 4

_local = threading.local()


def session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = UA
        _local.s = s
    return s


def get(url, params=None, tries=8):
    delay = 2
    for i in range(tries):
        try:
            r = session().get(url, params=params, timeout=120)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                return None
            err = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            err = str(e)
        print(f"  retry {i+1} {url} {params or ''}: {err}", file=sys.stderr)
        time.sleep(delay)
        delay = min(delay * 2, 120)
    raise RuntimeError(f"giving up on {url} {params}")


SCOPES = {
    "bund": ("Bundesrecht", "BrKons", "Bundesnormen"),
    "land": ("Landesrecht", "LrKons", "Landesnormen"),
}


def list_scope(raw, scope, date):
    endpoint, app, _ = SCOPES[scope]
    outdir = os.path.join(raw, "list", scope)
    os.makedirs(outdir, exist_ok=True)
    params = {"Applikation": app, "Fassung.FassungVom": date,
              "DokumenteProSeite": "OneHundred", "Seitennummer": 1}
    first = os.path.join(outdir, "page-00001.json")
    if not os.path.exists(first):
        r = get(API + endpoint, params)
        with open(first, "wb") as f:
            f.write(r.content)
    hits = int(json.load(open(first))["OgdSearchResult"]["OgdDocumentResults"]["Hits"]["#text"])
    pages = (hits + 99) // 100
    print(f"{scope}: {hits} documents, {pages} pages")
    todo = [p for p in range(2, pages + 1)
            if not os.path.exists(os.path.join(outdir, f"page-{p:05d}.json"))]

    def one(p):
        r = get(API + endpoint, dict(params, Seitennummer=p))
        d = r.json()  # validate
        if "OgdDocumentResults" not in d.get("OgdSearchResult", {}):
            raise RuntimeError(f"bad page {p}: {r.text[:300]}")
        tmp = os.path.join(outdir, f".page-{p:05d}.tmp")
        with open(tmp, "wb") as f:
            f.write(r.content)
        os.replace(tmp, os.path.join(outdir, f"page-{p:05d}.json"))
        return p

    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for n, _ in enumerate(ex.map(one, todo), 1):
            if n % 50 == 0:
                print(f"  {scope} pages {n}/{len(todo)}", flush=True)
    with open(os.path.join(outdir, "meta.json"), "w") as f:
        json.dump({"hits": hits, "date": date, "pages": pages}, f)


def iter_refs(raw, scope):
    """Yield (position, ref) for all listed documents, deduplicated by ID."""
    outdir = os.path.join(raw, "list", scope)
    seen = set()
    pos = 0
    for fn in sorted(os.listdir(outdir)):
        if not fn.startswith("page-"):
            continue
        d = json.load(open(os.path.join(outdir, fn)))["OgdSearchResult"]["OgdDocumentResults"]
        refs = d.get("OgdDocumentReference", [])
        if isinstance(refs, dict):
            refs = [refs]
        for ref in refs:
            i = ref["Data"]["Metadaten"]["Technisch"]["ID"]
            if i in seen:
                continue
            seen.add(i)
            pos += 1
            yield pos, ref


def docs_scope(raw, scope):
    _, _, coll = SCOPES[scope]
    outdir = os.path.join(raw, "xml", scope)
    os.makedirs(outdir, exist_ok=True)
    have = set(os.listdir(outdir))
    ids = [ref["Data"]["Metadaten"]["Technisch"]["ID"] for _, ref in iter_refs(raw, scope)]
    todo = [i for i in ids if i + ".xml" not in have]
    print(f"{scope}: {len(ids)} documents listed, {len(todo)} to download", flush=True)
    missing = []

    def one(i):
        r = get(DOC.format(coll=coll, id=i))
        if r is None:
            missing.append(i)
            return
        tmp = os.path.join(outdir, f".{i}.tmp")
        with open(tmp, "wb") as f:
            f.write(r.content)
        os.replace(tmp, os.path.join(outdir, i + ".xml"))

    t0 = time.time()
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for n, _ in enumerate(ex.map(one, todo), 1):
            if n % 1000 == 0:
                rate = n / (time.time() - t0)
                print(f"  {scope} docs {n}/{len(todo)} ({rate:.1f}/s, eta {(len(todo)-n)/rate/3600:.1f} h)", flush=True)
    if missing:
        with open(os.path.join(raw, f"missing-{scope}.txt"), "w") as f:
            f.write("\n".join(missing) + "\n")
        print(f"{scope}: {len(missing)} documents returned 404")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["list", "docs"])
    ap.add_argument("--raw", default=os.path.join(os.path.dirname(__file__), "..", "..", "_raw", "at"))
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--scope", default="all", choices=["bund", "land", "all"])
    a = ap.parse_args()
    scopes = ["bund", "land"] if a.scope == "all" else [a.scope]
    for s in scopes:
        if a.phase == "list":
            list_scope(a.raw, s, a.date)
        else:
            docs_scope(a.raw, s)


if __name__ == "__main__":
    main()
