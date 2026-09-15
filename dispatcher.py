#!/usr/bin/env python3
"""Deterministic source -> agent partition.

This is the anti-duplication mechanism. It is code and not an agent on purpose:
assigning N sources to N agents is a partition, not a decision. An LLM router can
hallucinate an overlap; a partition cannot.

    python dispatcher.py              # human-readable assignment table
    python dispatcher.py --json       # machine-readable, for the coordinator

Standard library only.
"""
import argparse, io, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Fences by access type. The coordinator hands these to each agent verbatim.
# "unlimited agents in parallel to find sources and rfps" is uncapped in COUNT,
# never in cost per agent -- one badly-scoped agent outspends twenty disciplined ones.
FENCES = {
    "script":  ["run the adapter and report its output - do not browse",
                "no WebSearch", "no document retrieval"],
    "http":    ["plain fetch only - no browser, no WebSearch",
                "no document retrieval", "two failures then BLOCKED"],
    "search":  ["WebSearch allowed, budget %d queries - you are the ONLY agent permitted to call it" % 40,
                "proven phrasings only", "emit LEADS, never FINDS - a deadline must come from the issuer"],
    "browser": ["SINGLETON - never runs alongside another browser agent",
                "read-only: no messaging, no connection requests, no form submission",
                "human-paced"],
}

COMMON = [
    "return fixed-field records only - no prose, no narration, no raw HTML",
    "check BOARD-LEDGER.md before reporting anything as a fresh find",
    "never infer a fact the brief does not contain - emit BLOCKED instead",
    "two failed attempts then BLOCKED - no retry loops",
]

ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|"
                 r"\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$")


def load(path=None):
    """Parse the active rows of the SOURCES.md registry."""
    path = path or os.path.join(HERE, "SOURCES.md")
    out = []
    for line in io.open(path, encoding="utf-8"):
        m = ROW.match(line)
        if not m:
            continue
        sid, lane, adapter, access, status, notes = (g.strip() for g in m.groups())
        if sid in ("id", "---") or set(sid) <= set("-: "):
            continue
        if access not in FENCES:          # not a source row (e.g. the retired table)
            continue
        out.append({"id": sid, "lane": lane, "adapter": None if adapter == "-" else adapter,
                    "access": access, "status": status, "notes": notes})
    return out


def assign(sources):
    """One disjoint source per agent. Raises if the registry would double-assign."""
    active = [s for s in sources if s["status"] == "active"]
    seen = set()
    for s in active:
        if s["id"] in seen:
            raise ValueError("SOURCES.md assigns '%s' twice - partition is not disjoint" % s["id"])
        seen.add(s["id"])
    return [{"agent": "src:" + s["id"],
             "source": s["id"],
             "lane": s["lane"],
             "adapter": s["adapter"],
             "brief": "BRIEF.md",
             "fences": FENCES[s["access"]] + COMMON} for s in active]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sources", help="path to SOURCES.md")
    a = ap.parse_args()

    srcs = load(a.sources)
    plan = assign(srcs)
    blocked = [s for s in srcs if s["status"] == "blocked"]

    if a.json:
        json.dump({"assignments": plan, "blocked": blocked}, sys.stdout, indent=2)
        return

    print("%d active sources -> %d agents, one source each" % (len(plan), len(plan)))
    print("=" * 74)
    for p in plan:
        print("%-14s %-22s %s" % (p["agent"], p["lane"], p["adapter"] or "(agent-driven)"))
    for b in blocked:
        print()
        print("BLOCKED  %-10s %s" % (b["id"], b["notes"]))
    print()
    print("fences applied per agent: see dispatcher.FENCES + dispatcher.COMMON")


if __name__ == "__main__":
    main()
