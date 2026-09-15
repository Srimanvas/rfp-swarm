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
