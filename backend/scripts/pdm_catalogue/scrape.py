"""
Downloads the SOLIDWORKS PDM Professional Web API help pages and stores each
one as plain text, one `.txt` file per page, for parse_pages.py to read.

The help site is a Next.js application. Every page embeds its content as HTML
inside the `__NEXT_DATA__` JSON blob (props.pageProps.helpContentData.helpText),
so the scraper reads that blob instead of the rendered page and reduces the
HTML to text where table cells are separated by ` | `. parse_pages.py relies
on that layout.

The page list comes either from a file (one page name per line, for example
`PDM Pro API_ws~r-api-{vaultName}-authenticate_o-HttpPost.html`) or, when no
file is given, from the links found on the help index page. The index page
itself is always saved too. Pages already present in the output directory are
skipped, so an interrupted run can simply be restarted.

The index-derived page list was reconstructed from how the original scrape
named its output files, not tested against the live site. If the index page
name or its link format has changed, pass `--index` or a `--pages` file.

Stdlib only. Usage (the output directory is scratch space, never commit it):
    python scripts/pdm_catalogue/scrape.py --out /tmp/pdmdocs
    python scripts/pdm_catalogue/scrape.py --out /tmp/pdmdocs --pages pages.txt
    python scripts/pdm_catalogue/scrape.py --out /tmp/pdmdocs --base-url \\
        https://help.solidworks.com/2026/english/api/pdmprowebapihelp/
"""

import argparse
import concurrent.futures
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://help.solidworks.com/2025/english/api/pdmprowebapihelp/"
DEFAULT_INDEX_PAGE = "index.html"
# Operation pages share this prefix; it is dropped from the output file names.
OPERATION_PAGE_PREFIX = "PDM Pro API_ws~r-"
# Overview pages the original scrape fetched in addition to the operations.
EXTRA_PAGES = ("GettingStarted.html", "Welcome.html", "WebEventHooks.html", "Hooks.html")
WORKERS = 6
TIMEOUT_SECONDS = 60

_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_HREF = re.compile(r'href="([^"]+)"')


def html_to_text(markup: str) -> str:
    """Reduce help-page HTML to text, keeping row breaks and ` | ` cell separators."""
    text = re.sub(r"<script.*?</script>", "", markup, flags=re.S)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
    text = re.sub(r"</(p|div|tr|li|h\d|pre|table)>", "\n", text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</t[dh]>", " | ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def output_name(page: str) -> str:
    """Map a page name to its `.txt` file name, matching the original scrape."""
    stem = page.replace(OPERATION_PAGE_PREFIX, "").replace(".html", "")
    return re.sub(r"[^A-Za-z0-9_.=-]+", "_", stem) + ".txt"


def fetch_help_html(base_url: str, page: str) -> str:
    """Fetch one page and return the help HTML embedded in its Next.js data blob."""
    url = base_url + urllib.parse.quote(page)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        raw = response.read().decode("utf-8", "replace")
    match = _NEXT_DATA.search(raw)
    if not match:
        raise ValueError("page has no __NEXT_DATA__ blob")
    data: dict[str, Any] = json.loads(match.group(1))
    help_text: str = data["props"]["pageProps"]["helpContentData"]["helpText"]
    return help_text


def links_on_page(markup: str) -> list[str]:
    """Return the distinct `.html` page names linked from help HTML, in order."""
    pages: list[str] = []
    for href in _HREF.findall(html.unescape(markup)):
        path = urllib.parse.urlsplit(href).path
        name = urllib.parse.unquote(path.rsplit("/", 1)[-1])
        if name.endswith(".html") and name not in pages:
            pages.append(name)
    return pages


def save_page(base_url: str, page: str, out_dir: Path) -> str:
    """Download one page unless it is cached; return a short status for the log."""
    target = out_dir / output_name(page)
    if target.exists():
        return "cached"
    try:
        help_html = fetch_help_html(base_url, page)
    except Exception as exc:  # one failed page must not stop the run
        return f"ERR {exc}"
    target.write_text(html_to_text(help_html), encoding="utf-8")
    return f"ok {len(help_html)}"


def read_page_list(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip().replace("%20", " ") for line in lines if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape the PDM Web API help pages to text.")
    parser.add_argument("--out", type=Path, required=True, help="directory for the .txt pages")
    parser.add_argument("--pages", type=Path, help="file with one page name per line")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="help site base URL")
    parser.add_argument("--index", default=DEFAULT_INDEX_PAGE, help="help index page name")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    try:
        index_html = fetch_help_html(args.base_url, args.index)
    except Exception as exc:  # reported, then the run stops
        print(f"could not fetch index page {args.index}: {exc}", file=sys.stderr)
        return 1
    (args.out / output_name(args.index)).write_text(html_to_text(index_html), encoding="utf-8")

    pages = read_page_list(args.pages) if args.pages else links_on_page(index_html)
    pages += [page for page in EXTRA_PAGES if page not in pages]
    print(f"{len(pages)} pages to fetch into {args.out}")

    with concurrent.futures.ThreadPoolExecutor(WORKERS) as pool:
        statuses = pool.map(lambda page: (page, save_page(args.base_url, page, args.out)), pages)
        for page, status in statuses:
            print(f"{status} | {page}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
