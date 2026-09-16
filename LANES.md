# LANES.md - the four agent-driven lanes

`BRIEF.md` is what every sourcing agent shares. This file is only what differs.
Nothing here restates the brief: the hard screens, the discard list, the record
format and the operating rules all still apply unchanged.

Four lanes have no adapter that runs end to end, so the agent carries part of the
method. Every other source in `SOURCES.md` is script-first - run the adapter,
report, do not browse.

| lane | emits | script | status |
|---|---|---|---|
| google | leads | `sources/google.py` (query generator) | active |
| linkedin | watchlist signals | - | **blocked** |
| web | screened rows | `sources/web.py` (screener) | active |
| scout | candidate sources | `sources/scout.py --probe` | active |

## google

**For:** dork queries on proven phrasings, to surface solicitations the adapters
do not cover. Every output is a LEAD.

**Not for:** composing queries. Generic web search for live solicitations has
failed every time it was tried here - five attempts, zero traces. Worse than
zero: the result summaries invented two deadlines that nearly shipped as
confirmed finds. One claimed Aug 14 when the PDF said proposals closed Jun 23;
the other named a solicitation that does not exist. The engine strongly prefers
vendor listicles ("21 Best Nonprofit CRMs") over real RFPs. The agent does not
get to try its own phrasing against that.

**This is the only agent permitted to call WebSearch.** Every other agent is
forbidden, per the WebSearch monopoly fence in `PROTOCOL.md`.

Steps:

1. `python sources/google.py` - or `--json q.json` to keep the list.
2. Run **only** the queries that script emits, in the order emitted. Hard budget
   **40**. The script refuses a larger one.
3. For each hit, open the issuer's own page or the document body. A hit that
   cannot be traced there is dropped, not reported.
4. Check `BOARD-LEDGER.md` before calling anything fresh.
5. Return records. Mark every one a LEAD.

**Returns:** the `BRIEF.md` record, with `source: google` and the originating
query. `close_date` is filled only from the issuer's own page or the document
body. Never from a search-result summary - that is the exact failure that
produced the two fabricated deadlines.

Emit BLOCKED when:

- a lead's issuer page is unreachable after two attempts
- a deadline appears only in a search summary and nowhere traceable
- a hit is a paid repost of something a public agency must publish free, and the
  free original cannot be found
- the query budget is exhausted with leads still untraced

## linkedin

**STATUS: BLOCKED.** The lane needs a Chrome extension permission grant for
linkedin.com, which only the user can give. It does not run until that lands. An
agent assigned this lane emits BLOCKED and stops.

**For:** signals, when it does run. LinkedIn does not host solicitations. It
hosts what precedes them:

| signal | why it matters |
|---|---|
| programme or ops staff saying they are seeking proposals | the RFP is being written now |
| grant awards | a funding announcement often precedes a build RFP by weeks |
| new CTO / digital-director hires at nonprofits | new leadership buys systems |

**Not for:** the GO list. Output goes to the **grantee watchlist**. This lane is
a watchlist feeder, not a pipeline source. No yield has ever been measured here -
do not state or imply one.

**Route:** a read-only pass through the user's own logged-in Chrome, at human
pace. No messaging, no connection requests, no form submission, no scraping
volume. The browser singleton fence applies - one browser-driven source at a
time.

**Returns:** watchlist rows - organisation, signal type, date observed, URL, and
the one line of evidence. No verdict, because nothing here is a solicitation.

Emit BLOCKED when:

- the permission grant for linkedin.com is absent - the current state
- a page asks for a login, an interstitial, or any click beyond reading
- a signal implies a solicitation exists but no issuer posting can be found -
  that is a watchlist note, never a find

## web

**For:** website and CMS scope only. Per the user's decision of **2026-09-15**
this lane filters on **issuer type**, not on the reference requirement.

| in | out |
|---|---|
| nonprofits, foundations, associations, commercial | cities, counties, states, federal, school districts, universities |

**This restriction applies to THIS LANE ONLY.** Every other lane keeps sweeping
government, screened by the reference gate in `RULES.md`.

**Not for:** re-sweeping. It screens rows the other adapters already pulled.
Re-fetching the same universe to apply a different filter is budget spent for
nothing.

Steps:

1. `python sources/web.py out-bidnet.json out-nyscr.json --json out-web.json` -
   any adapter `--json` outputs this run produced.
2. Read the counts line: `N REVIEW, N BLOCKED, N REJECT`.
3. Optionally run targeted issuer queries of its own - but never against a source
   another lane is already assigned. The dispatcher partitions sources for a
   reason.
4. Check `BOARD-LEDGER.md` before calling anything fresh.

**Returns:** the `BRIEF.md` record per row, with `web.py`'s `verdict` and
`reason` carried through unchanged.

`web.py` returns BLOCKED when the issuer type is not stated in the available
text. **The agent must not guess it.** Resolving it means the issuer's own page
naming itself - not inference from a title, a domain, or a plausible name.

Emit BLOCKED when:

- `web.py` marked the row BLOCKED and the issuer's own page does not state the
  type
- an issuer is genuinely both - a nonprofit operating a public authority, say
- scope sits between website work and a product purchase and the free summary
  does not settle it
- there is no adapter output to screen

## scout

**For:** finding procurement **sources** the system does not have. Not
opportunities. Emitting an opportunity is out of scope for this lane - if one
turns up, name the source it came from and stop there.

Steps:

1. Propose candidate sources not already in `SOURCES.md`, including its retired
   table - that table is the record of what was tried.
2. Gate each one: `python sources/scout.py --probe <url>`. The gate is
   reachable, free, names the issuer, carries awardable notices.
3. **Only a PASS may be probed further.** A FAIL stops there.
4. A probed source is **PROMOTED into `SOURCES.md` only if it yields at least one
   non-duplicate hit.** That is the brake on unbounded growth: a source that only
   re-serves rows the board already has is not a source, it is a mirror.

**Known-unfixable. Never re-attempt, never propose:**

| source | why |
|---|---|
| eMMA Maryland | reCAPTCHA on the public browse page. Never bypass - a human must fetch |
| CalEProcure | 403 to every scripted fetch. Use the issuing agency's own page |
| OregonBuys documents | .docx come through a JS form POST behind a session |
| RFPMart as a primary source | sold an NIH grant as an RFP, re-posted a closed solicitation with a fresh date, ~95% product buys |

**Source count is uncapped** - the user's decision, unlimited agents may look for
sources. Cost per agent is not uncapped: the per-agent fences in `PROTOCOL.md`
apply to every one of them.

**Returns:** candidate source rows - id, proposed lane, url, access method, probe
verdict, and the non-duplicate hit that justifies promotion, or the note that
there was none. The scribe writes `SOURCES.md`. The lane does not.

Emit BLOCKED when:

- a candidate needs an account, a login, a fee, or a submitted form
- the probe is ambiguous - reachable, but the issuer is not named
- a candidate sits between two lanes with no clear home
- two probe attempts have failed
