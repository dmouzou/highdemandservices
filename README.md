# highdemandservices

Static site for highdemandservices.com (GitHub Pages).

## Structure

- `assets/app.js` holds all page content and logic (trades, prices, copy, testimonials, router).
- `assets/style.css` holds the styles.
- `_build/shell.html` is the page template (header, footer, modals).
- Every page lives in its own folder (`trades/`, `trade/cleaning/`, `blog/<slug>/` ...) and is generated, so edit the files above, not the folders.

## After any edit to `assets/` or `_build/shell.html`

```
pip install playwright && playwright install chromium   # first time only
python3 _build/build.py
```

This regenerates all page folders, `404.html`, `sitemap.xml` and `robots.txt`, then commit and push.

## Adding a trade

Add a key to each trade map in `assets/app.js` (`IC`, `TR`, `TX`, `PR`, `PC`, `TW`, `PROP`, `PHOTOS`, `SKT`, `TRM`), then rebuild. Testimonials go in `TT0`; the proof section appears on a trade page only when that trade has entries there.
