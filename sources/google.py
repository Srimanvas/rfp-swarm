#!/usr/bin/env python3
"""Google lane - query GENERATOR, not a fetcher.

Generic search for live solicitations has failed every time it was tried here:
five attempts, zero traces, and result summaries that invented two deadlines which
nearly shipped as confirmed finds. Only two phrasings ever worked. So this script
does not search - it emits the exact, budgeted query list the agent is allowed to
run, and nothing else.

    python sources/google.py                 # the default budgeted query list
    python sources/google.py --budget 20     # fewer
    python sources/google.py --json q.json

Standard library only.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

# The only two phrasings with evidence behind them.
#   1. produced live nonprofit solicitations
#   2. the README's original sourcing lesson - issuers publish PDFs free
TEMPLATES = [
    '"request for proposals" "{term}" nonprofit "proposals are due" {month} {year}',
    'filetype:pdf "request for proposals" "{term}" {month} {year}',
]

# Terms we can actually deliver. Kept deliberately narrow: a broad term returns
# vendor listicles ("21 Best Nonprofit CRMs"), which is the documented failure mode.
TERMS = [
    "custom software development",
    "web application development",
    "website redesign",
    "content management system",
    "workflow automation",
    "data migration",
    "system integration",
    "case management system",
    "grants management system",
    "artificial intelligence",
]

DEFAULT_BUDGET = 40


def months(n=2):
    """This month and the next n-1 - solicitations close within weeks, not years."""
    out, d = [], datetime.now(timezone.utc)
    for _ in range(n):
        out.append((d.strftime("%B"), d.year))
        # jump past the end of the current month
        d = (d.replace(day=28) + timedelta(days=7)).replace(day=1)
    return out


def queries(budget=DEFAULT_BUDGET, terms=None, span=2):
    terms = terms or TERMS
    out = []
    for month, year in months(span):
        for term in terms:
            for tpl in TEMPLATES:
                if len(out) >= budget:
                    return out
                out.append(tpl.format(term=term, month=month, year=year))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="hard ceiling on queries (default %d)" % DEFAULT_BUDGET)
    ap.add_argument("--span", type=int, default=2, help="how many months forward")
    ap.add_argument("--json", help="write the query list here")
    a = ap.parse_args()

    if a.budget > DEFAULT_BUDGET:
        print("refusing budget %d: the ceiling is %d. Only this agent may call "
              "WebSearch, and the session allowance is shared."
              % (a.budget, DEFAULT_BUDGET), file=sys.stderr)
        return 2

    qs = queries(a.budget, span=a.span)
    print("%d queries (budget %d)" % (len(qs), a.budget))
    print("=" * 74)
    for q in qs:
        print(q)
    print()
    print("RULES FOR THE AGENT RUNNING THESE:")
    print("  - every hit is a LEAD, never a FIND")
    print("  - a deadline must come from the issuer's own page or the document body")
    print("  - never report a date taken from a search-result summary")
    print("  - no other agent may call WebSearch")

    if a.json:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import ledger
        rows = [{"query": q, "verdict": "LEAD-QUERY", "is_new": True} for q in qs]
        json.dump(ledger.envelope(rows, control=True, budget=a.budget),
                  open(a.json, "w", encoding="utf-8"), indent=2)
        print("\nwrote %s" % a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
