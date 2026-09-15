"""Shared seen-ledger handling for the multi-source sweep.

One flat JSON dict, keys namespaced by source so three sweeps can share a file:

    {"bidnet:444133683448": {"first_seen": "...", "title": "...", "verdict": "..."},
     "nyscr:2138075":       {...},
     "830158a1...":         {...}}          <- sweep.py's SAM ids stay bare

Metadata keys start with "_" and are ignored. Loading accepts both the flat shape
and the older {"notices": {...}} wrapper, same as sweep.py.
"""
import json


def load(path):
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return {}
    if not isinstance(d, dict):
        return {}
    if isinstance(d.get("notices"), dict):
        d = d["notices"]
    return {k: v for k, v in d.items() if not k.startswith("_")}


def key(source, ident):
    return "%s:%s" % (source, ident)


def mark(rows, seen, source, id_field):
    """Set is_new on each row against the ledger. Returns the rows."""
    for r in rows:
        r["is_new"] = key(source, r.get(id_field, "")) not in seen
    return rows


def envelope(rows, control=None, **extra):
    """Uniform --json envelope for every adapter.

    sam.py already emitted counts; the other four emitted bare {"results": rows}.
    A cloud run then re-ran nyscr.py FOUR TIMES hunting for a summary it could not
    find in the JSON - four full 599-ad sweeps, one of which hit a network error.
    Same shape everywhere means one run is enough."""
    from datetime import datetime, timezone
    verdicts = {}
    for r in rows:
        v = r.get("verdict", "UNKNOWN")
        verdicts[v] = verdicts.get(v, 0) + 1
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(),
           "control_passed": control,
           "counts": {"total": len(rows),
                      "new": sum(1 for r in rows if r.get("is_new", True)),
                      "by_verdict": verdicts},
           "results": rows}
    out.update(extra)
    return out
