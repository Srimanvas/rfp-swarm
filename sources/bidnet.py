"""BidNet Direct sweep -- state & local solicitations, free listing, no login.

~25,000 open bids across US state/local purchasing groups. The results page is
server-rendered and the keyword filter demonstrably bites (control: 25,365 open
-> 925 for 'software'), so this is a real filter, not a silently-ignored param.

    python bidnet.py                  # default keyword set
    python bidnet.py --json bn.json --pages 4

ponytail: regex over the result rows, stdlib only, same shape as nyscr.py.
"""
import argparse, html, json, re, time
from datetime import datetime
import urllib.parse, urllib.request

import board
import ledger

BASE = "https://www.bidnetdirect.com/solicitations/open-bids"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

KEYWORDS = [
    # custom builds -- the highest-value shape
    "software development", "custom software", "application development",
    "web application", "system development", "software design",
    # workflow / line-of-business systems agencies pay real money for
    "case management system", "permitting software", "licensing system",
    "grants management", "inspection software", "asset management system",
    "document management system", "workflow automation", "data migration",
    "system integration", "systems modernization", "legacy system",
    "business intelligence", "data warehouse", "API integration",
    # the AI lane
    "artificial intelligence", "machine learning", "generative AI",
    # web, kept narrow -- lower value, still ours
    "website redesign", "content management system",
]

KILL = re.compile(r"\b(renew|licen[cs]e |subscription|sole source|maintenance agreement|"
                  r"cabling|printer|toner|furniture|janitorial|construction|"
                  r"paving|roofing|hvac|vehicle|uniform|food service|staffing|"
                  r"staff augmentation|direct award|point.of.sale|managed service|"
                  # "system" also names a lot of physical plant -- none of it is ours
                  r"elevator|bus wash|vacuum|chiller|cooling|boiler|blower|solar|"
                  r"photovoltaic|door reader|access control|seating|crash alarm|"
                  r"parking access|harbor|sewer collection|wastewater|water chiller|"
                  # hard screen: awardable projects only -- no RFIs, no open-ended vehicles
                  r"RFI|request for information|sources sought|expression of interest|"
                  r"BAA|broad agency|research announcement|roster|photographer|videographer|"
                  r"survey|arresting|circuit breaker|overhaul|job order contract)\b", re.I)


def fetch(keywords, page=1):
    q = {"keywords": keywords, "solSearchStatus": "open"}
    if page > 1:
        q["pageNumberSelect"] = page
    url = BASE + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def total(page_html):
    m = re.search(r"([\d,]+)\s*results", page_html, re.I)
    return int(m.group(1).replace(",", "")) if m else 0


def parse(page_html):
    rows = []
    for block in re.split(r'<a id="searchResultSol_notice_\d+"', page_html)[1:]:
        block = block[:2600]
        href = re.search(r'href="([^"]+)"', block)

        def grab(cls):
            m = re.search(r'class="%s"[^>]*>(.*?)</span>' % cls, block, re.S)
            return html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))).strip() if m else ""

        dates = re.findall(r'class="dateValue"[^>]*>\s*([\d/]+)', block)
        rows.append({"url": "https://www.bidnetdirect.com" + href.group(1).split("?")[0]
                            if href else "",
                     "title": re.sub(r"\s+", " ", grab("rowTitle")),
                     "location": grab("location"),
                     "published": dates[0] if dates else "",
                     "closing": dates[1] if len(dates) > 1 else "",
                     "days_left": re.sub(r"\s+", " ", grab("timeRemaining"))})
    return [r for r in rows if r["title"]]


def days_out(d):
    try:
        m, dd, y = (int(x) for x in d.split("/"))
        return (datetime(y, m, dd) - datetime.now()).days
    except Exception:
        return None


def screen(r):
    if KILL.search(r["title"]):
        return "REJECT", "kill word in title"
    n = days_out(r["closing"])
    if n is None:
        return "REJECT", "no closing date (standing catalogue entry)"
    if n < 7:
        return "REJECT", "closes in %s days" % n
    # a year+ out is a standing roster or master agreement, not a project to bid
    if n > 300:
        return "REJECT", "open-ended vehicle (closes %d days out)" % n
    return "REVIEW", "survived title screen"


def title_hit(kw, title):
    """True if any substantive word of the keyword appears in the title."""
    words = [w for w in re.findall(r"[a-z]{4,}", kw.lower())]
    t = (title or "").lower()
    return any(w in t for w in words) if words else True


def overview(url):
    """Free scope summary on the detail page. Issuer and source are login-locked,
    but the summary is enough to tell a build from a product mandate."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        s = r.read().decode("utf-8", "replace")
    m = re.search(r"AI Overview\s*</[^>]+>\s*(.*?)(?:Location|Publication Date)", s, re.S)
    if not m:
        m = re.search(r"AI Overview(.{0,900}?)Location", re.sub(r"<[^>]+>", " ", s), re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(1)))).strip() if m else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--pages", type=int, default=8, help="pages per keyword (25/page)")  # Phase 0 fix 3: was 2, i.e. ~1% of 24,543
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--seen", help="ledger JSON to dedupe against")
    a = ap.parse_args()

    ledg = ledger.load(a.seen)
    control = total(fetch(""))
    print("control: unfiltered open bids = %d" % control)

    seen, rows = set(), []
    for kw in KEYWORDS:
        first = fetch(kw)
        n = total(first)
        if n >= control:
            print("  !! '%s' returned %d -- filter did NOT bite, skipping" % (kw, n))
            continue
        pages = [first] + [fetch(kw, p) for p in range(2, min(a.pages, -(-n // 25)) + 1)]
        for pg in pages:
            for r in parse(pg):
                key = (r["title"], r["location"])
                if key in seen:
                    continue
                seen.add(key)
                r["keyword"] = kw
                r["verdict"], r["reason"] = screen(r)
                # Phase 0 fix 3b: BidNet keyword search hits DOCUMENT BODY text, not
                # titles -- that is how "Flooring Abatement" and "KSP Drug Testing"
                # came back as software matches on 2026-08-28. Flag, never drop:
                # a vague title ("RFP 2026-14") can still be a real find.
                if r["verdict"] == "REVIEW" and not title_hit(kw, r["title"]):
                    r["verdict"], r["reason"] = "BODY-ONLY", "keyword matched document text, not the title"
                r["id"] = r["url"].rsplit("/", 1)[-1]
                r["is_new"] = ledger.key("bidnet", r["id"]) not in ledg
                rows.append(r)
        print("  %-28s %5d hits" % (kw, n))
        time.sleep(1)               # ponytail: polite scraper

    board.mark(rows, board.load())
    rows.sort(key=lambda r: (r["verdict"] != "REVIEW", days_out(r["closing"]) or 999))
    nrev = sum(1 for r in rows if r["verdict"] == "REVIEW")
    nnew = sum(1 for r in rows if r["verdict"] == "REVIEW" and r.get("is_new", True))
    print("\n%d unique bids pulled -> %d REVIEW (%d new)" % (len(rows), nrev, nnew))
    print("=" * 78)
    for r in rows:
        if r["verdict"] != "REVIEW" and not a.all:
            continue
        print("\n[%s]%s %s" % (r["verdict"], " NEW" if r.get("is_new", True) else "", r["title"]))
        print("  %s | closes %s (%s) | via '%s'"
              % (r["location"], r["closing"], r["days_left"], r["keyword"]))
    if a.json:
        json.dump({"results": rows}, open(a.json, "w", encoding="utf-8"), indent=2)

if __name__ == "__main__":
    main()
