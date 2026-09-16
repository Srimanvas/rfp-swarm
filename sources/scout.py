"""Scout reachability gate -- is a candidate SOURCE worth adding at all?

Finding candidate portals is agent work. This is the gate that stops a
plausible-looking URL from becoming a permanent SOURCES.md entry: a bad PASS
costs a slot in every sweep from then on. Four hard checks -- reachable, free,
names its issuer, carries awardable notices. Anything we cannot actually read
(JS shell, no text) comes back BLOCKED with a question, never a guess.

    python sources/scout.py --probe https://example.gov/bids
    python sources/scout.py --probe URL --probe URL2 --json out-scout.json

ponytail: stdlib only, no headless browser. A JS-only portal is a human call.
"""
import argparse, html, json, re
import urllib.error, urllib.request

import os as _os, sys as _sys
# sources/ adapters import board/ledger from the repo root, which is not on
# sys.path when run as `python sources/<name>.py`. Put the root on the path.
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import ledger

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

# Never bypass any of these -- detect, report, move on.
WALL = re.compile(r"sign in|log ?in|register to view|subscribe|create an account|"
                  r"members only|captcha|cloudflare (?:challenge|ray)|"
                  r"checking your browser|attention required|"
                  r"\$\s?\d[\d.,]*\s*(?:to|per|/)\s*(?:download|view|copy)", re.I)

ISSUER = re.compile(r"\bagenc(?:y|ies)\b|organi[sz]ation|department|\bcity of\b|"
                    r"\bcounty\b|\bstate of\b|foundation|district|authority|"
                    r"university|ministry|bureau|commission|municipal", re.I)

AWARDABLE = re.compile(r"request for proposal|\bRFPs?\b|invitation to bid|\bITBs?\b|"
                       r"request for quot|\bRFQs?\b|solicitation|bid opportunit", re.I)

# Not a gate on its own -- only used to catch a page that is ONLY these.
RFI_ONLY = re.compile(r"request for information|\bRFIs?\b|sources sought|"
                      r"expression of interest|\bEOIs?\b", re.I)

MACHINE = re.compile(r"application/json|/api/|\.json\b|opendata|socrata|"
                     r"odata|\.rss\b|\.xml\b", re.I)


def fetch(url):
    """(status, body, error). Two attempts, then give up -- no retry loop."""
    err = ""
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace"), ""
        except urllib.error.HTTPError as e:
            return e.code, "", "HTTP %d" % e.code   # a status IS an answer
        except Exception as e:
            err = type(e).__name__
    return 0, "", err


def visible(body):
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", body)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def judge(url, status, body, err=""):
    """All the deciding, separate from the fetching, so --selftest can drive it."""
    ck = {"reachable": False, "free": False, "names_issuer": False,
          "awardable": False, "machine_readable": False}
    row = {"url": url, "http_status": status, "title": "", "checks": ck}

    if status != 200 or not body.strip():
        row.update(verdict="FAIL",
                   reason="not reachable (%s)" % (err or "HTTP %s, empty body" % status))
        return row

    ck["reachable"] = True
    text = visible(body)
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", body)
    title = row["title"] = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip() if m else ""
    ck["machine_readable"] = bool(MACHINE.search(body))

    wall = WALL.search(text)
    ck["free"] = not wall
    if wall:
        row.update(verdict="FAIL", reason="login/paywall marker: %r" % wall.group(0))
        return row

    # A script-heavy shell with no prose means the notices are rendered by JS --
    # checks 3 and 4 are unjudgeable from what we were served, so we ask rather
    # than guess. A thin page with no scripts is just a thin page: that FAILs.
    if len(text) < 400 and "<script" in body.lower():
        row.update(verdict="BLOCKED",
                   reason="only %d chars of text served; JS-rendered? "
                          "Does this portal list notices without JavaScript, or "
                          "does it have a JSON/API endpoint we should probe instead?"
                          % len(text))
        return row

    # "obvious org name in <title>" -- two capitalised words is the cheap tell.
    ck["names_issuer"] = bool(ISSUER.search(text)) or bool(
        re.search(r"\b[A-Z][a-z]{2,}(?: (?:of|for|the))? [A-Z][a-z]{2,}", title))
    # Awardable only if it outweighs the RFI/EOI chatter, not merely appears.
    ck["awardable"] = len(AWARDABLE.findall(text)) > len(RFI_ONLY.findall(text))

    failed = [k for k in ("names_issuer", "awardable") if not ck[k]]
    if failed:
        row.update(verdict="FAIL", reason="failed: " + ", ".join(failed))
    else:
        row.update(verdict="PASS",
                   reason="reachable, free, names its issuer, carries awardable notices")
    return row


def probe(url):
    return judge(url, *fetch(url))


def selftest():
    shell = "<html><head><title>Portal</title></head><body><script src=x.js>"             "</script><div id=root></div></body></html>"
    wall = "<html><body>" + "Please sign in to view bid opportunities. " * 20 + "</body></html>"
    good = "<html><head><title>Bids</title></head><body>" +            "The City of Springfield Purchasing Department posts each request for "            "proposal and invitation to bid here. Current solicitation list. " * 6 + "</body></html>"
    thin = "<html><head><title>Example Domain</title></head><body>Nothing here.</body></html>"
    assert judge("u", 200, shell)["verdict"] == "BLOCKED"
    assert judge("u", 200, wall)["verdict"] == "FAIL" and not judge("u", 200, wall)["checks"]["free"]
    assert judge("u", 200, good)["verdict"] == "PASS", judge("u", 200, good)
    assert judge("u", 200, thin)["verdict"] == "FAIL"
    assert judge("u", 404, "", "HTTP 404")["verdict"] == "FAIL"
    # RFI-only pages must not ride in on one stray "RFP" mention
    rfi = good.replace("request for proposal and invitation to bid",
                       "request for information and sources sought notice")
    assert not judge("u", 200, rfi)["checks"]["awardable"]
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser(
        description="Gate a candidate procurement source before it earns a SOURCES.md line.")
    ap.add_argument("--probe", action="append", metavar="URL", default=[],
                    help="candidate source URL (repeatable)")
    ap.add_argument("--json", help="write the shared ledger envelope here")
    ap.add_argument("--selftest", action="store_true", help="offline check of the gate logic")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if not a.probe:
        ap.error("give at least one --probe URL (or --selftest)")

    rows = [probe(u) for u in a.probe]
    for r in rows:
        print("\n%s" % r["url"])
        if r["title"]:
            print("  title: %s" % r["title"][:90])
        for k, v in r["checks"].items():
            note = " (report only)" if k == "machine_readable" else ""
            print("  %-16s %s%s" % (k, "yes" if v else "no", note))
        print("  VERDICT: %s -- %s" % (r["verdict"], r["reason"]))

    tally = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    print("\n%s\nScout: %d probed -- %s" % ("=" * 78, len(rows),
          ", ".join("%d %s" % (n, v) for v, n in sorted(tally.items()))))
    if a.json:
        json.dump(ledger.envelope(rows, control=True),
                  open(a.json, "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    main()
