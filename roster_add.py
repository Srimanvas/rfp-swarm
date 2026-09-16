#!/usr/bin/env python3
"""Merge harvested domain lists into sources/issuers.txt.

The roster is the whole asset of the issuer lane, so this guards it.

Domains arrive from harvesting agents, and some of those are RECALLED rather than
read off a fetched page - which is exactly where an invented or misspelled domain
gets in. A domain that does not exist is not harmless: `discover()` tries every
path in PATHS against it, so one dead entry burns fifteen failed lookups on every
run, forever.

So every candidate must resolve in DNS before it earns a line. That check is
cheap (no HTTP, just getaddrinfo) and it separates "invented domain" from "real
domain with no RFP page" - only the second is worth keeping.

    python roster_add.py harvested1.txt harvested2.txt
    python roster_add.py *.txt --dry-run

Nothing is ever removed from the roster: this only ever appends.
"""
import argparse
import concurrent.futures as cf
import io
import os
import re
import socket
import sys

NEWLINE = chr(10)
ROSTER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "sources", "issuers.txt")

# strip scheme, www., any path, port, and surrounding punctuation
CLEAN = re.compile(r"^(?:https?://)?(?:www\.)?([a-z0-9][a-z0-9.-]*\.[a-z]{2,})", re.I)


def normalise(line):
    line = line.strip().strip(",;'\"")
    if not line or line.startswith("#"):
        return None
    m = CLEAN.match(line.split()[0].lower())
    return m.group(1).rstrip(".") if m else None


def read_candidates(paths):
    """Returns [(domain, cluster_label)] preserving the order seen."""
    out, cluster = [], "unlabelled"
    for p in paths:
        for raw in io.open(p, encoding="utf-8"):
            s = raw.strip()
            if s.startswith("#"):
                cluster = s.lstrip("# ").strip() or cluster
                continue
            d = normalise(s)
            if d:
                out.append((d, cluster))
    return out


def resolves(domain):
    try:
        socket.getaddrinfo(domain, 443, proto=socket.IPPROTO_TCP)
        return True
    except OSError:
        return False


def existing():
    if not os.path.exists(ROSTER):
        return set(), []
    lines = [l.rstrip(NEWLINE) for l in io.open(ROSTER, encoding="utf-8")]
    have = set()
    for l in lines:
        s = l.strip()
        if s and not s.startswith("#"):
            have.add(s.split("\t")[0].lower())
    return have, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="harvested domain lists")
    ap.add_argument("--jobs", type=int, default=32, help="parallel DNS lookups")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    have, lines = existing()
    cands = read_candidates(a.files)

    seen, fresh = set(), []
    for d, cluster in cands:
        if d in have or d in seen:
            continue
        seen.add(d)
        fresh.append((d, cluster))

    print("%d candidates read, %d already on the roster or duplicated, %d to check"
          % (len(cands), len(cands) - len(fresh), len(fresh)))

    with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        ok = list(ex.map(lambda t: resolves(t[0]), fresh))

    live = [t for t, good in zip(fresh, ok) if good]
    dead = [t for t, good in zip(fresh, ok) if not good]

    print("%d resolve, %d do not" % (len(live), len(dead)))
    if dead:
        print("\nnot added - these do not resolve (misspelled or invented):")
        for d, _ in dead:
            print("  %s" % d)

    if a.dry_run:
        print("\n--dry-run: roster unchanged")
        return 0

    by_cluster = {}
    for d, c in live:
        by_cluster.setdefault(c, []).append(d)

    add = []
    for cluster, domains in by_cluster.items():
        add.append("")
        add.append("# %s" % cluster)
        add.extend(sorted(domains))

    with io.open(ROSTER, "a", encoding="utf-8", newline=NEWLINE) as fh:
        fh.write(NEWLINE.join(add) + NEWLINE)

    print("\nappended %d domains in %d clusters to %s"
          % (len(live), len(by_cluster), ROSTER))
    print("roster was %d lines, now %d" % (len(lines), len(lines) + len(add)))
    print("next: python sources/issuers.py --discover --jobs 12")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
