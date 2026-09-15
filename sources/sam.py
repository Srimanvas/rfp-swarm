#!/usr/bin/env python3
"""
Weekly sourcing sweep for awardable software / AI solicitations.

Standard library only - no pip install, works in a bare cloud sandbox.

Design notes that matter:
  * SAM's search API SILENTLY IGNORES parameters it does not recognise, and
    repeated parameters do NOT OR together. Both were verified 2026-08-25.
    So: one code per query, one notice_type per query, everything else
    filtered client-side. run_control() proves a filter actually bit.
  * Screen on classification codes, not titles. Titles lie in both directions.

Usage:
    python sweep.py                 # sweep, print report to stdout
    python sweep.py --json out.json # also write machine-readable results
    python sweep.py --seen seen.json  # dedupe against a prior ledger
"""

import argparse
import os as _os, sys as _sys
# sources/ adapters import board/ledger from the repo root, which is not on
# sys.path when run as `python sources/<name>.py`. Put the root on the path.
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import board
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
SEARCH = "https://sam.gov/api/prod/sgs/v1/search/"
OPP_V2 = "https://sam.gov/api/prod/opps/v2/opportunities/"
RESOURCES = "https://sam.gov/api/prod/opps/v3/opportunities/{}/resources"

# --- what we screen on -------------------------------------------------------

# NAICS 541511 is the build code. It is the single highest-signal filter we have.
CODES = [
    ("naics", "541511", "Custom Computer Programming Services"),
    ("naics", "541512", "Computer Systems Design Services"),
    ("naics", "541519", "Other Computer Related Services"),
    ("naics", "518210", "Data Processing, Hosting and Related Services"),
    ("psc", "DA01", "IT & Telecom - Application Development Support"),
    ("psc", "DA10", "IT & Telecom - Business Application/Application Development"),
    ("psc", "7A20", "Application Development Software"),
]

# Awardable only. 'r' = Sources Sought, 'p' = Presolicitation -> excluded by design.
AWARDABLE_TYPES = ["o", "k"]

# Set-aside codes we cannot hold. Measured 2026-08-25: these lock only ~8% of
# the pool, so this filter is cheap insurance, not a strategic constraint.
BLOCKED_SETASIDES = {
    "SDVOSBC", "SDVOSBS", "WOSB", "EDWOSB", "8A", "8AN", "HZC",
    "VSA", "VSS", "ISBEE", "IEE",
}

# Titles that are never a build.
NOISE = re.compile(
    r"\b(renew\w*|licen[cs]e\w*|subscription|maintenance renewal|brand name"
    r"|sole.?source|intent to (award|sole)|notice of intent)\b", re.I)

# Scope language that means "we are buying a product, not commissioning a build".
PRODUCT_MANDATE = re.compile(
    r"\b(software as a service|saas\b|low.?code|off.?the.?shelf|cots\b"
    r"|use this product|commercially available|licen[cs]e the platform)\b", re.I)

# Positive signals - the CDC VAERS shape.
FIT_SIGNALS = [
    (re.compile(r"\b(branching|conditional) logic\b", re.I), 3, "branching logic"),
    (re.compile(r"\bintake\b", re.I), 2, "intake"),
    (re.compile(r"\beligibilit(y|ies)\b", re.I), 2, "eligibility rules"),
    (re.compile(r"\bworkflow automation\b", re.I), 2, "workflow automation"),
    (re.compile(r"\b(human.centered|user experience|ux)\b", re.I), 2, "UX design"),
    (re.compile(r"\b(validation|data quality)\b", re.I), 1, "validation"),
    (re.compile(r"\b(portal|self.service)\b", re.I), 1, "portal"),
    (re.compile(r"\b(ocr|intelligent document|document intake)\b", re.I), 2, "document intake"),
    (re.compile(r"\b(artificial intelligence|machine learning|\bai\b|llm)\b", re.I), 2, "AI/ML"),
    (re.compile(r"\bapi\b|\bintegration\b", re.I), 1, "integration"),
    (re.compile(r"\bfirm.fixed.price\b", re.I), 1, "fixed price"),
    (re.compile(r"\bmodernization\b", re.I), 1, "modernization"),
]

# Phase 0 fix 1 (user-approved 2026-09-15). Was 10, which hard-rejected 71
# genuinely-open notices on 2026-08-31. Federal simplified-acquisition RFQs post
# with 5-10 day windows by design, and the board already contradicted the rule:
# Meridian was screened GO on a ~5-day runway.
MIN_LEAD_DAYS = 3           # below this it is genuinely not biddable
SHORT_FUSE_DAYS = 10        # 3-9 days: biddable, but flagged so it gets decided fast
LOOKAHEAD_LIMIT_DAYS = 400  # ignore multi-year open BAAs / on-ramps


def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*",
                                        "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def search(kind, code, notice_type, size=100):
    qs = urllib.parse.urlencode({
        "index": "opp", "is_active": "true", "page": 0, "size": size,
        kind: code, "notice_type": notice_type, "sort": "-modifiedDate",
    })
    try:
        return fetch(SEARCH + "?" + qs).get("_embedded", {}).get("results", [])
    except Exception as e:
        print("  ! query failed %s=%s type=%s: %s" % (kind, code, notice_type, e), file=sys.stderr)
        return []


def run_control():
    """Prove notice_type actually filters. SAM ignores params it does not know,
    so an unverified filter is an unsafe filter."""
    try:
        qs_all = urllib.parse.urlencode({"index": "opp", "is_active": "true",
                                         "page": 0, "size": 1, "naics": "541511"})
        qs_o = qs_all + "&notice_type=o"
        total_all = fetch(SEARCH + "?" + qs_all).get("page", {}).get("totalElements")
        total_o = fetch(SEARCH + "?" + qs_o).get("page", {}).get("totalElements")
        ok = isinstance(total_all, int) and isinstance(total_o, int) and total_o < total_all
        print("control: naics=541511 -> %s ; +notice_type=o -> %s ; filter bit: %s"
              % (total_all, total_o, "YES" if ok else "NO -- RESULTS UNTRUSTWORTHY"))
        return ok
    except Exception as e:
        print("control check failed: %s" % e, file=sys.stderr)
        return False


def text_of(rec):
    parts = [rec.get("title") or ""]
    for d in (rec.get("descriptions") or []):
        parts.append(re.sub(r"<[^>]+>", " ", d.get("content") or ""))
    return re.sub(r"\s+", " ", " ".join(parts))


def normalise(rec, code_label):
    org = rec.get("organizationHierarchy") or []
    setaside = ((rec.get("solicitation") or {}).get("setAside") or {}).get("code")
    deadlines = (rec.get("solicitation") or {}).get("deadlines") or {}
    return {
        "id": rec.get("_id"),
        "solicitation_number": rec.get("solicitationNumber"),
        "title": rec.get("title") or "",
        "type": (rec.get("type") or {}).get("value"),
        "type_code": (rec.get("type") or {}).get("code"),
        "agency": org[0].get("name") if org else None,
        "office": org[-1].get("name") if len(org) > 1 else None,
        "set_aside": setaside,
        "naics": [n.get("code") for n in (rec.get("naics") or [])],
        "matched_code": code_label,
        # NOTE: responseDate from the search API is UTC. Reading it as local
        # cost us four hours of assumed runway on the CDC RFQ.
        "response_utc": rec.get("responseDate"),
        "deadline_local": deadlines.get("response"),
        "url": "https://sam.gov/opp/%s/view" % rec.get("_id"),
        "text": text_of(rec)[:4000],
    }



def enrich(rec):
    """Search results carry truncated descriptions, which starves the fit score.
    Pull the full record for survivors only - and take the deadline from
    deadlines.response, which carries a UTC OFFSET rather than bare UTC."""
    try:
        d = fetch(OPP_V2 + rec["id"])
    except Exception:
        return rec
    d2 = d.get("data2", d) or {}
    # NOTE: the v2 endpoint does NOT carry the description (verified 2026-08-25);
    # the search API's `descriptions` field is the only source. We call v2 purely
    # for deadlines.response, which carries a UTC OFFSET rather than bare UTC.
    sol = d2.get("solicitation") or {}
    dl = (sol.get("deadlines") or {}).get("response")
    if dl:
        rec["deadline_local"] = dl
    return rec

def days_out(rec, now):
    raw = rec.get("response_utc")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (dt - now).days
    except Exception:
        return None


def screen(rec, now):
    """Return (verdict, reasons, score). Stage 1 + stage 2 of the pipeline."""
    reasons = []
    if rec["type_code"] not in AWARDABLE_TYPES:
        return "REJECT", ["not an awardable notice type"], 0
    if (rec["set_aside"] or "").upper() in BLOCKED_SETASIDES:
        return "REJECT", ["set-aside we cannot hold: %s" % rec["set_aside"]], 0
    if NOISE.search(rec["title"]):
        return "REJECT", ["title is a renewal / licence / sole-source notice"], 0

    d = days_out(rec, now)
    if d is None:
        return "REJECT", ["no response date"], 0
    # Phase 0 fix 2: SAM keeps notices is_active ~15 days past close, so 64% of
    # the "active" universe is dead. Expired gets its own bucket or the live count
    # is meaningless.
    if d < 0:
        return "EXPIRED", ["closed %d days ago (SAM still lists it active)" % -d], 0
    if d < MIN_LEAD_DAYS:
        return "REJECT", ["closes in %d days - below the %d-day floor" % (d, MIN_LEAD_DAYS)], 0
    if d > LOOKAHEAD_LIMIT_DAYS:
        return "REJECT", ["closes in %d days - open BAA / on-ramp, not a project" % d], 0

    blob = rec["text"]

    # SAM's own notice-type label is not reliable: SSA 28321326RI0000041 is
    # typed "Solicitation" but opens "This Request for Information is for...".
    if re.search(r"this (is a |document is a )?request for information"
                 r"|this rfi|market (survey|research) (exercise|only)"
                 r"|is not a solicitation", blob, re.I):
        return "REJECT", ["describes itself as an RFI / market survey despite its notice type"], 0

    # Stage 2 kill patterns. These are flags, not auto-rejects: each one cost a
    # full manual trace to learn, and each needs a human to confirm from the
    # solicitation document itself.
    if PRODUCT_MANDATE.search(blob):
        reasons.append("FLAG: product-mandate language in scope - likely a buy, not a build")
    if re.search(r"501\(c\)\(3\)|not.for.profit organization|nonprofit organization", blob, re.I):
        reasons.append("FLAG: entity-type eligibility - check we are not excluded as a for-profit")
    if re.search(r"fedramp", blob, re.I):
        reasons.append("FLAG: FedRAMP mentioned - determine WHO carries it "
                       "(agency-held costs us nothing; vendor-held is a wall)")
    if re.search(r"certificate of insurance", blob, re.I):
        reasons.append("FLAG: certificate of insurance - check if required AT SUBMISSION vs at award")
    if re.search(r"(government|public sector|municipal|state agency)[^.]{0,60}"
                 r"(experience|references?) (is |are )?(required|mandatory)", blob, re.I):
        reasons.append("FLAG: possible mandatory public-sector reference gate")

    score = 0
    hits = []
    for pat, weight, label in FIT_SIGNALS:
        if pat.search(blob):
            score += weight
            hits.append(label)
    if rec["matched_code"].startswith("541511"):
        score += 3
        hits.append("NAICS 541511 build code")

    # Deliberately NOT gating on score. Many notices carry only "see attached",
    # so a low score means "thin description", not "poor fit". The machine's job
    # is to cut ~291 down to ~18; a human reads those 18. Score is ranking only.
    verdict = "REVIEW"
    reasons.append("fit signals (%d): %s" % (score, ", ".join(hits) or "none"))
    reasons.append("closes in %d days" % d)
    return verdict, reasons, score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write full results as JSON to this path")
    ap.add_argument("--seen", help="path to a seen-ledger JSON to dedupe against")
    ap.add_argument("--all", action="store_true", help="include WEAK and REJECT in the report")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    print("SOURCING SWEEP  %s UTC" % now.strftime("%Y-%m-%d %H:%M"))
    print("=" * 78)
    trusted = run_control()
    print()

    seen = {}
    if args.seen:
        try:
            with open(args.seen, "r", encoding="utf-8") as fh:
                seen = json.load(fh)
        except Exception:
            seen = {}
    if not isinstance(seen, dict):
        seen = {}
    # ledger ids may sit at the top level or nested under "notices" - accept both
    seen = seen.get("notices", seen) if isinstance(seen.get("notices"), dict) else seen

    found = {}
    for kind, code, label in CODES:
        for t in AWARDABLE_TYPES:
            for rec in search(kind, code, t):
                if (rec.get("type") or {}).get("code") != t:
                    continue          # SAM sometimes returns unfiltered rows
                rid = rec.get("_id")
                if not rid or rid in found:
                    continue
                found[rid] = normalise(rec, "%s %s" % (code, label))

    print("raw unique awardable notices: %d" % len(found))

    # Cheap pre-filter first so we only pay for enrichment on survivors.
    prelim = []
    for rid, rec in found.items():
        d = days_out(rec, now)
        if rec["type_code"] not in AWARDABLE_TYPES: continue
        if (rec["set_aside"] or "").upper() in BLOCKED_SETASIDES: continue
        if NOISE.search(rec["title"]): continue
        if d is None or d < MIN_LEAD_DAYS or d > LOOKAHEAD_LIMIT_DAYS: continue  # expired (d<0) excluded here too
        prelim.append(rid)
    print("passing stage-1 filters: %d  (enriching each with its full description)" % len(prelim))
    for rid in prelim:
        found[rid] = enrich(found[rid])

    results = []
    for rid, rec in found.items():
        verdict, reasons, score = screen(rec, now)
        rec.update(verdict=verdict, reasons=reasons, score=score,
                   is_new=rid not in seen)
        results.append(rec)

    board.mark(results, board.load())
    results.sort(key=lambda r: (-r["score"], str(r.get("response_utc"))))
    review = [r for r in results if r["verdict"] == "REVIEW"]
    new_review = [r for r in review if r["is_new"]]

    print("after screen: %d REVIEW (%d new), %d WEAK, %d REJECT"
          % (len(review), len(new_review),
             sum(1 for r in results if r["verdict"] == "WEAK"),
             sum(1 for r in results if r["verdict"] == "REJECT")))
    if not trusted:
        print("\n*** CONTROL CHECK FAILED - treat this run as unverified ***")
    print()

    show = results if args.all else review
    for r in show:
        flag = "NEW" if r["is_new"] else "   "
        print("-" * 78)
        print("%s [%s score %d] %s" % (flag, r["verdict"], r["score"], r["title"]))
        print("    %s | %s | set-aside %s" % (r["agency"], r["solicitation_number"], r["set_aside"]))
        print("    closes %s (UTC) | %s" % (r["response_utc"], r["matched_code"]))
        print("    %s" % r["url"])
        if r.get("board_dup"):
            d = r["board_dup"]
            print("    ^^ ALREADY ON BOARD: %s | %s | %s"
                  % (d["title"], d["status"], d["folder"]))
        for reason in r["reasons"]:
            print("      - %s" % reason)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"generated_utc": now.isoformat(),
                       "control_passed": trusted,
                       "counts": {"raw": len(found), "review": len(review),
                                  "new_review": len(new_review)},
                       "results": results}, fh, indent=2)
        print("\nwrote %s" % args.json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
