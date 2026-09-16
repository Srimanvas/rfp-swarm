#!/usr/bin/env python3
"""Web lane - website/CMS scope, nonprofit and commercial issuers only.

User decision 2026-09-15: this lane filters on ISSUER TYPE, not on the reference
requirement. In: nonprofits, foundations, associations, commercial. Out: cities,
counties, states, federal, school districts, universities.

That restriction applies to THIS LANE ONLY. Every other source keeps sweeping
government freely, screened by the reference gate in RULES.md.

It screens rows the other adapters already pulled rather than sweeping again -
re-fetching the same universe to apply a different filter is wasted budget.

    python sources/web.py out-bidnet.json out-nyscr.json --json out-web.json
    python sources/web.py out-*.json --all

Standard library only.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ledger

# Scope: is this website / CMS work at all?
SCOPE = re.compile(
    r"\b(web ?site|web ?page|web ?design|web ?development|webdev|"
    r"content management|\bcms\b|drupal|wordpress|joomla|sitecore|contentful|"
    r"sanity|headless|redesign|re-?design|web ?portal|intranet|"
    r"information architecture|ux|user experience|accessibility remediation)\b", re.I)

# Issuer type. Any of these means PUBLIC SECTOR or EDUCATION -> out of this lane.
PUBLIC = re.compile(
    r"\b(city of|town of|village of|county|borough|parish|municipal|"
    r"state of|commonwealth|department of|dept\.? of|federal|"
    r"school district|unified school|board of education|\bisd\b|\busd\b|"
    r"university|college|campus|\bsuny\b|\bcuny\b|community college|"
    r"authority|transit|housing authority|port authority|"
    r"public works|sheriff|police|fire district|water district|"
    r"\bdoe\b|\bdot\b|\bdhs\b|\bhhs\b|\bva\b medical)\b", re.I)

# Positive markers for the issuers this lane WANTS.
PRIVATE = re.compile(
    r"\b(foundation|nonprofit|non-profit|not-for-profit|501\s*\(?c\)?|"
    r"association|society|institute|council|coalition|alliance|trust|"
    r"charit|philanthrop|\binc\.?\b|\bllc\b|\bltd\b|corporation|company)\b", re.I)


def issuer_of(row):
    for k in ("issuer", "agency", "organization", "org", "buyer", "location"):
        if row.get(k):
            return str(row[k])
    return ""


def classify(row):
    """Return (in_lane, reason)."""
    blob = "%s %s" % (row.get("title") or "", issuer_of(row))
    if not SCOPE.search(blob):
        return False, "not website/CMS scope"
    hit = PUBLIC.search(blob)
    if hit:
        return False, "public-sector or education issuer: '%s'" % hit.group(0)
    if PRIVATE.search(blob):
        return True, "website scope, private/nonprofit issuer"
    # Nothing either way. Do NOT guess - that is the whole point of BLOCKED.
    return None, "issuer type not stated - BLOCKED, do not infer"


def load(paths):
    rows = []
    for p in paths:
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            print("skip %s: %s" % (p, e), file=sys.stderr)
            continue
        for r in d.get("results", d if isinstance(d, list) else []):
            r.setdefault("_src", os.path.basename(p))
            rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="adapter --json outputs to screen")
    ap.add_argument("--json", help="write results here")
    ap.add_argument("--all", action="store_true", help="print rejects too")
    a = ap.parse_args()

    rows = load(a.inputs)
    out = []
    for r in rows:
        keep, why = classify(r)
        r["verdict"] = {True: "REVIEW", False: "REJECT", None: "BLOCKED"}[keep]
        r["reason"] = why
        out.append(r)

    n = {v: sum(1 for r in out if r["verdict"] == v)
         for v in ("REVIEW", "BLOCKED", "REJECT")}
    print("web lane: %d rows screened -> %d REVIEW, %d BLOCKED, %d REJECT"
          % (len(out), n["REVIEW"], n["BLOCKED"], n["REJECT"]))
    print("=" * 74)
    for r in out:
        if r["verdict"] == "REJECT" and not a.all:
            continue
        print("\n[%s] %s" % (r["verdict"], r.get("title") or "(no title)"))
        print("  %s | %s" % (issuer_of(r) or "(issuer not stated)", r["reason"]))
        if r.get("url"):
            print("  %s" % r["url"])
    if n["BLOCKED"]:
        print("\n%d rows could not be classified from the text available." % n["BLOCKED"])
        print("They are BLOCKED, not guessed. Resolve the issuer, then re-run.")

    if a.json:
        json.dump(ledger.envelope(out, control=True),
                  open(a.json, "w", encoding="utf-8"), indent=2)
        print("\nwrote %s" % a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
