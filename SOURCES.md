# SOURCES.md - the source registry

**This file is the dispatcher's input.** `dispatcher.py` parses the table below and
assigns exactly one source per agent, so two agents can never be handed the same
source. Adding a row here is how a source becomes permanent.

**Append-only.** To retire a source set its status to `retired` - never delete the row.
The history of what was tried and what failed is the point.

| id | lane | adapter | access | status | notes |
|---|---|---|---|---|---|
| sam | federal | sources/sam.py | script | active | NAICS 541511/541512/541519/518210 + PSC DA01/DA10/7A20, awardable types o/k only |
| bidnet | state-local | sources/bidnet.py | script | active | ~24,543 open bids; the volume lane. Free scope summary on detail pages |
| nyscr | state-local | sources/nyscr.py | script | active | all NY agencies/authorities >= $50K must advertise here |
| ungm | un | sources/ungm.py | script | active | ~4,000 notices. Submission still gated on Quantum registration |
| issuers | nonprofit | sources/issuers.py | http | active | 40-domain roster; the lever is roster size |
| google | search | sources/google.py | search | active | dork lane ONLY. Proven phrasings, fixed query budget. Emits leads, never finds |
| linkedin | signal | - | browser | blocked | needs Chrome extension permission for linkedin.com |
| web | nonprofit-commercial | sources/web.py | http | active | website/CMS scope, nonprofit + commercial issuers only |
| scout | discovery | sources/scout.py | http | active | hunts sources not in this table. Emits candidate sources, never opportunities |

## Retired / known-unfixable - do not re-attempt

| id | why |
|---|---|
| emma-maryland | reCAPTCHA on the public browse page. Needs a human click. Never bypass |
| caleprocure | 403 to every scripted fetch. Use the issuing agency's own page instead |
| oregonbuys-docs | detail page is free, but .docx come through a JS form POST behind a session |
| websearch-generic | generic "<system> RFP 2026" queries return vendor listicles, and summaries invent deadlines |
| rfpmart-primary | sold an NIH grant as an RFP, re-posted a closed solicitation with a fresh date, ~95% product buys |
