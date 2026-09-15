"""Issuer-page poller -- mission-driven organisations' own RFP pages.

The only channel where quality AND competition both move in our favour: these
postings are never syndicated. Meridian International Center (~$499K over four
years) came from meridian.org/rfp and appeared on no aggregator at all.

The weakness of the channel is that it needs a roster. This script removes the
other half of the problem -- guessing the path -- by probing the common ones per
domain. Add a domain to issuers.txt and it finds the page itself.

    python issuers.py --discover        # find each domain's RFP page, update roster
    python issuers.py                   # poll known pages, report live postings

ponytail: stdlib only. The roster is a text file, not a database.
"""
import argparse, html, json, os, re, time
import urllib.error, urllib.request

import board
import ledger

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

ROSTER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "issuers.txt")

# Ordered by how often each actually turns out to be the right one.
PATHS = ["/rfp", "/rfps", "/procurement", "/bids", "/rfp/", "/rfps/",
         "/about/procurement", "/about-us/procurement", "/work-with-us/rfp",
         "/doing-business", "/opportunities", "/request-for-proposals",
         "/about/rfps", "/who-we-are/procurement", "/vendor-opportunities"]

# A page is only interesting if it looks like it lists actual solicitations.
LIVE = re.compile(r"request for proposal|\bRFP\b|\bRFQ\b|invitation to bid|"
                  r"solicitation|proposals? due|submission deadline", re.I)

# What we can actually deliver -- see RULES.md target profile.
FIT = re.compile(r"software|application|platform|website|web site|portal|"
                 r"database|dashboard|data|digital|system|integrat|"
                 r"artificial intelligence|machine learning|\bAI\b|CRM|redesign", re.I)


def get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def load_roster():
    """Lines are 'domain' or 'domain<TAB>discovered-url'. # comments allowed."""
    out = []
    if not os.path.exists(ROSTER):
        return out
    for line in open(ROSTER, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        out.append((parts[0], parts[1] if len(parts) > 1 else ""))
    return out


def discover(domain):
    """Try the common paths; return the first that exists and looks like a
    solicitation page. Returns '' when the domain has no findable RFP page."""
    for p in PATHS:
        url = "https://%s%s" % (domain, p)
        try:
            status, body = get(url)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            continue
        if status == 200 and LIVE.search(body):
            return url
        time.sleep(0.3)
    return ""


def postings(body, base):
    """Anchor text that looks like a solicitation, with its link."""
    out = []
    for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.S):
        href, text = m.group(1), html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 12 or len(text) > 160 or not LIVE.search(text):
            continue
        if href.startswith("/"):
            href = re.sub(r"(https?://[^/]+).*", r"\1", base) + href
        elif not href.startswith("http"):
            continue
        out.append({"title": text, "url": href, "fit": bool(FIT.search(text))})
    # de-dup on title, keep order
    seen, uniq = set(), []
    for p in out:
        if p["title"] in seen:
            continue
        seen.add(p["title"])
        uniq.append(p)
    return uniq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--discover", action="store_true",
                    help="probe each domain for its RFP page and rewrite the roster")
    ap.add_argument("--seen", help="ledger JSON to dedupe against")
    ap.add_argument("--json")
    a = ap.parse_args()

    roster = load_roster()
    if not roster:
        print("no roster at %s -- add one domain per line" % ROSTER)
        return

    if a.discover:
        found, lines = 0, []
        for domain, known in roster:
            url = known or discover(domain)
            if url:
                found += 1
            lines.append("%s\t%s" % (domain, url) if url else domain)
            print("  %-34s %s" % (domain, url or "(no RFP page found)"))
        # never drop a domain: the roster only ever gains resolved URLs
        with open(ROSTER, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# Mission-driven issuers polled for their own RFP pages.\n")
            fh.write("# domain<TAB>discovered-url. Add domains freely; --discover fills the URL.\n")
            fh.write("\n".join(lines) + "\n")
        print("\n%d of %d domains have a findable RFP page" % (found, len(roster)))
        return

    ledg = ledger.load(a.seen)
    rows, live = [], 0
    for domain, url in roster:
        if not url:
            continue
        try:
            status, body = get(url, timeout=20)
        except Exception as e:
            print("  %-34s FETCH FAILED (%s)" % (domain, type(e).__name__))
            continue
        found = postings(body, url)
        live += 1
        fits = [p for p in found if p["fit"]]
        print("  %-34s %2d postings, %d in our lane" % (domain, len(found), len(fits)))
        for p in fits:
            p["issuer"] = domain
            p["source_page"] = url
            p["is_new"] = ledger.key("issuer", p["url"]) not in ledg
            rows.append(p)
        time.sleep(1)                     # ponytail: polite scraper

    board.mark(rows, board.load())
    nnew = sum(1 for r in rows if r["is_new"])
    print("\nIssuer poll: %d pages live -> %d postings in our lane (%d new)"
          % (live, len(rows), nnew))
    print("=" * 78)
    for r in rows:
        print("\n[%s]%s %s" % (r["issuer"], " NEW" if r["is_new"] else "", r["title"]))
        print("  %s" % r["url"])
    if a.json:
        json.dump({"results": rows}, open(a.json, "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    main()
