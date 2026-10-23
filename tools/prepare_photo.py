#!/usr/bin/env python3
"""Turn chosen candidates (or a local photo) into post-ready public photos.

Pick from a find_photos.py run:
  python3 tools/prepare_photo.py --cands /tmp/ph/candidates.json --pick 9,14,2 \
      --post <post id> --date YYYY-MM-DD --out /tmp/ph/ready --push

Host one local file (for example a photo Mark uploaded to the board):
  python3 tools/prepare_photo.py --file /path/photo.jpg --post <post id> --date YYYY-MM-DD \
      --credit "U.S. Army Corps of Engineers photo by Andrew Byrne" --disclaimer --out /tmp/ph/ready --push

For every photo it prints one JSON record with: option, source, title, page_url, url (public link to post),
preview (local 600 px JPEG to upload to the board), credit, license, disclaimer, unsplash_dl.
Unsplash photos stay on Unsplash (their terms require it); everything else is saved as a JPEG under photos/
in this repo, pushed, and checked live at raw.githubusercontent.com.
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time
import urllib.request

from PIL import Image, ImageOps

UA = "NOS-Social-Photo-Finder/1.0 (markn@nosmanufacturing.com)"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = "https://raw.githubusercontent.com/markn-web/nos-social-media/main/"
BG = (20, 23, 28)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def load(data):
    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    return im.convert("RGB")


def fit(im):
    """Fit within 1600 px and keep the aspect ratio inside Instagram's 4:5 to 1.91:1 range."""
    im.thumbnail((1600, 1600), Image.LANCZOS)
    w, h = im.size
    r = w / h
    if r < 0.8:  # too tall: widen to 4:5
        W = int(round(h * 0.8))
        c = Image.new("RGB", (W, h), BG)
        c.paste(im, ((W - w) // 2, 0))
        im = c
    elif r > 1.91:  # too wide: heighten to 1.91:1
        H = int(round(w / 1.91))
        c = Image.new("RGB", (w, H), BG)
        c.paste(im, (0, (H - h) // 2))
        im = c
    return im


def preview(im, path):
    p = im.copy()
    p.thumbnail((640, 640))
    p.save(path, "JPEG", quality=80)


def host(im, rel):
    dst = os.path.join(REPO, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im.save(dst, "JPEG", quality=85, optimize=True, progressive=True)
    return RAW + rel


def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True)


def push(msg):
    git("add", "photos")
    if not git("status", "--porcelain", "photos").stdout.strip():
        return True
    git("-c", "user.name=NOS Social", "-c", "user.email=markn@nosmanufacturing.com", "commit", "-m", msg)
    for _ in range(3):
        git("pull", "--rebase", "--depth", "1", "origin", "main")
        if git("push", "origin", "HEAD:main").returncode == 0:
            return True
        time.sleep(5)
    return False


def live(url, tries=12):
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(5)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cands")
    ap.add_argument("--pick", default="", help="candidate numbers in the order you rank them")
    ap.add_argument("--file")
    ap.add_argument("--credit", default="")
    ap.add_argument("--disclaimer", action="store_true")
    ap.add_argument("--post", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    month = a.date[:7]
    recs, hosted = [], []
    if a.file:
        im = fit(load(open(a.file, "rb").read()))
        rel = f"photos/{month}/{a.date}-{a.post}-own.jpg"
        url = host(im, rel)
        pv = os.path.join(a.out, f"{a.post}-own.jpg")
        preview(im, pv)
        hosted.append(url)
        recs.append(dict(option=0, source="mark", title="Mark's photo", page_url="", url=url, preview=pv,
                         credit=a.credit, license="", disclaimer=bool(a.disclaimer), unsplash_dl=""))
    if a.cands:
        cands = {c["n"]: c for c in json.load(open(a.cands))["candidates"]}
        for i, n in enumerate([int(x) for x in a.pick.split(",") if x.strip()], 1):
            c = cands[n]
            rec = dict(option=i, source=c["source"], title=c.get("title", ""), page_url=c.get("page_url", ""),
                       credit=c.get("credit", ""), license=c.get("license", ""), disclaimer=bool(c.get("disclaimer")),
                       unsplash_dl=c.get("unsplash_dl", ""))
            pv = os.path.join(a.out, f"{a.post}-{i}.jpg")
            data, err = None, None
            for u in [c["full_url"], *c.get("alt_full", []), c.get("preview_url")]:
                try:
                    data = fetch(u)
                    if u != c["full_url"] and c.get("hotlink"):
                        data = None  # Unsplash must use its own link
                        continue
                    break
                except Exception as e:
                    err = e
            if data is None:
                print(json.dumps({"option": i, "n": n, "error": f"download failed: {err}"}), file=sys.stderr)
                continue
            im = load(data)
            if c.get("hotlink"):
                rec["url"] = c["full_url"]
                preview(im, pv)
            else:
                im = fit(im)
                rel = f"photos/{month}/{a.date}-{a.post}-{i}.jpg"
                rec["url"] = host(im, rel)
                preview(im, pv)
                hosted.append(rec["url"])
            rec["preview"] = pv
            recs.append(rec)
    if hosted and a.push:
        if not push(f"Photos for {a.date} post {a.post}"):
            print(json.dumps({"error": "git push failed"}), file=sys.stderr)
        for r in recs:
            if r["url"] in hosted:
                r["live"] = live(r["url"])
    print(json.dumps(recs, indent=1))


if __name__ == "__main__":
    main()
