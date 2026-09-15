# KILL-PATTERNS.md - what killed a bid, so it dies cheaper next time

**Append one row every time an opportunity is judged NON-VIABLE.** This is the only
part of the system that compounds on the quality axis rather than the volume axis:
a phrase learned once screens its whole kind out for free thereafter.

**Append-only.** Never delete a row, never rewrite one. A pattern that turns out to be
wrong gets a new row marking it superseded.

## Structural kills - no verdict survives these

| pattern | why it kills | first seen |
|---|---|---|
| `must (be \|have) FedRAMP (certified\|authorized)` | vendor-held FedRAMP is a six-figure, 12-18 month wall. Agency-held is fine - read which side of the boundary | GPO 040ADV-26-R-0041 |
| `not-for-profit\|501\(c\)\(3\)` in eligible applicants | we are a for-profit Wyoming C Corp | NYSDOH SOI 20838 |
| `currently in use by \d+ (customers\|agencies)` | installed-base mandate; a build shop cannot supply it | 2026-08-01 sweep |
| `certificate of insurance` in required-uploads-at-submission | collides with bind-at-award. Check the uploads list, not just the terms | NFTA RFP 260039 |
| `references must be from (government\|public)` | no delivered government contract | screen rule |
| `scripted (product )?demonstration` | pre-award demo implies a configured product | build-vs-buy test |
| `audited financial statements\|D&B\|bid bond` | small-firm-entry rule | 2026-07-31 conflict sweep |
| `\d+ years.{0,30}(municipal\|government\|K-12)` | domain-experience minimum | 2026-07-31 conflict sweep |
| `OECM\|Ontario` bars US businesses | hard eligibility exclusion, invisible from the title | build-vs-buy test |

## Product-mandate tells - read the FIRST sentence of the overview

| pattern | why |
|---|---|
| overview opens `seeking proposals for a (SaaS\|Software as a Service\|platform)` | it is a purchase, not a build. No good scope further down changes it |
| `plans to use this product` | same |
| NIGP `96258` Expert System Software | product code |
| NIGP `208-\d\d` | business software product |
| pricing schedule asks per-seat / annual subscription | licensing, not a build |

## Positive signal - the strongest one we have

| pattern | why |
|---|---|
| NAICS `541511` Custom Computer Programming Services | it is the build code. Predicts build-vs-buy better than any title |
