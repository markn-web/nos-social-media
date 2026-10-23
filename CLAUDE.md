# Photo finding for NOS social posts

This repository hosts post photos publicly. It is a PUBLIC repo: never commit API keys, board links,
notes, or anything other than photos and these tools.

## Find
Run with the keys from your instructions as environment variables (never echo or save them):

    UNSPLASH_KEY=... PIXABAY_KEY=... DVIDS_KEY=... python3 tools/find_photos.py \
      --query "<2 to 4 concrete visual words>" --query "<a second angle>" --out /tmp/ph

Queries describe what should be IN the photo (a part, a machine, a process, a setting), not the
post's message: "cnc lathe cutting steel", "industrial pipeline valve", "metal 3d printer build plate".
Then Read /tmp/ph/sheet.jpg and look at every numbered candidate.

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
      --post <post id> --date <post date> --out /tmp/ph/ready --push

It prints one record per option with the public `url`, a local `preview` (upload it to the board),
the `credit`, `license`, `disclaimer` (true for DVIDS) and `unsplash_dl`.
Use `--file <path> --credit "<credit>" [--disclaimer]` instead to host a photo Mark uploaded.

## Credit
The publishing run adds a credit line under each post: "Photo: <credit>" and, when `disclaimer`
is true, the DVIDS line: "The appearance of U.S. Department of War visual information does not
imply or constitute DoW endorsement." NOS's own photos get no credit line.
When an Unsplash photo is actually published, call its `unsplash_dl` link once with the Unsplash
key (Authorization: Client-ID <key>), as Unsplash's terms require.
