#!/usr/bin/env python3
"""Search free photo libraries for one social post and build a numbered contact sheet.

Usage:
  python3 tools/find_photos.py --query "cnc machining" --query "metal lathe" --out /tmp/ph

Keys are read from the environment and never written anywhere:
  UNSPLASH_KEY, PIXABAY_KEY, DVIDS_KEY   (a source without its key is skipped)

Writes:
  OUT/candidates.json   every candidate with source, credit, license and links
  OUT/sheet.jpg         numbered previews to look at before choosing
  OUT/previews/N.jpg    one preview per candidate
"""
import argparse
import concurrent.futures as cf
import html
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFont, ImageOps

UA = "NOS-Social-Photo-Finder/1.0 (markn@nosmanufacturing.com)"
TIMEOUT = 25
SITE = "https://nosmanufacturing.com"
SITE_PAGES = ["/", "/how-we-work.html", "/work.html", "/about.html"]
DOW_LINE = ("The appearance of U.S. Department of War visual information does not imply "
            "or constitute DoW endorsement.")
OK_CC = re.compile(r"^(cc0|pdm|public domain|pd\b|pd-|cc[- ]by(-sa)?[- ]?\d|cc[- ]by(-sa)?$|by(-sa)?$)", re.I)
BAD_CC = re.compile(r"\b(nc|nd)\b|noncommercial|noderiv", re.I)


def get(url, headers=None, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = r.read()
    return data if raw else json.loads(data.decode("utf-8"))


def clean(s, n=160):
    s = html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))
    return re.sub(r"\s+", " ", s).strip()[:n]


def words(q):
    return [w for w in re.findall(r"[a-z0-9]+", q.lower()) if len(w) > 2]


# ---------- sources ----------

def src_website(q, n):
    out, seen = [], set()
    ws = words(q)
    for page in SITE_PAGES:
        try:
            body = get(SITE + page, raw=True).decode("utf-8", "ignore")
        except Exception:
            continue
        for tag in re.findall(r"<img[^>]+>", body):
            m = re.search(r'src="([^"]+)"', tag)
            if not m or "logo" in m.group(1) or not re.search(r"\.(jpe?g|png|webp)", m.group(1), re.I):
                continue
            url = urllib.parse.urljoin(SITE + page, m.group(1))
            if url in seen:
                continue
            seen.add(url)
            alt = clean((re.search(r'alt="([^"]*)"', tag) or [None, ""])[1])
            score = sum(w in alt.lower() for w in ws)
            out.append(dict(source="website", title=alt or "NOS photo", page_url=SITE + page,
                            preview_url=url, full_url=url, credit="", license="NOS Manufacturing (own photo)",
                            disclaimer=False, hotlink=False, score=score))
    out.sort(key=lambda c: -c["score"])
    return out[:n]


def src_dvids(q, n):
    key = os.environ.get("DVIDS_KEY")
    if not key:
        return []
    url = "https://api.dvidshub.net/search?" + urllib.parse.urlencode(
        dict(type="image", q=q, api_key=key, max_results=n, thumb_width=1600, thumb_quality=90))
    d = get(url)
    out = []
    for r in d.get("results", []):
        credit = r.get("credit")
        if isinstance(credit, list):
            credit = ", ".join(clean(c.get("name") if isinstance(c, dict) else c, 80) for c in credit)
        elif isinstance(credit, dict):
            credit = clean(credit.get("name"), 80)
        credit = clean(credit, 80)
        branch = clean(r.get("branch"), 40)
        who = f"U.S. {branch}" if branch and branch.lower() not in ("joint", "civilian", "other") else clean(r.get("unit_name"), 80)
        thumb = r.get("thumbnail")
        if isinstance(thumb, dict):
            thumb = thumb.get("url")
        if not thumb:
            continue
        out.append(dict(source="dvids", title=clean(r.get("title")), page_url=r.get("url"),
                        preview_url=thumb, full_url=thumb,
                        credit=f"{who} photo by {credit}" if credit else f"{who} photo",
                        license="Public domain (U.S. government, DVIDS)", disclaimer=True, hotlink=False,
                        width=r.get("width"), height=r.get("height"), unit=clean(r.get("unit_name"), 80)))
    return out


def src_nasa(q, n):
    d = get("https://images-api.nasa.gov/search?" + urllib.parse.urlencode(dict(q=q, media_type="image", page_size=n * 2)))
    out = []
    for it in d.get("collection", {}).get("items", []):
        data = (it.get("data") or [{}])[0]
        desc = (data.get("description") or "") + " " + (data.get("secondary_creator") or "")
        if re.search(r"©|copyright|courtesy of|used with permission", desc, re.I):
            continue  # not clearly NASA public domain
        links = it.get("links") or []
        thumb = next((l.get("href") for l in links if l.get("rel") == "preview"), None)
        if not thumb:
            continue
        thumb = thumb.replace("http://", "https://").replace(" ", "%20")
        nid = data.get("nasa_id")
        full = thumb.replace("~thumb.", "~large.")
        who = clean(data.get("photographer") or data.get("secondary_creator"), 60)
        out.append(dict(source="nasa", title=clean(data.get("title")), page_url=f"https://images.nasa.gov/details/{urllib.parse.quote(str(nid))}",
                        preview_url=thumb.replace("~thumb.", "~medium."), full_url=full,
                        alt_previews=[thumb], alt_full=[thumb.replace("~thumb.", "~orig."), thumb.replace("~thumb.", "~medium.")],
                        credit=(who if "nasa" in who.lower() else f"NASA/{who}") if who else "NASA", license="Public domain (NASA)",
                        disclaimer=False, hotlink=False))
        if len(out) >= n:
            break
    return out


def src_unsplash(q, n):
    key = os.environ.get("UNSPLASH_KEY")
    if not key:
        return []
    d = get("https://api.unsplash.com/search/photos?" + urllib.parse.urlencode(dict(query=q, per_page=n, content_filter="high")),
            headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1"})
    out = []
    for r in d.get("results", []):
        raw = r["urls"]["raw"]
        sep = "&" if "?" in raw else "?"
        out.append(dict(source="unsplash", title=clean(r.get("alt_description") or r.get("description")),
                        page_url=r["links"]["html"], preview_url=r["urls"]["small"],
                        full_url=f"{raw}{sep}w=1600&q=85&fm=jpg&fit=max",
                        credit=f"Photo by {clean(r['user']['name'], 60)} on Unsplash", license="Unsplash License",
                        disclaimer=False, hotlink=True, unsplash_dl=r["links"]["download_location"],
                        width=r.get("width"), height=r.get("height")))
    return out


def src_pixabay(q, n):
    key = os.environ.get("PIXABAY_KEY")
    if not key:
        return []
    d = get("https://pixabay.com/api/?" + urllib.parse.urlencode(dict(key=key, q=q[:100], image_type="photo", per_page=max(3, n), safesearch="true")))
    out = []
    for h in d.get("hits", [])[:n]:
        out.append(dict(source="pixabay", title=clean(h.get("tags")), page_url=h.get("pageURL"),
                        preview_url=h.get("webformatURL"), full_url=h.get("largeImageURL"),
                        credit=f"Image by {clean(h.get('user'), 60)} from Pixabay", license="Pixabay Content License",
                        disclaimer=False, hotlink=False, width=h.get("imageWidth"), height=h.get("imageHeight")))
    return out


def src_openverse(q, n):
    d = get("https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(
        dict(q=q, license="cc0,pdm,by,by-sa", page_size=n, mature="false")))
    out = []
    for r in d.get("results", []):
        lic = (r.get("license") or "").lower()
        name = "Public domain" if lic in ("cc0", "pdm") else f"CC {lic.upper()} {r.get('license_version') or ''}".strip()
        who = clean(r.get("creator"), 60)
        src = clean(r.get("source"), 30).replace("_", " ").title()
        out.append(dict(source="openverse", title=clean(r.get("title")), page_url=r.get("foreign_landing_url"),
                        preview_url=f"https://api.openverse.org/v1/images/{r['id']}/thumb/", full_url=r.get("url"),
                        credit=(f"Photo by {who}, {name}, via {src}" if who else f"Photo: {name}, via {src}"),
                        license=name, license_url=r.get("license_url"), disclaimer=False, hotlink=False,
                        width=r.get("width"), height=r.get("height")))
    return out


def src_wikimedia(q, n):
    d = get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(dict(
        action="query", generator="search", gsrsearch=f"{q} filetype:bitmap", gsrnamespace=6, gsrlimit=n * 2,
        prop="imageinfo", iiprop="url|extmetadata|size", iiurlwidth=1600, format="json")))
    out = []
    for p in (d.get("query", {}).get("pages") or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        em = ii.get("extmetadata") or {}
        lic = clean((em.get("LicenseShortName") or {}).get("value"), 40)
        if not lic or BAD_CC.search(lic) or not OK_CC.search(lic):
            continue
        who = clean((em.get("Artist") or {}).get("value"), 60)
        thumb = ii.get("thumburl") or ii.get("url")
        if not thumb:
            continue
        out.append(dict(source="wikimedia", title=clean((em.get("ObjectName") or {}).get("value") or p.get("title", "")),
                        page_url=ii.get("descriptionurl"), preview_url=thumb, full_url=thumb,
                        credit=(f"Photo by {who}, {lic}, via Wikimedia Commons" if who else f"Photo: {lic}, via Wikimedia Commons"),
                        license=lic, disclaimer=False, hotlink=False, width=ii.get("width"), height=ii.get("height")))
        if len(out) >= n:
            break
    return out


SOURCES = [("website", src_website), ("dvids", src_dvids), ("nasa", src_nasa), ("unsplash", src_unsplash),
           ("pixabay", src_pixabay), ("openverse", src_openverse), ("wikimedia", src_wikimedia)]


# ---------- previews and sheet ----------

def fetch_preview(c, path):
    data, err = None, None
    for u in [c["preview_url"], *c.get("alt_previews", [])]:
        try:
            data = get(u, raw=True)
            break
        except Exception as e:
            err = e
    if data is None:
        raise err
    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im).convert("RGB")
    c["preview_size"] = list(im.size)
    im.thumbnail((640, 640))
    im.save(path, "JPEG", quality=82)
    return c


def sheet(cands, out_dir, cols=5, tw=360, th=260):
    rows = (len(cands) + cols - 1) // cols
    S = Image.new("RGB", (cols * tw, rows * (th + 28)), (20, 23, 28))
    d = ImageDraw.Draw(S)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
    except Exception:
        font = ImageFont.load_default()
    for i, c in enumerate(cands):
        x, y = (i % cols) * tw, (i // cols) * (th + 28)
        try:
            im = Image.open(os.path.join(out_dir, "previews", f"{c['n']}.jpg"))
            im.thumbnail((tw - 8, th - 8))
            S.paste(im, (x + (tw - im.width) // 2, y + 4 + (th - 8 - im.height) // 2))
        except Exception:
            pass
        d.text((x + 6, y + th + 2), f"{c['n']}  {c['source']}", fill=(255, 210, 120), font=font)
    S.save(os.path.join(out_dir, "sheet.jpg"), "JPEG", quality=80)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", action="append", required=True, help="2 to 4 visual words; repeat for more searches")
    ap.add_argument("--out", required=True)
    ap.add_argument("--per", type=int, default=4, help="results per source per query")
    ap.add_argument("--max", type=int, default=30)
    ap.add_argument("--only", default="", help="comma list of sources to use")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "previews"), exist_ok=True)
    only = set(filter(None, a.only.split(",")))
    found, errors, seen = [], {}, set()
    for q in a.query:
        for name, fn in SOURCES:
            if only and name not in only:
                continue
            if name == "website" and q != a.query[0]:
                continue
            try:
                for c in fn(q, a.per):
                    k = c.get("full_url") or c.get("preview_url")
                    if k and k not in seen:
                        seen.add(k)
                        c["query"] = q
                        found.append(c)
            except Exception as e:
                errors[f"{name}:{q}"] = str(e)[:160]
    order = {n: i for i, (n, _) in enumerate(SOURCES)}
    found.sort(key=lambda c: (order[c["source"]], -c.get("score", 0)))
    found = found[: a.max]
    for i, c in enumerate(found, 1):
        c["n"] = i
    ok = []
    with cf.ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(fetch_preview, c, os.path.join(a.out, "previews", f"{c['n']}.jpg")): c for c in found}
        for f in cf.as_completed(futs):
            c = futs[f]
            try:
                ok.append(f.result())
            except Exception as e:
                errors[f"preview:{c['n']}"] = str(e)[:160]
    ok.sort(key=lambda c: c["n"])
    sheet(ok, a.out)
    json.dump({"candidates": ok, "errors": errors, "dow_line": DOW_LINE}, open(os.path.join(a.out, "candidates.json"), "w"), indent=1)
    by = {}
    for c in ok:
        by[c["source"]] = by.get(c["source"], 0) + 1
    print(json.dumps({"count": len(ok), "by_source": by, "errors": errors, "sheet": os.path.join(a.out, "sheet.jpg")}))


if __name__ == "__main__":
    main()
