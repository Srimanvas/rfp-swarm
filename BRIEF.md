# BRIEF.md - the one-page screening brief

**Every sourcing agent loads this file and only this file.** The full context pack
(`RAMEDIA.md`) is loaded only by the verdict step. A sourcing agent does not need the
past-performance library, and loading it into every agent spends it N times for nothing.

## What we are looking for

Awardable solicitations for **custom software builds, AI/workflow automation, and
website/CMS work**. A six-person US firm, all-remote capable.

Best-fit profiles: ERP and accounting integration - distribution, supply chain and
logistics automation - AI workflow automation - custom application development -
WordPress/WooCommerce redesign and hosting - field service management - marketplace
and e-commerce operations.

## Hard screens - apply before reporting anything

**Awardable only.** Drop RFI, Request for Information, Sources Sought,
Pre-solicitation, Presolicitation, Request for EOI, Expression of Interest, INFO ONLY.
These produce no contract. On SAM that means `type.code` in `o` and `k`, never `r` or `p`.

**Deal size:** no floor, cap **300,000 USD**.

**Geography:** nationwide and remote are fine. Drop anything mandating an in-state
office or local business registration.

**Screen on codes, not words. Titles lie in both directions.**

| code | means |
|---|---|
| NAICS 541511 | custom computer programming - **the build code, strongest positive signal** |
| NAICS 541512 / 541519 / 518210 | systems design / other computer related / hosting |
| NIGP 96258 | Expert System Software - a product purchase |
| NIGP 208-xx | business software product |
| NIGP 918 / 920 series | services |

**The government reference gate.** The firm has no delivered government contract.

- PASS: "three references for similar projects", "client references", "relevant experience"
- FAIL: "public sector experience required", "references must be from government agencies", "completed N projects for municipalities"
- CAUTION: public-sector experience as a *scored* criterion is survivable; as a *mandatory* one it is not

**Lane-specific:** the `web` agent takes **nonprofit, foundation, association and
commercial issuers only** - no cities, counties, states, federal, school districts or
universities. That restriction is for the web lane alone; every other lane sweeps
government freely, screened by the reference gate above.

## Discard on sight, before opening anything

1. COTS / installed-base language - "currently in use by N customers", capability matrix, scripted product demo
2. Audited financial statements, D&B, bid bonds
3. Domain-experience minimums - "N years in X industry", municipal references required
4. Cyber insurance at or above 5,000,000 USD
5. Hard SOC 2 / CJIS / FedRAMP / HIPAA / PCI requirements
6. Eligibility limited to 501(c)(3) - the firm is a for-profit C Corp
7. **Vendor-held** FedRAMP. *Agency-held* FedRAMP is fine and costs us nothing - read which side of the boundary it sits on

See `KILL-PATTERNS.md` for the full learned set, and append to it every time something dies.

## Operating rules

1. **Return fixed-field records.** No prose, no narration, no raw HTML.
2. **Run the control query first.** A silently-ignored filter parameter is the failure
   mode that makes a sweep look clean while screening nothing. It has happened on SAM
   and was nearly missed on NYSCR.
3. **Never report an unverified deadline.** Search-result summaries invent them - two
   fabricated deadlines nearly shipped as confirmed finds in a single sweep. A date
   comes from the document body or the issuer's own page, or it is not reported.
4. **Check `BOARD-LEDGER.md` first.** Already foldered or already screened means say
   so, not report it as fresh.
5. **No document retrieval.** Title, URL, issuer, code, date. Full text happens after
   the verdict gate.
6. **Never pay for a government solicitation.** Public agencies must publish openly.
   Search the distinctive scope phrase and find the free agency posting.
7. **Two failures then `BLOCKED`.** No retry loops. See `PROTOCOL.md`.
8. **Never delete anything, anywhere.** Create, modify, rename, move only.

## The record to return

    id | source | title | issuer | url | naics_or_nigp | notice_type | close_date |
    verdict | reason | already_on_board

`verdict` is one of `REVIEW`, `WEAK`, `BODY-ONLY`, `EXPIRED`, `REJECT`.
Anything you cannot determine is `BLOCKED`, never a guess.
