"""UNGM sweep -- UN system procurement notices. Free, public, no login.

~4,000 active notices across the whole UN system. Highest software-build density
of any channel tested (10 shortlisted builds from a single sweep on 2026-08-20).

The search is a plain JSON POST that returns HTML rows -- no session, no token.

    python ungm.py
    python ungm.py --json ungm.json --seen seen.json

ponytail: stdlib only, same shape as the other adapters.
"""
import argparse, html, json, re, time
from datetime import datetime
import urllib.request

import board
import ledger

URL = "https://www.ungm.org/Public/Notice/Search"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

KEYWORDS = ["software", "web application", "information system", "digital platform",
            "artificial intelligence", "machine learning", "data management",
            "mobile application", "website", "system development", "database"]

# Awardable instruments only. EOIs and RFIs produce no contract.
AWARDABLE = ("invitation to bid", "request for proposal", "request for quotation")

# UNDP/UNICEF/FAO submissions route through the Quantum portal, which cost five
# bids on timing in one week. Registration is half-done (UNGM vendor no. 1246038)
# but until it is finished these are flagged, not silently included.
QUANTUM = ("undp", "unicef", "fao")

# A US corporation cannot deliver into these. Screen them out before they reach
# a human -- an IAEA nuclear-plant package for Iran surfaced on the first run.
SANCTIONED = ("iran", "syria", "north korea", "korea, democratic", "cuba",
              "russian federation", "belarus", "afghanistan", "myanmar", "sudan")

KILL = re.compile(r"\b(licen[cs]e[sd]?|renewals?|subscriptions?|supply of|"
                  r"servers?|hardware|laptops?|printers?|furniture|vehicles?|"
                  r"construction|catering|cleaning|security guards?|insurance|"
                  r"training|workshop|translation)\b", re.I)


def search(keyword, page=0, size=15):
    body = json.dumps({
        "PageIndex": page, "PageSize": size, "Title": keyword, "Description": "",
        "Reference": "", "PublishedFrom": "", "PublishedTo": "",
        "DeadlineFrom": "", "DeadlineTo": "", "Countries": [], "Agencies": [],
        "UNSPSCs": [], "NoticeTypes": [], "SortField": "DatePublished",
        "SortAscending": False}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def text_of(cell):
    t = html.unescape(re.sub(r"<[^>]+>", " ", cell))
    t = re.sub(r"var deadlineCells.*", "", t, flags=re.S)     # inline script tail
    return re.sub(r"\s+", " ", t).strip()


def parse(page_html):
    out = []
    parts = re.split(r'<div role="row"[^>]*data-noticeid="(\d+)"', page_html)
    for i in range(1, len(parts), 2):
        nid, block = parts[i], parts[i + 1][:6000]
        cells = [text_of(c) for c in
                 re.findall(r'<div role="cell"[^>]*>(.*?)(?=<div role="cell"|$)', block, re.S)]
        if len(cells) < 8:
            continue
        title = re.sub(r"\s*Open in a new window\s*$", "", cells[1])
        title = re.sub(r"\s*(Open|Closed)\s*$", "", title).strip()
        deadline = re.sub(r"\s*[\d.]+$", "", cells[2]).strip()   # trailing sort key
        out.append({"id": nid, "title": title, "deadline": deadline,
                    "published": cells[3], "agency": cells[4], "type": cells[5],
                    "reference": cells[6], "country": cells[7].strip(),
                    "url": "https://www.ungm.org/Public/Notice/%s" % nid})
    return out


def days_out(deadline):
    m = re.match(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})", deadline)
    if not m:
        return None
    try:
        d = datetime.strptime("%s-%s-%s" % m.groups(), "%d-%b-%Y")
        return (d - datetime.now()).days
    except ValueError:
        return None


def screen(r):
    if r["type"].strip().lower() not in AWARDABLE:
        return "REJECT", "notice type '%s' is not awardable" % r["type"]
    if KILL.search(r["title"]):
        return "REJECT", "kill word in title"
    n = days_out(r["deadline"])
    if n is None:
        return "CAUTION", "could not read deadline '%s'" % r["deadline"]
    if n < 7:
        return "REJECT", "closes in %d days" % n
    if any(c in r["country"].strip().lower() for c in SANCTIONED):
        return "REJECT", "sanctioned/non-deliverable geography: %s" % r["country"]
    if any(q in r["agency"].strip().lower() for q in QUANTUM):
        return "CAUTION", "%s submits via the Quantum portal - registration incomplete" % r["agency"]
    return "REVIEW", "awardable, %d days out" % n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--seen", help="ledger JSON to dedupe against")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--pages", type=int, default=3, help="pages per keyword (15/page)")
    a = ap.parse_args()

    ledg = ledger.load(a.seen)

    # control: a filter that does not bite would return the same set for every term
    wide = len(parse(search("")))
    narrow = len(parse(search("zzzqqq-no-such-thing")))
    bit = narrow < wide
    print("control: empty-term rows=%d ; nonsense-term rows=%d ; filter bit: %s"
          % (wide, narrow, "YES" if bit else "NO"))

    seen, rows = set(), []
    for kw in KEYWORDS:
        got = []
        for pg in range(a.pages):
            batch = parse(search(kw, pg))
            got += batch
            if len(batch) < 15:
                break
            time.sleep(0.5)
        for r in got:
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            r["keyword"] = kw
            r["verdict"], r["reason"] = screen(r)
            r["is_new"] = ledger.key("ungm", r["id"]) not in ledg
            rows.append(r)
        print("  %-24s %3d rows" % (kw, len(got)))
        time.sleep(1)                    # ponytail: polite scraper

    order = {"REVIEW": 0, "CAUTION": 1, "REJECT": 2}
    board.mark(rows, board.load())
    rows.sort(key=lambda r: (order[r["verdict"]], days_out(r["deadline"]) or 999))
    n = {v: sum(1 for r in rows if r["verdict"] == v) for v in order}
    nnew = sum(1 for r in rows if r["verdict"] == "REVIEW" and r["is_new"])
    print("\nUNGM: %d unique notices -> %d REVIEW (%d new), %d CAUTION, %d REJECT"
          % (len(rows), n["REVIEW"], nnew, n["CAUTION"], n["REJECT"]))
    print("=" * 78)
    for r in rows:
        if r["verdict"] == "REJECT" and not a.all:
            continue
        print("\n[%s]%s %s" % (r["verdict"], " NEW" if r["is_new"] else "", r["title"][:74]))
        print("  %s | %s | %s | closes %s" % (r["agency"], r["type"], r["country"], r["deadline"]))
        print("  %s  -- %s" % (r["url"], r["reason"]))
    if a.json:
        json.dump({"results": rows}, open(a.json, "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    main()
