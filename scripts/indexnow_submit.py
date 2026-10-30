#!/usr/bin/env python3
"""Submit newly published Codeedge pages to IndexNow using only stdlib.

Dry runs never make network requests. Live submissions are limited to the
verified host and canonical pages currently listed in the XML sitemap.
"""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

HOST = "codeedge.online"
ORIGIN = f"https://{HOST}"
ENDPOINT = "https://api.indexnow.org/indexnow"
ROOT = Path(__file__).resolve().parents[1]


def find_key():
    matches = [p for p in ROOT.glob("*.txt")
               if re.fullmatch(r"[a-f0-9]{32}\.txt", p.name)
               and p.read_text(encoding="utf-8").strip() == p.stem]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one matching 32-hex IndexNow key file at site root")
    return matches[0].stem


def sitemap_urls():
    tree = ET.parse(ROOT / "sitemap.xml")
    links = [n.text.strip() for n in tree.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc") if n.text]
    if not links:
        raise RuntimeError("Sitemap is empty")
    for link in links:
        u = urlsplit(link)
        if u.scheme != "https" or u.netloc != HOST or u.query or u.fragment:
            raise RuntimeError(f"Unexpected sitemap URL: {link}")
    return links


def changed_urls(before, available):
    if not re.fullmatch(r"[0-9a-f]{40}", before or "") or before == "0" * 40:
        raise RuntimeError("Expected a valid push 'before' commit SHA; use --mode all for first-time manual submission")
    paths = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", before, "HEAD", "--"],
        cwd=ROOT, text=True,
    ).splitlines()
    found = set()
    for path in paths:
        if path == "index.html":
            link = ORIGIN + "/"
        elif path.endswith("/index.html"):
            link = ORIGIN + "/" + path[:-len("index.html")]
        else:
            continue
        if link in available:
            found.add(link)
    return sorted(found)


def verify_hosted_key(key, attempts=8):
    url = f"{ORIGIN}/{key}.txt"
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Codeedge-IndexNow/1.0"})
            with urllib.request.urlopen(req, timeout=12) as response:
                body = response.read(256).decode("utf-8").strip()
            if body == key:
                return
        except (urllib.error.URLError, TimeoutError):
            pass
        if attempt + 1 < attempts:
            time.sleep(12)
    raise RuntimeError("IndexNow key not publicly available yet; no URLs were submitted")


def main():
    parser = argparse.ArgumentParser(description="Submit changed canonical Codeedge URLs to IndexNow")
    parser.add_argument("--mode", choices=("all", "changed"), required=True)
    parser.add_argument("--before", default="", help="Push event's previous SHA for changed mode")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    key = find_key()
    available = sitemap_urls()
    urls = available if args.mode == "all" else changed_urls(args.before, set(available))
    print(f"Eligible URLs: {len(urls)} (mode={args.mode})")
    if not urls:
        print("Nothing new to submit")
        return
    if args.dry_run:
        print(json.dumps({"host": HOST, "urlList": urls}, indent=2))
        return

    verify_hosted_key(key)
    payload = json.dumps({
        "host": HOST, "key": key,
        "keyLocation": f"{ORIGIN}/{key}.txt",
        "urlList": urls,
    }).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=payload, method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Codeedge-IndexNow/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"IndexNow submission rejected: HTTP {exc.code}") from exc
    if status not in (200, 202):
        raise RuntimeError(f"Unexpected IndexNow HTTP status {status}")
    print(f"IndexNow accepted submission of {len(urls)} URLs (HTTP {status}); this is not an indexing guarantee")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError, ET.ParseError) as exc:
        sys.exit(str(exc))
