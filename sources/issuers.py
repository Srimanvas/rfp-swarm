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
import argparse
import concurrent.futures as cf
from datetime import datetime
import io, html, json, os, re, time
import urllib.error, urllib.request

import os as _os, sys as _sys
# sources/ adapters import board/ledger from the repo root, which is not on
# sys.path when run as `python sources/<name>.py`. Put the root on the path.
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import board
import ledger

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

ROSTER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "issuers.txt")

# Ordered by how often each actually turns out to be the right one.
NEWLINE = chr(10)

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
    """Roster lines, in one of three shapes:

        domain                        never probed
        domain<TAB>url                has an RFP page
        domain<TAB>-<TAB>YYYY-MM-DD   probed on that date, no page found

    The third shape is what makes a large roster affordable. A domain with no RFP
    page costs every path in PATHS, and most domains have none, so re-probing the
    whole roster weekly is the dominant cost: at ~8,800 domains that is hours per
    run. Recording the date means a miss is retried on a slow cycle (see
    --recheck-days) instead of every single run. Comments are allowed.
    """
    out = []
    if not os.path.exists(ROSTER):
        return out
    for line in open(ROSTER, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        url = parts[1] if len(parts) > 1 else ""
        checked = parts[2] if len(parts) > 2 else ""
        out.append((parts[0], "" if url == "-" else url, checked))
    return out


def stale(checked, days):
    """True if a past miss is old enough to be worth probing again."""
    if not checked:
        return True
    try:
        when = datetime.strptime(checked, "%Y-%m-%d")
    except ValueError:
        return True
    return (datetime.now() - when).days >= days


def load_lines():
    """Roster lines verbatim, comments included, so --discover can rewrite the
    file without dropping the cluster labels that record where each domain came
    from. The previous rewrite discarded them silently."""
    if not os.path.exists(ROSTER):
        return []
    return [l.rstrip(NEWLINE) for l in io.open(ROSTER, encoding="utf-8")]


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
    ap.add_argument("--limit", type=int, default=0,
                    help="probe at most N domains this run, then write. The roster "
                         "is only saved when the run ends, so at thousands of "
                         "domains an un-chunked run risks hours of lost work. "
                         "0 means no limit")
    ap.add_argument("--recheck-days", type=int, default=90,
                    help="re-probe a past miss only if it is this many days old "
                         "(default 90; 0 forces every domain)")
    ap.add_argument("--jobs", type=int, default=12,
                    help="parallel domains during --discover (default 12)")
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
        # A domain with NO RFP page costs every path in PATHS, and most domains
        # have none, so the negative case dominates the runtime. Two things keep
        # that affordable at roster sizes in the thousands: fan out across domains
        # (each worker still paces itself between its own paths, and workers hit
        # different hosts so no host sees a burst), and skip domains already
        # probed recently.
        today = datetime.now().strftime("%Y-%m-%d")
        todo = [(d, u, c) for d, u, c in roster
                if u or stale(c, a.recheck_days)]
        if a.limit:
            todo = todo[:a.limit]
        skipped = len(roster) - len(todo)
        if skipped:
            print("skipping %d domains probed within the last %d days "
                  "(--recheck-days 0 to force)" % (skipped, a.recheck_days))

        def resolve(item):
            domain, known, _ = item
            return domain, (known or discover(domain))

        with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
            resolved = dict(ex.map(resolve, todo))
        found = sum(1 for v in resolved.values() if v)
        for domain, _, _ in todo:
            print("  %-34s %s" % (domain, resolved[domain] or "(no RFP page found)"))

        # Never drop a line. Comments, cluster labels and every domain survive;
        # the roster only ever GAINS information.
        prior = {d: (u, c) for d, u, c in roster}
        out = []
        for line in load_lines():
            bare = line.strip()
            if not bare or bare.startswith("#"):
                out.append(line)
                continue
            d = bare.split("\t")[0]
            if d in resolved:
                url = resolved[d]
                out.append("%s\t%s" % (d, url) if url
                           else "%s\t-\t%s" % (d, today))
            else:
                out.append(line)            # untouched this run, keep verbatim
        with io.open(ROSTER, "w", encoding="utf-8", newline=NEWLINE) as fh:
            fh.write(NEWLINE.join(out) + NEWLINE)
        print("\n%d of %d probed domains have a findable RFP page "
              "(%d already known, %d skipped)"
              % (found, len(todo), sum(1 for _, u, _ in roster if u), skipped))
        return

    ledg = ledger.load(a.seen)
    rows, live = [], 0
    for domain, url, _checked in roster:
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
        json.dump(ledger.envelope(rows), open(a.json, "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    main()
