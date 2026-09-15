# RAMEDIA.example.md

`RAMEDIA.md` is the firm context pack: the file the verdict step loads to decide
what can truthfully be claimed and what kills a bid.

**It is gitignored and must stay that way.** The real file contains the firm's
tax identifier, direct phone numbers, client reference contacts, the internal
never-claim list and open compliance gaps. None of that belongs in a public repo.

Copy this file to `RAMEDIA.md` and fill it in locally.

---

## 1. Who we are
Legal entity, d/b/a, state and type of incorporation, tax id, registrations
(SAM.gov, E-Verify), address, headcount, time zone, partner programs.

### Team and the real rate card
Name, role, contact, hourly rate. Then the **blended rate actually quoted** - pricing
models start there, not from market estimates.

### Pricing philosophy
Fixed fee by milestone or time and materials; who carries overrun exposure; whether
to price to the ceiling.

## 2. Stack we can claim in production
Only what has actually shipped.

## 3. Past performance
One entry per engagement. **Tag each with its verification state**: KPIs VERIFIED
(client-approved for external use), QUALITATIVE ONLY (scope and duration but no
numbers), or IN PROGRESS (present as current work, never as past performance).

Then a lead-with matrix mapping solicitation type to the entry that leads and the
ones that support.

## 4. NEVER CLAIM
Anything designed but not shipped. Anything at proposal or concept stage. **Lost bids
are not past performance** - a bid price is not a contract value and must never be
used as a revenue reference or pricing comp.

## 5. Compliance posture
For each of SOC 2, accessibility, insurance, E-Verify, registrations: the real status,
and the exact language permitted in a proposal. Never imply an artifact exists.

## 6. Targeting criteria
Deal size floor and cap, geography rules, entity-type constraints, and the hard
filters that gate whole categories.

## 7. The reference gate
The PASS / FAIL / CAUTION phrasings for the firm's weakest qualification.

## 8. House proposal voice
How the firm writes. Read the client's live site before estimating. Name gaps plainly.
Publish baselines beside headline numbers. Disclose AI-assisted tooling.

## 9. Hard operating rules
Never delete. Append-only. Screen on codes not words. Control queries. Never report an
unverified deadline.
