#!/usr/bin/env python3
"""Private, read-only SEO reports. NEVER put report output in the public website repo."""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

SITE = "https://codeedge.online/"
GSC = "https://www.googleapis.com/webmasters/v3/sites/"
GA4 = "https://analyticsdata.googleapis.com/v1beta/properties/"
BING = "https://ssl.bing.com/webmaster/api.svc/json/"

def request_json(url, payload=None, token=None):
    if not url.startswith((GSC, GA4, BING)):
        raise ValueError("Unsupported reporting endpoint")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json", "User-Agent": "CodeedgeSEO/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if data is not None:
        headers["Content-Type"] = "application/json"
    try:
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method="POST" if data is not None else "GET")
        with urllib.request.urlopen(req, timeout=25) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        # Never expose sensitive Bing API key from URL in exception messages.
        raise RuntimeError("Reporting API rejected request (HTTP %s)" % error.code) from None
    except urllib.error.URLError:
        raise RuntimeError("Reporting API network error") from None
    if not isinstance(result, (dict, list)):
        raise RuntimeError("Invalid reporting API response")
    return result

def google_token(credentials_json):
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        info = json.loads(credentials_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=[
            "https://www.googleapis.com/auth/webmasters.readonly",
            "https://www.googleapis.com/auth/analytics.readonly",
        ])
        creds.refresh(Request())
        return creds.token
    except Exception:
        raise RuntimeError("Read-only Google authorization failed; check service account, API access and permissions") from None

def gsc_report(token, start, end):
    url = GSC + urllib.parse.quote(SITE, safe="") + "/searchAnalytics/query"
    body = {"startDate": start, "endDate": end, "type": "web"}
    totals = request_json(url, body, token)
    queries = request_json(url, dict(body, dimensions=["query"], rowLimit=25), token)
    pages = request_json(url, dict(body, dimensions=["page"], rowLimit=25), token)
    first = (totals.get("rows") or [{}])[0]
    def convert(response):
        return [{"name": r.get("keys", [""])[0], "clicks": r.get("clicks", 0),
                 "impressions": r.get("impressions", 0), "position": r.get("position")}
                for r in response.get("rows", [])]
    return {"status": "ok", "clicks": first.get("clicks", 0),
            "impressions": first.get("impressions", 0),
            "queries": convert(queries), "pages": convert(pages),
            "note": "Top rows only; zero rows is not proof a page is unindexed."}

def ga4_report(token, property_id, start, end):
    if not re.fullmatch(r"[0-9]{4,20}", property_id):
        raise RuntimeError("Numeric GA4_PROPERTY_ID required, not G- measurement ID")
    url = GA4 + property_id + ":runReport"
    dates = [{"startDate": start, "endDate": end}]
    def run(metrics, dimensions=None):
        body = {"dateRanges": dates, "metrics": [{"name": x} for x in metrics]}
        if dimensions:
            body["dimensions"] = [{"name": x} for x in dimensions]
        return request_json(url, body, token)
    summary = run(["activeUsers", "sessions", "screenPageViews"])
    values = (summary.get("rows") or [{}])[0].get("metricValues") or []
    nums = [int(float(v.get("value", 0))) for v in values]
    events = run(["eventCount"], ["eventName"])
    names = {}
    for row in events.get("rows", []):
        name = (row.get("dimensionValues") or [{}])[0].get("value", "")
        total = (row.get("metricValues") or [{}])[0].get("value", "0")
        if name:
            names[name] = int(float(total))
    return {"status": "ok", "active_users": nums[0] if len(nums) > 0 else 0,
            "sessions": nums[1] if len(nums) > 1 else 0,
            "page_views": nums[2] if len(nums) > 2 else 0,
            "events": names, "note": "Analytics subject to visitor consent and measurement setup."}

def bing_date(raw):
    if not isinstance(raw, str):
        return None
    match = re.search(r"/Date\((-?\d+)(?:[+-]\d{4})?\)/", raw)
    if match:
        try:
            return datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc).date().isoformat()
        except (ValueError, OverflowError):
            return None
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        return None

def bing_report(key, start, end):
    if not re.fullmatch(r"[\w-]{12,256}", key):
        raise RuntimeError("Invalid Bing Webmaster API key format")
    def query(method):
        url = BING + method + "?" + urllib.parse.urlencode({"siteUrl": SITE, "apikey": key})
        result = request_json(url)
        if not isinstance(result, dict) or not isinstance(result.get("d"), list):
            raise RuntimeError("Unexpected Bing JSON response")
        return result["d"]
    daily = []
    for row in query("GetRankAndTrafficStats"):
        when = bing_date(row.get("Date"))
        if when and start <= when <= end:
            daily.append({"date": when, "clicks": int(row.get("Clicks") or 0),
                          "impressions": int(row.get("Impressions") or 0)})
    terms = []
    for row in query("GetQueryStats"):
        when = bing_date(row.get("Date"))
        if when and start <= when <= end:
            terms.append({"date": when, "query": row.get("Query") or "",
                          "clicks": int(row.get("Clicks") or 0),
                          "impressions": int(row.get("Impressions") or 0)})
    terms.sort(key=lambda x: x["clicks"], reverse=True)
    return {"status": "ok", "clicks": sum(x["clicks"] for x in daily),
            "impressions": sum(x["impressions"] for x in daily),
            "queries": terms[:25], "daily": sorted(daily, key=lambda x: x["date"]),
            "note": "Bing figures may include web, chat, images and other verticals."}

def collect(env, today=None):
    today = today or date.today()
    end = today - timedelta(days=3)
    start = end - timedelta(days=27)
    result = {"site": SITE, "start": str(start), "end": str(end), "sources": {}}
    account = env.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    token = None
    google_error = "GOOGLE_SERVICE_ACCOUNT_JSON authorization required"
    if account:
        try:
            token = google_token(account)
            google_error = None
        except RuntimeError as error:
            google_error = str(error)
    for name in ("gsc", "ga4"):
        if google_error:
            result["sources"][name] = {"status": "authorization_required", "reason": google_error}
            continue
        if name == "ga4" and not env.get("GA4_PROPERTY_ID"):
            result["sources"][name] = {"status": "authorization_required", "reason": "Numeric GA4_PROPERTY_ID required"}
            continue
        try:
            if name == "gsc":
                data = gsc_report(token, str(start), str(end))
            else:
                data = ga4_report(token, env["GA4_PROPERTY_ID"], str(start), str(end))
        except RuntimeError as error:
            data = {"status": "error", "reason": str(error)}
        result["sources"][name] = data
    if not env.get("BING_WEBMASTER_API_KEY"):
        result["sources"]["bing"] = {"status": "authorization_required", "reason": "Bing Webmaster API key required"}
    else:
        try:
            result["sources"]["bing"] = bing_report(env["BING_WEBMASTER_API_KEY"], str(start), str(end))
        except RuntimeError as error:
            result["sources"]["bing"] = {"status": "error", "reason": str(error)}
    return result

def to_markdown(report):
    lines = ["# Codeedge private SEO report", "",
             "Period: " + report["start"] + " through " + report["end"], ""]
    for name in ("gsc", "ga4", "bing"):
        data = report["sources"][name]
        lines += ["## " + {"gsc": "Google Search Console", "ga4": "Google Analytics 4",
                          "bing": "Bing Webmaster"}[name], "", "Status: **" + data["status"] + "**", ""]
        if data["status"] == "ok":
            if name in ("gsc", "bing"):
                lines.append("Clicks: %s; impressions: %s" % (data["clicks"], data["impressions"]))
                lines.append("Top queries: " + ", ".join(
                    str(q.get("name") or q.get("query")) + " (" + str(q["clicks"]) + ")"
                    for q in data["queries"][:10]))
            else:
                lines.append("Active users: %s; sessions: %s; page views: %s" %
                             (data["active_users"], data["sessions"], data["page_views"]))
                lines.append("Tracked events: " + ", ".join(
                    "%s (%s)" % (key, value) for key, value in sorted(data["events"].items())))
            lines.append(data.get("note", ""))
        else:
            lines.append(data.get("reason", "Private access needed"))
        lines.append("")
    lines += ["**PRIVATE REPORT: do not commit or publish it.**", ""]
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, help="Private local directory OUTSIDE public repo")
    args = parser.parse_args()
    folder = Path(args.output_dir).expanduser().resolve()
    root = Path(__file__).resolve().parents[1]
    if folder == root or root in folder.parents:
        raise SystemExit("Refusing to save private report inside public Codeedge website repo")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    report = collect(os.environ)
    for name, content in (("report.json", json.dumps(report, indent=2)),
                          ("report.md", to_markdown(report))):
        target = folder / name
        target.write_text(content + "\n", encoding="utf-8")
        try:
            target.chmod(0o600)
        except OSError:
            pass
    print("Private report generated; source connection states: " + ", ".join(
        name + "=" + section["status"] for name, section in report["sources"].items()))
    return 0 if all(x["status"] == "ok" for x in report["sources"].values()) else 2

if __name__ == "__main__":
    sys.exit(main())
