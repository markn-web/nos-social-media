#!/usr/bin/env python3
"""Get a public technical PDF ready for a LinkedIn document post (a swipeable PDF in the feed).

  python3 tools/prepare_pdf.py --src <https link to the PDF, or a local path> --pages "1-3,6,9-11" \
      --title "Title shown on LinkedIn" --credit "NASA Technical Reports Server: <report title>" \
      --license "Public domain (U.S. government work)" --source-url <the document's landing page> \
      --post <post id> --date YYYY-MM-DD --thumb-url <public image link, used in direct mode> \
      --out /tmp/pdf --push

Prints one JSON record: mode, url, thumb_url, title, pages, credit, license, source_url, preview.
- mode "hosted": the PDF was downloaded, cut to --pages (6 to 10 pages reads best on LinkedIn), saved
  under docs/ in this repo with a page-one cover image, pushed, and checked live. preview is a local
  600 px JPEG of page one to upload to the board.
- mode "direct": this session can't download from the PDF's host, so the record points at the original
  PDF and LinkedIn shows the whole document with --thumb-url as its cover. Only use direct mode for a
  document of 60 pages or fewer (check the page count on its landing page).
Only public-domain U.S. government works or CC BY / CC BY-SA documents. Never paywalled papers,
journal reprints or company brochures.
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

from PIL import Image
from pypdf import PdfReader, PdfWriter

UA = "NOS-Social-Photo-Finder/1.0 (markn@nosmanufacturing.com)"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = "https://raw.githubusercontent.com/markn-web/nos-social-media/main/"
MAX_BYTES = 100 * 1024 * 1024  # LinkedIn and Buffer limit


def die(msg):
    print(json.dumps({"error": msg}))
    sys.exit(1)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("PDF is over 100 MB")
    return data


def parse_pages(spec, total):
    if not spec:
        return list(range(min(total, 10)))
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            die(f"bad --pages part: {part}")
        a = int(m.group(1))
        b = int(m.group(2) or a)
        for n in range(a, b + 1):
            if 1 <= n <= total and (n - 1) not in out:
                out.append(n - 1)
    if not out:
        die(f"--pages selects nothing (the PDF has {total} pages)")
    return out


def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True)


def push(msg):
    git("add", "docs")
    if not git("status", "--porcelain", "docs").stdout.strip():
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


def cover(pdf_path, out_jpg, width):
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, "p")
        r = subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-png", "-r", "150", pdf_path, base],
                           capture_output=True, text=True)
        pngs = [f for f in os.listdir(td) if f.endswith(".png")]
        if r.returncode != 0 or not pngs:
            die("couldn't render page one: " + (r.stderr or "no image")[:200])
        im = Image.open(os.path.join(td, pngs[0])).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(out_jpg, "JPEG", quality=85, optimize=True, progressive=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="https link to the PDF file, or a local path")
    ap.add_argument("--pages", default="", help='pages to keep, like "1-3,6,9-11" (default: first 10)')
    ap.add_argument("--title", required=True, help="document title LinkedIn shows")
    ap.add_argument("--credit", required=True, help="publisher and document name for the credit line")
    ap.add_argument("--license", required=True)
    ap.add_argument("--source-url", required=True, help="the document's landing page")
    ap.add_argument("--post", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--thumb-url", default="", help="public image link used as the cover in direct mode")
    ap.add_argument("--out", default="/tmp/pdf")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        die("--date must be YYYY-MM-DD")
    if re.search(r"\b(NC|ND)\b|non-?commercial|no-?deriv", a.license, re.I):
        die("NC and ND licenses are not allowed")
    os.makedirs(a.out, exist_ok=True)
    rec = {"title": a.title, "credit": a.credit, "license": a.license, "source_url": a.source_url}

    data = None
    if re.match(r"https?://", a.src):
        try:
            data = fetch(a.src)
        except Exception as e:  # host blocked from this session, or a network error
            if not a.thumb_url:
                die(f"couldn't download the PDF ({e.__class__.__name__}) and no --thumb-url was given for direct mode")
            rec.update(mode="direct", url=a.src, thumb_url=a.thumb_url, pages=None, preview="",
                       note="Not downloadable from this session; LinkedIn will show the whole document. "
                            "Use only if its landing page shows 60 pages or fewer.")
            print(json.dumps(rec))
            return
    else:
        with open(a.src, "rb") as f:
            data = f.read()
    if not data.startswith(b"%PDF"):
        die("the link didn't return a PDF file (it may be a landing page; use the direct PDF link)")

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            die("the PDF is encrypted")
    keep = parse_pages(a.pages, len(reader.pages))
    writer = PdfWriter()
    for i in keep:
        writer.add_page(reader.pages[i])
    writer.add_metadata({"/Title": a.title, "/Subject": f"Source: {a.credit}. {a.license}. {a.source_url}"})

    stem = re.sub(r"[^a-z0-9-]+", "-", f"{a.date}-{a.post}".lower()).strip("-")
    rel_pdf = f"docs/{a.date[:7]}/{stem}.pdf"
    rel_jpg = f"docs/{a.date[:7]}/{stem}-cover.jpg"
    dst_pdf = os.path.join(REPO, rel_pdf)
    os.makedirs(os.path.dirname(dst_pdf), exist_ok=True)
    with open(dst_pdf, "wb") as f:
        writer.write(f)
    if os.path.getsize(dst_pdf) > MAX_BYTES:
        die("the trimmed PDF is still over 100 MB")
    cover(dst_pdf, os.path.join(REPO, rel_jpg), 1200)
    preview = os.path.join(a.out, f"{stem}-cover-preview.jpg")
    cover(dst_pdf, preview, 600)

    rec.update(mode="hosted", url=RAW + rel_pdf, thumb_url=RAW + rel_jpg, pages=len(keep),
               source_pages=len(reader.pages), preview=preview)
    if a.push:
        if not push(f"PDF for {a.date} post {a.post}"):
            die("git push failed")
        if not (live(rec["url"]) and live(rec["thumb_url"])):
            die("pushed, but the public links aren't live yet; run again in a minute")
    else:
        rec["note"] = "Not pushed (no --push): the links won't work until it is."
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
