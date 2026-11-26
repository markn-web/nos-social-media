#!/usr/bin/env python3
"""Build the list of photos a new post must not use (Mark's fresh-photo rule, Nov 25, 2026).

Save the board's posts first (ArtifactData list, collection "posts", out_dir /tmp/board, every page),
then:
  python3 tools/used_photos.py --posts /tmp/board --date <post date> --out /tmp/used.json

Pass the result to find_photos.py --exclude and to prepare_photo.py --used (which adds each new pick,
so a day's three posts never share a photo).

The rule:
- A library photo (Unsplash, Pixabay, DVIDS, NASA, Openverse, Wikimedia) that went out on a post, or is
  on a picked post (draft, approved, scheduled, posted), is never used again.
- An NOS photo that went out, or is picked, within DAYS of the date is not used again.
- A library photo offered as an option on a post dated within DAYS of the date (before or after) is
  not offered again; an NOS photo offered (and not picked) comes back after NOS_DAYS, because there
  are far fewer of them.
"""
import argparse
import datetime as dt
import glob
import json
import os

PICKED = {"draft", "approved", "scheduled", "posted"}
NOS = {"website", "mark"}


def day(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def ids(o):
    out = []
    if o.get("key"):
        out.append(o["key"])
    if o.get("source") not in NOS and o.get("page_url"):
        out.append(o["page_url"])
    if o.get("source") == "website" and o.get("title"):
        out.append("nos-title:" + o["title"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--posts", required=True, help="folder holding the board's posts as JSON files")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="date of the post getting photos")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--nos-days", type=int, default=14)
    ap.add_argument("--skip-post", action="append", default=[], help="post id whose own photos don't count")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ref = day(a.date)
    files = sorted(glob.glob(os.path.join(a.posts, "**", "*.json"), recursive=True))
    used, why = [], {"library_published": 0, "nos_recent": 0, "offered_recent": 0}

    def add(keys, reason):
        new = [k for k in keys if k not in used]
        used.extend(new)
        if new:
            why[reason] += 1

    posts = 0
    for f in files:
        try:
            p = json.load(open(f))
        except Exception:
            continue
        if not isinstance(p, dict) or "photo_options" not in p and "image_url" not in p:
            continue
        pid = os.path.splitext(os.path.basename(f))[0]
        if pid in a.skip_post:
            continue
        posts += 1
        d = day(p.get("date"))
        gap = abs((d - ref).days) if d is not None and ref is not None else 10 ** 6
        recent = gap <= a.days
        picked = p.get("status") in PICKED
        for o in p.get("photo_options") or []:
            if not isinstance(o, dict):
                continue
            chosen = picked and o.get("option") == p.get("photo_choice")
            if chosen and o.get("source") not in NOS:
                add(ids(o), "library_published")
            elif chosen and recent:
                add(ids(o), "nos_recent")
            if gap <= (a.nos_days if o.get("source") in NOS else a.days):
                add(ids(o), "offered_recent")
    json.dump(used, open(a.out, "w"), indent=0)
    print(json.dumps({"posts_read": posts, "photos_excluded": len(used), "by_reason": why, "out": a.out}))


if __name__ == "__main__":
    main()
