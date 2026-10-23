# nos-social-media

Public photo hosting for NOS Manufacturing's social posts. Files under `photos/` are posted to LinkedIn,
Facebook and Instagram through Buffer and Metricool, which need a public link to each image.

- `tools/find_photos.py` searches free libraries (NOS website, DVIDS, NASA, Unsplash, Pixabay,
  Openverse, Wikimedia Commons) and builds a numbered contact sheet.
- `tools/prepare_photo.py` turns the chosen photos into post-ready JPEGs, pushes them here and
  returns their public links and credit lines.

Every photo here is either NOS's own, in the public domain, or used under its library's license.
Credits travel with each post.
