"""Board-ledger dedupe checks, built from the four real misses of 2026-08-28.

Run: python test_board.py
"""
import board

BOARD = [
    {"key": k, "tokens": set(k.split()), "title": t, "deadline": "-",
     "status": s, "folder": "x"}
    for k, t, s in [
        ("utsa vied wordpress consolidation antonio",
         "UT San Antonio - VIED 10-Site WordPress Consolidation", "GO-WITH-FIXES"),
        ("juvenile division case",
         "Juvenile Division- Case Management System", "SCREENED CAUTION"),
        ("meridian international center",
         "Meridian International Center - Website Rebuild", "QUESTIONS SUBMITTED"),
        ("fdlp exchange",
         "GPO FDLP eXchange Hosting", "NON-VIABLE"),
        ("ogemaw",
         "Ogemaw County Website Redesign", "GO"),
        ("sumner",
         "Sumner City Website Redesign", "GO-WITH-FIXES"),
    ]
]


def hit(title):
    d = board.dup_of(title, BOARD)
    return d["title"] if d else None


def main():
    # 1. Different source, different wording, same solicitation.
    assert hit("VIED Website Redesign & Migration to WordPress Infrastructure") \
        == "UT San Antonio - VIED 10-Site WordPress Consolidation"

    # 2. BidNet re-titles the same bid between runs - the Ohio case.
    assert hit("Court of Common Pleas, Juvenile Division Case Management System "
               "and Related Services") == "Juvenile Division- Case Management System"

    # 3. One distinctive token is enough when it is the whole of the shorter set.
    assert hit("Meridian Website Redesign") == "Meridian International Center - Website Rebuild"

    # 4. Punctuation and agency noise must not defeat it.
    assert hit("Hosting Service (FDLP eXchange/FDP.gov)") == "GPO FDLP eXchange Hosting"

    # 5. THE ONE THAT MATTERS: two unrelated municipal website redesigns share
    #    every generic word and must NOT collide. If the stoplist ever thins,
    #    this fails first and the sweep starts silently eating real finds.
    assert hit("Sumner City Website Redesign and Development Services") \
        != "Ogemaw County Website Redesign"

    # 6. Genuinely new stays new.
    assert hit("Statewide Broadband Mapping Portal") is None
    assert hit("Ai Recruiter") is None

    print("all board dedupe checks passed")


if __name__ == "__main__":
    main()
