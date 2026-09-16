#!/usr/bin/env python3
"""Harvest candidate issuer domains from Wikidata's official-website property.

Why this and not an agent reading directory pages:

- WebFetch summarises a page through a model, so link targets are dropped. Five
  directory fetches yielded zero domains in practice.
- Wikipedia list pages link to Wikipedia ARTICLES, not to the institutions' own
  sites, so scraping their external links yields nothing either.
- Affiliate directories (Catholic Charities, Feeding America, Goodwill, YMCA) are
  JS ZIP-code widgets, so there is nothing to scrape without a browser.
- That leaves an agent RECALLING domains, which is where invented and misspelled
  ones get in. Measured: 5 bad domains in the first 264.

Wikidata holds `official website` (P856) as structured data, so a domain that
comes out of here was published by the institution, not remembered. One query
returned 380 US art museums.

    python wikidata_harvest.py --out harvest.txt
    python wikidata_harvest.py --list

Feed the result to roster_add.py, which still DNS-checks everything.
Standard library only.
"""
import argparse
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request

ENDPOINT = "https://query.wikidata.org/sparql"
UA = "rfp-swarm roster builder (contact info@ramedia.dev)"
NEWLINE = chr(10)

# label -> Wikidata class. Anything that is an instance of the class, or of a
# subclass of it, located in the US, that publishes an official website.
# A wrong QID simply returns 0 rows, which is visible rather than silent.
CLASSES = [
    ("museums",            "Q33506"),
    ("nonprofits",         "Q163740"),
    ("foundations",        "Q157031"),
    ("zoos",               "Q43501"),
    ("aquariums",          "Q2281788"),
    ("botanical gardens",  "Q167346"),
    ("libraries",          "Q7075"),
    ("orchestras",         "Q42998"),
    ("opera companies",    "Q1268865"),
    ("theatres",           "Q1241025"),
    ("hospitals",          "Q16917"),
    ("radio stations",     "Q14350"),
    ("charities",          "Q708676"),
    ("research institutes", "Q31855"),
]

QUERY = """SELECT DISTINCT ?site WHERE {
  ?item wdt:P31/wdt:P279* wd:%s .
  ?item wdt:P17 wd:Q30 .
  ?item wdt:P856 ?site .
} LIMIT %d"""

DOMAIN = re.compile(r"^https?://(?:www\.)?([a-z0-9][a-z0-9.-]*\.[a-z]{2,})", re.I)

# Federal and state bodies duplicate SAM.gov and the state portals, which are
# already swept. The issuer lane exists for organisations that publish nowhere else.
SKIP = re.compile(r"\.(gov|mil)$|\.si\.edu$|\.state\.[a-z]{2}\.us$", re.I)


def run(qid, limit, timeout=120):
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": QUERY % (qid, limit)})
    req = urllib.request.Request(url, headers={
        "Accept": "application/sparql-results+json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def domains(payload):
    out = set()
    for row in payload["results"]["bindings"]:
        m = DOMAIN.match(row["site"]["value"].strip())
        if not m:
            continue
        d = m.group(1).lower().rstrip(".")
        if not SKIP.search(d):
            out.add(d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write the harvested domains here")
    ap.add_argument("--limit", type=int, default=1500, help="rows per class")
    ap.add_argument("--list", action="store_true", help="show the classes and exit")
    a = ap.parse_args()

    if a.list:
        for label, qid in CLASSES:
            print("  %-20s %s" % (label, qid))
        return 0

    lines, total, seen = [], 0, set()
    for label, qid in CLASSES:
        try:
            got = domains(run(qid, a.limit))
        except Exception as e:                      # one bad class must not kill the run
            print("  %-20s FAILED  %s" % (label, e), file=sys.stderr)
            continue
        fresh = sorted(got - seen)
        seen |= got
        total += len(fresh)
        print("  %-20s %4d domains (%d new)" % (label, len(got), len(fresh)))
        if fresh:
            lines.append("")
            lines.append("# wikidata %s" % label)
            lines.extend(fresh)
        time.sleep(1)                               # be polite to a free endpoint

    print("%d unique domains across %d classes" % (total, len(CLASSES)))
    if a.out:
        io.open(a.out, "w", encoding="utf-8", newline=NEWLINE).write(
            NEWLINE.join(lines) + NEWLINE)
        print("wrote %s" % a.out)
        print("next: python roster_add.py %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
