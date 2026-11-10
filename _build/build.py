#!/usr/bin/env python3
"""Generate one folder per page (e.g. trade/cleaning/index.html) from the app.

Run from the repo root after editing assets/app.js, assets/style.css or _build/shell.html:

    pip install playwright && playwright install chromium   (first time only)
    python3 _build/build.py

Each page is rendered in a headless browser and written as static HTML, so every
URL works on direct visit and search engines see real content. The app still
takes over in the browser, so nothing visible changes for visitors.
"""
import html, json, os, re, shutil, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SHELL = open(os.path.join(ROOT, "_build", "shell.html"), encoding="utf-8").read()
DOMAIN = open(os.path.join(ROOT, "CNAME")).read().strip()
BASE = "https://" + DOMAIN
TYPES = {".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/assets/"):
            fp = os.path.join(ROOT, path.lstrip("/"))
            if os.path.isfile(fp):
                body = open(fp, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", TYPES.get(os.path.splitext(fp)[1], "application/octet-stream"))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()
            return
        body = SHELL.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)


def sub1(pattern, repl, text, flags=re.S):
    new, n = re.subn(pattern, lambda m: repl, text, count=1, flags=flags)
    assert n == 1, pattern
    return new


def compose(d, path, noindex=False):
    t = SHELL
    t = sub1(r"<title>.*?</title>", "<title>%s</title>" % html.escape(d["title"], quote=False), t)
    t = sub1(r'<meta name="description" content="[^"]*">', '<meta name="description" content="%s">' % html.escape(d["desc"]), t)
    t = sub1(r'<meta property="og:title" content="[^"]*">', '<meta property="og:title" content="%s">' % html.escape(d["title"]), t)
    t = sub1(r'<meta property="og:description" content="[^"]*">', '<meta property="og:description" content="%s">' % html.escape(d["desc"]), t)
    extra = ""
    if not noindex:
        url = BASE + path
        extra += '<link rel="canonical" href="%s"><meta property="og:url" content="%s">' % (url, url)
    else:
        extra += '<meta name="robots" content="noindex">'
    if d["ld"]:
        extra += '<script type="application/ld+json" id="ld">%s</script>' % d["ld"].replace("</", "<\\/")
    t = t.replace("</head>", extra + "</head>", 1)
    t = t.replace("<body>", '<body data-mode="%s">' % d["mode"], 1)
    t = sub1(r"<header>.*?</header>", d["header"], t)
    t = sub1(r'<div class="bar">.*?</div>', d["bar"], t)
    t = sub1(r'<main id="app" tabindex="-1"></main>', '<main id="app" tabindex="-1" data-pre="1">%s</main>' % d["app"], t)
    return t


def write(path, text):
    fp = os.path.join(ROOT, path.strip("/"), "index.html") if path != "/" else os.path.join(ROOT, "index.html")
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    open(fp, "w", encoding="utf-8").write(text)


def main():
    from playwright.sync_api import sync_playwright

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    origin = "http://127.0.0.1:%d" % port

    extract = """() => ({
      title: document.title,
      desc: document.querySelector('meta[name=description]').content,
      ld: (document.getElementById('ld') || {}).textContent || '',
      mode: document.body.dataset.mode || '',
      header: document.querySelector('header').outerHTML,
      bar: document.querySelector('.bar').outerHTML,
      app: document.getElementById('app').innerHTML
    })"""

    with sync_playwright() as p:
        exe = os.environ.get("CHROME") or ("/usr/bin/google-chrome" if os.path.exists("/usr/bin/google-chrome") else None)
        b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"]) if exe else p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1200, "height": 900}, reduced_motion="reduce")
        ctx.route(re.compile(r"^(?!http://127\.0\.0\.1).*"), lambda r: r.abort())
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        pg.goto(origin + "/")
        pg.wait_for_function("document.getElementById('app').children.length > 0")
        keys = pg.evaluate("({P:Object.keys(P),LG:Object.keys(LG),B:Object.keys(B),TR:Object.keys(TR)})")
        paths = ["/"]
        for k in keys["P"] + keys["LG"]:
            if k and "/%s/" % k not in paths:
                paths.append("/%s/" % k)
        paths += ["/trade/%s/" % k for k in keys["TR"]]
        paths += ["/service/%s/" % k for k in keys["TR"]]
        paths += ["/blog/%s/" % k for k in keys["B"]]

        # clear previously generated page folders so deleted pages do not linger
        for d in os.listdir(ROOT):
            fp = os.path.join(ROOT, d)
            if os.path.isdir(fp) and not d.startswith((".", "_")) and d != "assets" and any(
                    "index.html" in files for _, _, files in os.walk(fp)):
                shutil.rmtree(fp)

        for path in paths:
            pg.goto(origin + path)
            pg.wait_for_function("document.getElementById('app').children.length > 0")
            pg.wait_for_timeout(120)
            write(path, compose(pg.evaluate(extract), path))

        pg.goto(origin + "/page-not-found-404/")
        pg.wait_for_function("document.getElementById('app').children.length > 0")
        d = pg.evaluate(extract)
        open(os.path.join(ROOT, "404.html"), "w", encoding="utf-8").write(compose(d, "/404.html", noindex=True))

        b.close()
        if errors:
            print("PAGE ERRORS:", errors)
            sys.exit(1)

    urls = "".join("<url><loc>%s%s</loc></url>\n" % (BASE, x) for x in paths)
    open(os.path.join(ROOT, "sitemap.xml"), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n")
    open(os.path.join(ROOT, "robots.txt"), "w").write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % BASE)
    print("built %d pages + 404.html, sitemap.xml, robots.txt" % len(paths))


if __name__ == "__main__":
    main()
