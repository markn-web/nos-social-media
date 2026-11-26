# Photo finding for NOS social posts

This repository hosts post photos and PDF documents publicly. It is a PUBLIC repo: never commit API
keys, board links, notes, or anything other than photos, public PDFs (see "PDF documents") and these tools.

## Fresh photos (Mark's rule, Nov 25, 2026)
Mark doesn't want the same photos coming back. Every post gets photos from a fresh search:
- A library photo (Unsplash, Pixabay, DVIDS, NASA, Openverse, Wikimedia) that went out on a post is
  never used again, and any photo offered on a post within 30 days isn't offered again.
- An NOS photo that went out within 30 days isn't used again; one that was only offered comes back
  after 14 days (there are far fewer of them).
- A day's posts never share a photo.
- Never copy a photo url, hosted file or thumb from another post. Every option comes from a
  find_photos.py run and prepare_photo.py.
- If the search fails or nothing usable turns up after a second search with different words, don't fall
  back to older photos: leave photo_options empty, and say in the board note that the photo search
  failed and the exact error, so it gets fixed.

Build the used list first. Save the board's posts (ArtifactData action "list", collection "posts",
query limit 1000, out_dir /tmp/board), then:

    python3 tools/used_photos.py --posts /tmp/board --date <post date> --out /tmp/used.json

Pass `--exclude /tmp/used.json` to every find_photos.py run and `--used /tmp/used.json` to every
prepare_photo.py run (it adds the new picks, so the next post of the day can't take them).

## Find
Run with the keys from your instructions as environment variables (never echo or save them):

    UNSPLASH_KEY=... PIXABAY_KEY=... DVIDS_KEY=... python3 tools/find_photos.py \
      --query "<2 to 4 concrete visual words>" --query "<a second angle>" \
      --exclude /tmp/used.json --out /tmp/ph

Queries describe what should be IN the photo (a part, a machine, a process, a setting), not the
post's message: "cnc lathe cutting steel", "industrial pipeline valve", "metal 3d printer build plate".
Then Read /tmp/ph/sheet.jpg and look at every numbered candidate.

## NOS photos first
`find_photos.py` always searches nosmanufacturing.com (home, How We Work, Work, Reverse Engineering
and About pages) as source "website", plus `tools/nos_photos.json`: Mark's other work photos hosted on
the site (single shots of the scan, CAD, FEA, CFD, printed and machined stages, and parts not on the
pages). The Work page carries every one of Mark's project collages, so for work, explainer and reverse
engineering posts a website photo should usually be option 1, as long as the fresh-photo rule allows it.
- Within one post, prefer NOS photos from different projects (the `group` field in nos_photos.json).
- When a new NOS work photo goes up on nosmanufacturing.com, add it to nos_photos.json: file path,
  a plain title that describes only what is in the photo (it becomes the alt text), tags and group.
- Never crop or split a multi-photo collage. `prepare_photo.py` only scales and pads (to 4:5 or
  1.91:1 with a plain background), so pass collages to it as they are and never cut one yourself.
- Mark's full-size originals live in his Google Drive folder "Project Photos" (inside "Website Assets
  - Drop Files Here"). New project photos land there before they reach the website. If your session
  has Google Drive tools, list that folder by name only (search_files with excludeContentSnippets);
  never download images through the Drive tool (it returns the whole file as base64, far too large).
  If a photo there fits a post clearly better than anything on the website, say so in one line of the
  board note you write ("New project photo in Drive fits <topic>: <file name>. Upload it on the post to
  use it."), so Mark can upload it on the board.

## Choose 3
Rank the best three for the post. Keep a photo only if all of these hold:
- It clearly shows the subject or a close, honest stand-in. Real industrial photos over renders.
  NOS website photos come first whenever one fits (they are real NOS work).
- No military insignia, unit patches, flags, ship hull numbers or uniforms as the focus, and no
  recognizable face as the main subject (DVIDS and NASA photos may not imply government endorsement).
- No visible competitor brand or machine-maker logo as the focus, no watermarks, no text overlays,
  no AI-looking images, nothing unsafe (no PPE where it is obviously needed).
- License is one of: NOS own, public domain (DVIDS, NASA, CC0, PDM), Unsplash License, Pixabay Content
  License, CC BY or CC BY-SA. Never NC or ND.
If fewer than three pass, search again with different words; if still short, keep what passes.

## Prepare
    python3 tools/prepare_photo.py --cands /tmp/ph/candidates.json --pick A,B,C \
      --post <post id> --date <post date> --used /tmp/used.json --out /tmp/ph/ready --push

It prints one record per option with the public `url`, a local `preview` (upload it to the board),
the `credit`, `license`, `disclaimer` (true for DVIDS), `unsplash_dl` and `key` (the photo's stable
id; keep it in the board's photo_options entry so the fresh-photo rule can recognize it later).
It never overwrites a hosted photo: a post that gets new photos gets new files.
Use `--file <path> --credit "<credit>" [--disclaimer]` instead to host a photo Mark uploaded.

## Credit
The publishing run adds a credit line under each post: "Photo: <credit>" and, when `disclaimer`
is true, the DVIDS line: "The appearance of U.S. Department of War visual information does not
imply or constitute DoW endorsement." NOS's own photos get no credit line.
When an Unsplash photo is actually published, call its `unsplash_dl` link once with the Unsplash
key (Authorization: Client-ID <key>), as Unsplash's terms require.

## PDF documents (weekly LinkedIn document post)
Find one technical PDF that directly supports the post's topic. Allowed: U.S. government works
(NASA Technical Reports Server with "Public Use Permitted", DTIC "Distribution Statement A: approved for
public release", NIST, DOE/OSTI, FAA, Navy and Air Force public releases) or documents under CC BY or
CC BY-SA. Confirm the status on the document's landing page. Never paywalled papers, journal reprints,
standards sold by their publisher, export-controlled or limited-distribution documents, or company
brochures and data sheets.

    python3 tools/prepare_pdf.py --src <direct https link to the .pdf> --pages "1-3,6,9-11" \
      --title "<what LinkedIn shows, under about 60 characters>" \
      --credit "<publisher>: <document title>" --license "Public domain (U.S. government work)" \
      --source-url <landing page> --post <post id> --date <post date> \
      --thumb-url <the post's selected photo url> --out /tmp/pdf --push

Pick the 6 to 10 pages that carry the useful content (summary, key figures, tables, conclusions) and
skip covers, distribution pages and long reference lists. The record's `mode` is "hosted" (cut, hosted
here with a page-one cover, `preview` to upload to the board) or "direct" (this session can't reach
the PDF's host; LinkedIn shows the whole document, so only use it when the landing page shows 60 pages
or fewer). The publishing run credits it under the post: "Document: <credit> (<license>)."

