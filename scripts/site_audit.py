#!/usr/bin/env python3
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import json, re, sys, xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
DOMAIN="https://codeedge.online"
LEGACY=("codeedge.co.uk","020 1234 5678","hello@codeedge.co.uk")
errors=[]
titles={}
canonicals={}
production=[]

class AuditParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title=False; self.title_text=[]; self.h1=0; self.meta_desc=False; self.canonical=None
        self.links=[]; self.images=[]; self.blank=[]; self.jsonld=[]; self.in_jsonld=False; self.json_buf=[]
        self.lang=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="html": self.lang=a.get("lang")
        if tag=="title": self.title=True
        if tag=="h1": self.h1+=1
        if tag=="meta" and a.get("name","").lower()=="description" and a.get("content","").strip(): self.meta_desc=True
        if tag=="link" and a.get("rel","").lower()=="canonical": self.canonical=a.get("href")
        if tag=="a" and a.get("href"): 
            self.links.append(a["href"])
            if a.get("target")=="_blank": self.blank.append((a["href"],a.get("rel","")))
        if tag=="img": self.images.append(a)
        if tag=="script" and a.get("type","").lower()=="application/ld+json":
            self.in_jsonld=True; self.json_buf=[]
    def handle_endtag(self,tag):
        if tag=="title": self.title=False
        if tag=="script" and self.in_jsonld:
            self.in_jsonld=False; self.jsonld.append("".join(self.json_buf).strip())
    def handle_data(self,data):
        if self.title: self.title_text.append(data)
        if self.in_jsonld: self.json_buf.append(data)

def expected_file(href):
    clean=urlparse(href).path
    if clean=="/": return ROOT/"index.html"
    if clean.endswith("/"): return ROOT/clean.lstrip("/")/"index.html"
    return ROOT/clean.lstrip("/")

html_files=sorted(ROOT.rglob("*.html"))
for f in html_files:
    rel=f.relative_to(ROOT).as_posix()
    raw=f.read_text(encoding="utf-8")
    if any(x.lower() in raw.lower() for x in LEGACY):
        errors.append(f"{rel}: legacy domain/contact placeholder found")
    p=AuditParser()
    try: p.feed(raw)
    except Exception as e: errors.append(f"{rel}: HTML parse error: {e}"); continue
    redirect=rel in {"privacy.html","terms.html"}
    notfound=rel=="404.html"
    if not redirect:
        if p.lang!="en-GB": errors.append(f"{rel}: html lang must be en-GB")
        title=" ".join("".join(p.title_text).split())
        if not title: errors.append(f"{rel}: missing title")
        elif title in titles: errors.append(f"{rel}: duplicate title with {titles[title]}")
        else: titles[title]=rel
        if p.h1!=1: errors.append(f"{rel}: expected one h1, found {p.h1}")
        if not notfound and not p.meta_desc: errors.append(f"{rel}: missing meta description")
        if not notfound:
            if not p.canonical or not p.canonical.startswith(DOMAIN+"/"): errors.append(f"{rel}: invalid/missing canonical")
            elif p.canonical in canonicals: errors.append(f"{rel}: duplicate canonical with {canonicals[p.canonical]}")
            else: canonicals[p.canonical]=rel; production.append(p.canonical)
    for payload in p.jsonld:
        try: json.loads(payload)
        except Exception as e: errors.append(f"{rel}: invalid JSON-LD: {e}")
    for img in p.images:
        if "alt" not in img and img.get("aria-hidden")!="true": errors.append(f"{rel}: image missing alt")
    for href,relattr in p.blank:
        if "noopener" not in relattr.split(): errors.append(f"{rel}: target=_blank missing noopener for {href}")
    for href in p.links:
        if href.startswith(("mailto:","tel:","https://","http://","#")): continue
        if not href.startswith("/"): continue
        if href.startswith("/assets/") or href in {"/manifest.webmanifest","/robots.txt","/sitemap.xml"}:
            target=ROOT/href.lstrip("/")
        else:
            target=expected_file(href)
        if not target.exists(): errors.append(f"{rel}: broken internal link {href} -> {target.relative_to(ROOT)}")

# Sitemap should contain every canonical production page and no stale domain.
sitemap=ROOT/"sitemap.xml"
if not sitemap.exists(): errors.append("sitemap.xml: missing")
else:
    text=sitemap.read_text(encoding="utf-8")
    if "codeedge.co.uk" in text: errors.append("sitemap.xml: legacy domain found")
    try:
        ns={"s":"http://www.sitemaps.org/schemas/sitemap/0.9"}
        root=ET.fromstring(text)
        urls={e.text.strip() for e in root.findall("s:url/s:loc",ns) if e.text}
        expected=set(production)
        missing=expected-urls; extra=urls-expected
        if missing: errors.append("sitemap.xml: missing "+", ".join(sorted(missing)))
        if extra: errors.append("sitemap.xml: unexpected "+", ".join(sorted(extra)))
    except Exception as e: errors.append(f"sitemap.xml: invalid XML: {e}")

robots=(ROOT/"robots.txt").read_text(encoding="utf-8") if (ROOT/"robots.txt").exists() else ""
if "Sitemap: https://codeedge.online/sitemap.xml" not in robots: errors.append("robots.txt: canonical sitemap missing")
if not (ROOT/"CNAME").exists() or (ROOT/"CNAME").read_text().strip()!="codeedge.online": errors.append("CNAME: must contain codeedge.online")

if errors:
    print("SITE AUDIT FAILED")
    for e in errors: print("-",e)
    sys.exit(1)
print(f"SITE AUDIT PASSED: {len(html_files)} HTML files, {len(production)} canonical pages, {len(titles)} unique titles.")
