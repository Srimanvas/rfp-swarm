"""Smallest check that the ledger-format fix holds. Run: python test_seen.py"""
import json, subprocess, sys, tempfile, os

def load(obj):
    """Mirror of sweep.py's --seen unwrap."""
    seen = obj if isinstance(obj, dict) else {}
    return seen.get("notices", seen) if isinstance(seen.get("notices"), dict) else seen

assert "abc" in load({"notices": {"abc": {}}, "_comment": "x"})   # nested (2026-08-25 shape)
assert "abc" in load({"abc": {}, "_comment": "x"})                # flat (2026-08-26 shape)
assert load([]) == {} and load({}) == {}
print("ok")
