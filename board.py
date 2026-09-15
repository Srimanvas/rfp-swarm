#!/usr/bin/env python3
"""
Board ledger - what the folder board already holds, as one flat .md file.

The seen-notices JSON only knows what previous *sweeps* saw. Anything foldered
before the sweep automation existed is invisible to it, which is how UTSA VIED
got re-reported as a fresh GO on 2026-08-28 after sitting on the board since
2026-08-07. This file closes that gap.

Built locally from the folder board, committed to the repo, read by the cloud
sweep - which has no access to the local board at all.

Usage:
    python board.py --build                  # regenerate BOARD-LEDGER.md
    python board.py --check "some rfp title" # what would this collide with?
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "BOARD-LEDGER.md")

# The board lives outside this repo and only exists on the local machine.
BOARD_ROOTS = [
    r"C:\Dev\Code Repo\FJC\RFP\RFP Mart",
    r"C:\Dev\Code Repo\FJC\RFP\_focus-nonprofit-software",
    r"C:\Dev\Code Repo\FJC\RFP\_screens",
]

# Words that carry no identifying signal in this domain. Without these stripped,
# every municipal website redesign matches every other one.
STOP = set("""
a an and are as at be by for from in into is it its of on or the to with
rfp rfq rfi sow itb ifb solicitation proposal proposals bid bids notice
website websites web site sites redesign redevelopment rebuild refresh
development develop developing design designing services service
system systems software solution solutions platform platforms portal portals
application applications app tool tools suite
hosting hosted host maintenance support managed
migration migrate migrating implementation implement
management managing modernization modernize modernizing
infrastructure enterprise program project projects related associated
professional consulting consultant technical technology
new state county city town village district authority department office
inc llc corp company firm group global
due closed closes closing open under review pending
go nogo viable non nonviable questions submitted duplicate stub folder use see
""".split())

TOKEN = re.compile(r"[a-z0-9]+")
DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+")
STATUS_DIRS = {"GO", "GO-WITH-FIXES", "NO-GO"}


def tokens(text):
    """Significant tokens: lowercase words, stopwords and 1-3 char noise gone."""
    out = set()
    for t in TOKEN.findall(text.lower()):
        if t in STOP or len(t) < 4 or t.isdigit():
            continue
        out.add(t)
    return out


def _h1(folder):
    """First markdown H1 inside the folder - a far better title than the slug."""
    for name in ("00-brief.md", "ORIGINAL-RFP-SOURCE.md", "VERDICT.md", "research.md"):
        p = os.path.join(folder, name)
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.startswith("# "):
                        return line[2:].strip()
        except OSError:
            pass
    return ""


def _status(path, name):
    for part in path.split(os.sep):
        if part in STATUS_DIRS:
            return part
    # Suffix conventions: "...-Non-viable - nonprofits only", "...-GO"
    low = name.lower()
    for marker in ("non-viable", "not viable", "questions submitted",
                   "under review", "pending", "duplicate", "submitted"):
        if marker in low:
            return marker.upper()
    return "-"


# Manual-era slug: "22-tx-utsa-vied-...". Case-sensitive on purpose - without
# that, the category container "1-Software-Platforms" matches and the whole
# lane gets pruned out of the ledger.
SLUG = re.compile(r"^\d{1,2}-[a-z]{2}-[a-z]")


def is_bid_folder(parent, name, roots):
    """A bid folder, not a category container or an attachment subfolder."""
    if DATE.match(name) or SLUG.match(name):
        return True
    return os.path.basename(parent) in STATUS_DIRS


def scan(roots):
    """Every bid folder on the board, deepest-named first."""
    rows = []
    for root in roots:
        if not os.path.isdir(root):
            print("skip (not on this machine): %s" % root, file=sys.stderr)
            continue
        for dirpath, dirnames, _ in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != "documents"]
            keep = []
            for d in dirnames:
                if d in STATUS_DIRS or d.startswith(("_", ".")):
                    keep.append(d)
                    continue
                full = os.path.join(dirpath, d)
                if not is_bid_folder(dirpath, d, roots):
                    keep.append(d)          # a container - walk into it
                    continue
                # A bid folder is one that holds files, not just other folders.
                if not any(os.path.isfile(os.path.join(full, f))
                           for f in os.listdir(full)):
                    continue
                # Do NOT descend: its attachment subfolders are not bids.
                m = DATE.match(d)
                deadline = m.group(1) if m else ""
                if not deadline:
                    m2 = re.search(r"due-([a-z]{3})(\d{1,2})", d, re.I)
                    if m2:
                        deadline = "~%s %s" % (m2.group(1).title(), m2.group(2))
                title = _h1(full) or re.sub(r"[-_]+", " ", DATE.sub("", d)).strip()
                rel = os.path.relpath(full, os.path.dirname(root))
                rows.append({
                    "key": " ".join(sorted(tokens(d + " " + title))),
                    "title": title[:110],
                    "deadline": deadline or "-",
                    "status": _status(full, d),
                    "folder": rel.replace(os.sep, "/"),
                })
            dirnames[:] = keep
    rows.sort(key=lambda r: (r["deadline"], r["title"]))
    return rows


SCREEN_VERDICTS = ("GO", "CAUTION", "NON-VIABLE")


def scan_screens(roots):
    """Verdicts from past SCREEN-*.md files.

    CAUTION and NON-VIABLE items never become folders, so without this they get
    re-screened every single day - the Ohio juvenile CMS was judged twice in two
    days and would have been judged again tomorrow.
    """
    rows, verdict = [], "-"
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for f in sorted(files):
                if not (f.startswith("SCREEN-") and f.endswith(".md")):
                    continue
                path = os.path.join(dirpath, f)
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as fh:
                        for line in fh:
                            s = line.strip().lstrip("\\").strip()
                            if s.startswith("#"):
                                head = s.lstrip("#").strip().upper()
                                for v in SCREEN_VERDICTS:
                                    if head.startswith(v):
                                        verdict = v
                                        break
                                continue
                            if not s.startswith("|") or set(s) <= set("|- "):
                                continue
                            p = [c.strip() for c in s.strip("|").split("|")]
                            if len(p) < 4 or p[0].lower() in ("item", "bid", ""):
                                continue
                            title = p[0].strip("*` ")
                            tk = tokens(title)
                            if len(tk) < 2:
                                continue
                            rows.append({
                                "key": " ".join(sorted(tk)),
                                "title": title[:110],
                                "deadline": p[3] if re.match(r"20\d\d-", p[3]) else "-",
                                "status": "SCREENED %s" % verdict,
                                "folder": os.path.basename(path),
                            })
                except OSError:
                    pass
    return rows


def write_md(rows, path=LEDGER):
    lines = [
        "# Board Ledger",
        "",
        "Every bid folder already on the board, as dedupe keys for the sweep.",
        "**Generated - do not hand-edit.** Rebuild with `python board.py --build`.",
        "",
        "`Key` is the significant-token set of the folder name plus its H1 title,",
        "stopwords stripped. The sweep matches new notices against these keys so a",
        "solicitation already foldered is never re-reported as a fresh find.",
        "",
        "| Key | Title | Deadline | Status | Folder |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append("| %s | %s | %s | %s | %s |" % (
            r["key"], r["title"].replace("|", "/"), r["deadline"],
            r["status"], r["folder"]))
    lines.append("")
    lines.append("%d entries." % len(rows))
    lines.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return len(rows)


def load(path=LEDGER):
    """Read BOARD-LEDGER.md back into rows. Missing file is not an error."""
    rows = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                if not line.startswith("| ") or line.startswith("| Key |"):
                    continue
                if set(line.strip()) <= set("|- "):
                    continue
                p = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(p) < 5:
                    continue
                rows.append({"key": p[0], "tokens": set(p[0].split()),
                             "title": p[1], "deadline": p[2],
                             "status": p[3], "folder": p[4]})
    except OSError:
        pass
    return rows


def dup_of(title, board):
    """Best board entry this title collides with, or None.

    Match is token-overlap, not string equality: BidNet renames the same
    solicitation between runs ("Juvenile Division- Case Management System" ->
    "Court of Common Pleas, Juvenile Division Case Management System and
    Related Services") and different sources title the same bid differently.
    """
    t = tokens(title)
    if not t:
        return None
    best, best_cov = None, 0.0
    for b in board:
        inter = t & b["tokens"]
        if not inter:
            continue
        cov = len(inter) / float(min(len(t), len(b["tokens"])))
        # Two shared distinctive tokens, or total containment of the shorter set.
        if cov < 0.5 or (len(inter) < 2 and cov < 1.0):
            continue
        if cov > best_cov:
            best, best_cov = b, cov
    if best:
        best = dict(best, coverage=round(best_cov, 2))
    return best


def mark(rows, board, field="title"):
    """Annotate rows with board_dup. Flags - never silently drops a row."""
    for r in rows:
        d = dup_of(r.get(field, ""), board)
        if d:
            r["board_dup"] = d
            r["is_new"] = False
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="regenerate the ledger")
    ap.add_argument("--check", metavar="TITLE", help="test one title against it")
    ap.add_argument("--out", default=LEDGER)
    a = ap.parse_args()

    if a.build:
        rows = scan(BOARD_ROOTS)
        nfold = len(rows)
        seen = {r["key"] for r in rows}
        for r in scan_screens(BOARD_ROOTS):
            if r["key"] not in seen:
                seen.add(r["key"])
                rows.append(r)
        rows.sort(key=lambda r: (r["deadline"], r["title"]))
        n = write_md(rows, a.out)
        print("wrote %s (%d entries: %d foldered, %d screened-only)"
              % (a.out, n, nfold, n - nfold))
        return 0
    if a.check:
        d = dup_of(a.check, load(a.out))
        if d:
            print("DUP of: %s\n  folder:   %s\n  deadline: %s\n  status:   %s"
                  "\n  overlap:  %.0f%%" % (d["title"], d["folder"], d["deadline"],
                                            d["status"], d["coverage"] * 100))
        else:
            print("no collision - genuinely new")
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
