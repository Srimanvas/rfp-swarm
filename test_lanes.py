"""Checks for the agent-driven lanes' deterministic halves.

    python test_lanes.py

The judgment half of each lane lives in LANES.md and is the agent's job. What is
testable is the part that must NOT drift: the search budget, and the issuer-type
classifier that encodes a decision the user actually made.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "sources"))


# --- google lane -----------------------------------------------------------

def test_query_budget_is_enforced():
    import google
    assert len(google.queries(budget=7)) == 7
    assert len(google.queries()) <= google.DEFAULT_BUDGET


def test_cannot_raise_the_budget_from_the_command_line():
    """The WebSearch allowance is shared and this is the only lane that may spend
    it. A lane that can talk itself into a bigger budget is not a fence."""
    r = subprocess.run([sys.executable, os.path.join("sources", "google.py"),
                        "--budget", "500"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode != 0, "google.py accepted a budget above its ceiling"
    assert "refusing budget" in r.stderr


def test_only_proven_phrasings_are_emitted():
    """Generic '<system> RFP 2026' queries returned vendor listicles and invented
    deadlines. Only the two phrasings with evidence behind them are allowed."""
    import google
    for q in google.queries():
        assert '"request for proposals"' in q, "unproven phrasing: %s" % q
        assert any(str(y) in q for y in (2025, 2026, 2027, 2028)), \
            "query without a year will pull closed solicitations: %s" % q


# --- web lane --------------------------------------------------------------

def _row(title, issuer=""):
    return {"title": title, "issuer": issuer}


def test_public_sector_issuers_are_out_of_the_web_lane():
    import web
    for issuer in ("City of Hartford", "Hennepin County", "State of Oregon",
                   "Springfield School District", "Rutgers University",
                   "Port Authority of NY & NJ"):
        keep, why = web.classify(_row("Website Redesign Services", issuer))
        assert keep is False, "%s should be out of this lane, got %r (%s)" % (issuer, keep, why)


def test_nonprofit_and_commercial_issuers_are_in():
    import web
    for issuer in ("Meridian International Center Foundation",
                   "National Association of Counties Foundation",
                   "Acme Industries Inc.", "Sepsis Alliance"):
        keep, why = web.classify(_row("Website Redesign and CMS Migration", issuer))
        assert keep is True, "%s should be in this lane, got %r (%s)" % (issuer, keep, why)


def test_unknown_issuer_is_blocked_never_guessed():
    """The user's rule: do not infer. An unclassifiable issuer is a question."""
    import web
    keep, why = web.classify(_row("Website Redesign", ""))
    assert keep is None, "expected BLOCKED for an unstated issuer, got %r" % keep
    assert "BLOCKED" in why


def test_non_website_scope_is_rejected():
    import web
    keep, _ = web.classify(_row("Sludge Dewatering Centrifuge Replacement",
                                "Acme Industries Inc."))
    assert keep is False


def test_web_lane_screens_files_rather_than_resweeping():
    """It consumes other adapters' JSON. Re-fetching the same universe to apply a
    different filter is wasted budget."""
    import web
    src = open(os.path.join(ROOT, "sources", "web.py"), encoding="utf-8").read()
    assert "urllib" not in src, "web.py should screen existing rows, not fetch"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok  " + name)
    print()
    print("all lane checks passed")
