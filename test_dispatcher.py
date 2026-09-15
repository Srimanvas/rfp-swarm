"""One runnable check: the partition is disjoint and the fences are attached.

    python test_dispatcher.py
"""
import dispatcher


def test_registry_parses():
    s = dispatcher.load()
    assert len(s) >= 8, "expected the seeded registry, got %d rows" % len(s)
    assert {x["id"] for x in s} >= {"sam", "bidnet", "nyscr", "ungm", "issuers"}


def test_partition_is_disjoint():
    plan = dispatcher.assign(dispatcher.load())
    ids = [p["source"] for p in plan]
    assert len(ids) == len(set(ids)), "a source was assigned to two agents: %s" % ids


def test_double_assignment_raises():
    dup = [{"id": "sam", "lane": "federal", "adapter": None, "access": "script",
            "status": "active", "notes": ""}] * 2
    try:
        dispatcher.assign(dup)
    except ValueError:
        return
    raise AssertionError("assign() accepted a duplicated source")


def test_blocked_source_is_not_assigned():
    plan = dispatcher.assign(dispatcher.load())
    assert "linkedin" not in [p["source"] for p in plan],         "linkedin is status=blocked pending a Chrome permission grant"


def test_every_agent_carries_fences():
    for p in dispatcher.assign(dispatcher.load()):
        assert p["fences"], "%s has no fences" % p["agent"]
        assert any("BLOCKED" in f for f in p["fences"]), "%s lacks the escalation rule" % p["agent"]
        assert p["brief"] == "BRIEF.md", "%s must load the one-page brief, not RAMEDIA.md" % p["agent"]


def test_only_search_lane_may_websearch():
    for p in dispatcher.assign(dispatcher.load()):
        allowed = any("WebSearch allowed" in f for f in p["fences"])
        forbidden = any(f == "no WebSearch" for f in p["fences"])
        assert allowed or forbidden or p["lane"] in ("nonprofit", "discovery",
                                                     "nonprofit-commercial", "signal"),             "%s neither permits nor forbids WebSearch" % p["agent"]


def test_adapters_run_from_repo_root():
    """Adapters live in sources/ but import board/ledger from the root.

    py_compile does NOT catch this - it never executes imports - so a broken
    path shim would ship green and every sweep would die at runtime. Actually
    run each one."""
    import os, subprocess, sys
    root = os.path.dirname(os.path.abspath(__file__))
    for name in ("sam", "bidnet", "nyscr", "ungm", "issuers"):
        r = subprocess.run([sys.executable, os.path.join("sources", name + ".py"), "--help"],
                           cwd=root, capture_output=True, text=True)
        assert r.returncode == 0, "sources/%s.py fails from repo root:%s%s" % (name, os.linesep, r.stderr.strip())

def test_every_adapter_emits_the_same_envelope():
    """All five --json outputs must carry counts, not just results.

    Only sam.py did. A cloud run re-ran nyscr.py four times looking for a
    summary the JSON never contained - four full sweeps for one number."""
    import ledger, re, io as _io, os
    env = ledger.envelope([{"verdict": "REVIEW", "is_new": True},
                           {"verdict": "REJECT", "is_new": False}], control=True)
    assert set(env) >= {"generated_utc", "control_passed", "counts", "results"}
    assert env["counts"]["total"] == 2 and env["counts"]["new"] == 1
    assert env["counts"]["by_verdict"] == {"REVIEW": 1, "REJECT": 1}
    root = os.path.dirname(os.path.abspath(__file__))
    for name in ("nyscr", "bidnet", "ungm", "issuers"):
        src = _io.open(os.path.join(root, "sources", name + ".py"), encoding="utf-8").read()
        assert "ledger.envelope(" in src, "%s still writes a bare results dict" % name

if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok  " + name)
    print()
    print("all checks passed")
