"""NY State Contract Reporter sweep.

Every NY agency, authority, SUNY/CUNY campus and public benefit corp must
advertise >=$50k here. The free results page names issuer, CR#, dates and
category; only the documents sit behind the login.

    python nyscr.py               # IT + admin/technical + marketing, open, awardable
    python nyscr.py --json ny.json

ponytail: regex over the result cards, no HTML parser dependency. The markup
is a stable server-rendered Bootstrap card; swap in bs4 if it ever churns.
"""
import argparse, html, json, re, sys, time
from datetime import datetime
import urllib.parse, urllib.request

import board
import ledger

BASE = "https://www.nyscr.ny.gov/Ads/Search"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

# NYSCR category codes -> label. Only the ones we can actually do work in.
CATEGORIES = {16: "Information Technology",
              1: "Administrative & Technical",
              3: "Advertising, Graphic Arts, Marketing & Interior Design",
              28: "Telecommunications"}

AD_TYPE_GENERAL = 1        # awardable. 4/10/11/12 etc. are RFI/grant/surplus noise.

# Same kill words the SAM sweep uses -- a rename or a licence renewal is not a build.
KILL = re.compile(r"\b(renew|licen[cs]e|subscription|sole source|intent to|"
                  r"brand name|maintenance agreement|extension of)\b", re.I)
FIT = re.compile(r"\b(software|application|web ?site|web ?based|portal|platform|"
                 r"system|develop|programming|data|dashboard|integrat|"
                 r"artificial intelligence|machine learning|\bAI\b|modern)", re.I)


def fetch(cat, skip=0, top=50):
    q = [("Status", "Open"), ("AdTypes[]", AD_TYPE_GENERAL),
         ("Sort", "-DateIssued"), ("DateFilter", "All Time"),
         ("Top", top), ("Skip", skip)]
    if cat is not None:                      # None = every category (Phase 0 fix 4)
        q.insert(2, ("Categories[]", cat))
    url = BASE + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def opportunity_count(page):
    m = re.search(r"All Open Opportunities:\s*</span>\s*([\d,]+)", page)
    return int(m.group(1).replace(",", "")) if m else -1


def control():
    """Prove the category filter actually bit. An ignored filter param is the
    failure mode that makes a sweep look clean while screening nothing."""
    q = [("Status", "Open"), ("AdTypes[]", AD_TYPE_GENERAL), ("Top", 5)]
    url = BASE + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=45) as r:
        unfiltered = opportunity_count(r.read().decode("utf-8", "replace"))
    filtered = opportunity_count(fetch(16, 0, 5))       # 16 = Information Technology
    bit = unfiltered > 0 and 0 < filtered < unfiltered
    print("control: open awardable ads=%d ; +Categories[]=16 -> %d ; filter bit: %s"
          % (unfiltered, filtered, "YES" if bit else "NO"))
    return bit


def field(block, name):
    m = re.search(r">\s*%s:?\s*</div>\s*<div[^>]*>(.*?)</div>" % name, block, re.S)
    return html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))).strip() if m else ""


def parse(page):
    out = []
    # cards are <div class="opp-list-item ..." data-ad-id="NNN"> ... </div>
    parts = re.split(r'<div class="opp-list-item[^"]*" data-ad-id="(\d+)"', page)
    for i in range(1, len(parts), 2):
        ad_id, block = parts[i], parts[i + 1]
        t = re.search(r'title="Full Title:\s*([^"]*)"', block)
        title = html.unescape(t.group(1)).strip() if t else ""
        out.append({"ad_id": ad_id,
                    "title": re.sub(r"\s+", " ", title),
                    "cr": field(block, "CR#"),
                    "agency": field(block, "Agency"),
                    "division": field(block, "Division"),
                    "issued": field(block, "Issue date"),
                    "due": field(block, "Due date"),
                    "category": field(block, "Category"),
                    "ad_type": field(block, "Ad type"),
                    # NYSCR has NO public per-ad page -- /Ads/Details/<id> redirects
                    # to login. Searching the CR number is the public route to the ad.
                    "url": BASE + "?Status=Open&Keyword=%s" % ad_id})
    return out


def days_out(due):
    try:
        m, d, y = (int(x) for x in due.split("/"))
        return (datetime(y, m, d) - datetime.now()).days
    except Exception:
        return None


def screen(ad):
    text = "%s %s" % (ad["title"], ad["category"])
    if KILL.search(text):
        return "REJECT", "kill word in title"
    n = days_out(ad["due"])
    # a due date a year+ out is a standing enrolment program, not a project to bid
    if n is not None and n > 300:
        return "REJECT", "rolling enrolment program (due %d days out)" % n
    # Phase 0 fix 1b (user-approved 2026-09-15): aligned with sam.py. Was 7.
    if n is not None and n < 3:
        return "REJECT", "closes in %d days - below the 3-day floor" % n
    if n is not None and n < 10 and FIT.search(text):
        return "REVIEW", "SHORT-FUSE: closes in %d days - decide fast" % n
    if not FIT.search(text):
        return "WEAK", "no build signal in title"
    return "REVIEW", "fit signal in title"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write results here")
    ap.add_argument("--seen", help="ledger JSON to dedupe against")
    ap.add_argument("--all", action="store_true", help="print WEAK and REJECT too")
    ap.add_argument("--categories", type=int, nargs="*", help="restrict to these NYSCR category codes (default: all)")
    a = ap.parse_args()

    ledg = ledger.load(a.seen)
    trusted = control()
    seen, rows = set(), []
    # Phase 0 fix 4: the whitelist saw 16% of NY. Agencies file a build under the
    # BUYING DEPARTMENT's category -- "OCUE Modernization" is Educational &
    # Recreational, "Highway Work Permit System" is Miscellaneous. Sweep all
    # categories and let the FIT regex screen. --categories restores the old behaviour.
    cats = [(c, CATEGORIES.get(c, str(c))) for c in a.categories] if a.categories else [(None, "all")]
    for cat, label in cats:
        skip = 0
        while True:
            page = fetch(cat, skip)
            got = parse(page)
            if not got:
                break
            for ad in got:
                if ad["ad_id"] in seen:
                    continue
                seen.add(ad["ad_id"])
                ad["nyscr_category"] = label
                ad["verdict"], ad["reason"] = screen(ad)
                ad["is_new"] = ledger.key("nyscr", ad["ad_id"]) not in ledg
                rows.append(ad)
            if len(got) < 50:
                break
            skip += 50
            time.sleep(1)          # ponytail: be a polite scraper

    board.mark(rows, board.load())
    rows.sort(key=lambda r: (r["verdict"] != "REVIEW", r["due"]))
    n = {v: sum(1 for r in rows if r["verdict"] == v) for v in ("REVIEW", "WEAK", "REJECT")}
    nnew = sum(1 for r in rows if r["verdict"] == "REVIEW" and r.get("is_new", True))
    print("NYSCR sweep: %d open awardable ads -> %d REVIEW (%d new), %d WEAK, %d REJECT"
          % (len(rows), n["REVIEW"], nnew, n["WEAK"], n["REJECT"]))
    print("=" * 78)
    for r in rows:
        if r["verdict"] != "REVIEW" and not a.all:
            continue
        print("\n[%s] %s" % (r["verdict"], r["title"] or "(no title)"))
        print("  %s / %s | CR# %s | due %s" % (r["agency"], r["division"], r["cr"], r["due"]))
        print("  %s" % r["category"])
        print("  %s" % r["url"])
    if a.json:
        json.dump({"results": rows}, open(a.json, "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    main()
