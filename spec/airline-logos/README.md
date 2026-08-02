# spec/airline-logos/

Drop real airline logo files here to have them show up on the browser
edition's itinerary/invoice document (`EM`/`EMI`/`EMT`) instead of the
generated colored-badge placeholder.

**These image files are gitignored on purpose** (see root `.gitignore`) —
they're real trademarked/copyrighted assets, and this repo doesn't want to
distribute them just because one person's checkout has them locally. Only
this README is tracked; everything else you put in this folder stays local
to your machine.

## Naming

One file per carrier, named by lowercase IATA code:

```
aa.svg
dl.svg
ua.png
```

Only codes present in `../airlines.json` are picked up. SVG is preferred
(scales cleanly, small) but PNG/JPG work too. If a carrier has both, the
build picks in this order: `svg` > `png` > `jpg`/`jpeg`.

## Applying changes

After adding/removing files here, regenerate the browser's copy:

```bash
python3 spec/build.py
```

This writes `web/generated/airline-logos.js` (also gitignored — it embeds
the logos as base64 data URIs) as `const AIRLINE_LOGOS = {"AA": "data:...", ...}`.
Any carrier without a logo file here simply won't have a key in that object,
and the browser falls back to the generated placeholder badge for it - see
`airlineBadgeSVG` in `web/script.js`.
