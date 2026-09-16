# ARCHITECTURE.md

Diagrams: https://claude.ai/artifact/RirfapYnSgbuxdsAvAnF6X

## The finding that shaped this

A live audit of every adapter on 2026-08-31 found the sweep was not broken, it was
starved. All four control checks passed.

| source | universe | actually read |
|---|---|---|
| BidNet | 24,543 open bids | **1%** |
| NYSCR | 602 open awardable ads | **16%** |
| SAM | 280 "active" | 64% were already past their response date |

`MIN_LEAD_DAYS = 10` additionally hard-rejected **71 genuinely-open notices** that
never printed.

**Fanning out over a 1% read rate buys N views of the same throttled slice.** So
Phase 0 - roughly twenty lines - runs before any agent does. Those fixes are applied
in this repo; see the `Phase 0 fix` comments in `sources/`.

## Topology

    CONTEXT PACK  (BRIEF.md for sourcing, RAMEDIA.md for verdict only)
          |
    DISPATCHER  (code, not an agent)  -- checkpoint 1
          |
      +---+--------------------------------------------------+
      |        8 sourcing agents, parallel, uncapped          |  -- checkpoint 2
      |  sam  bidnet  nyscr  ungm  issuers  google  web  ...  |
      +------------------------------------------------------+
          |                                   |
          |                          SCOUT -> reachability gate
          |                                -> PROBE xN (uncapped)
          |                                -> PROMOTE to SOURCES.md
      collector bus
          |
    CONSOLIDATOR  (board.py token-overlap merge)  -- checkpoint 3
          |
    VERDICT  (viability gates, reference gate, build-vs-buy)
          |
    SCRIBE x1, serial  ->  Drive + local
          |
          +--> appends SOURCES.md / BOARD-LEDGER.md / KILL-PATTERNS.md
               back into the context pack: next run starts wider and cheaper

## Three decisions worth arguing with

### 1. The coordinator is the interactive session, not an agent

A background workflow cannot ask a question mid-run. It fires, runs to completion,
returns. A coordinator inside it that meets an unknown must guess or fail silently,
and both are forbidden. The session is the only component that can turn to the user
and ask, so that is where coordination lives. See `PROTOCOL.md`.

### 2. The dispatcher is code

Assigning N sources to N agents is a partition, not a decision. An LLM router can
hallucinate an overlap; a partition cannot. This - not a better prompt - is what
delivers the no-duplicate-work requirement. `test_dispatcher.py` asserts disjointness
and that a double assignment raises.

Judgement stays with the coordinator: the final ranking call, and every question the
agents kick back.

### 3. Dedupe is board.py, not an agent

Token-overlap matching against the board already exists and is tested. It flags rather
than drops, so a false positive cannot eat a real find. An LLM dedupe agent would be
slower, non-reproducible, and a rewrite of tested code. The consolidator *agent* keeps
the judgement half - are these two differently-titled rows the same solicitation - and
calls the script for the matching half.

## The lanes

| lane | status | note |
|---|---|---|
| SAM, BidNet, NYSCR, UNGM | proven, script-backed | deterministic, near-zero token cost |
| nonprofit issuers | **strongest of the web lanes** | Meridian, CEPF, LSC, CalVCB all came this way and none were syndicated anywhere. The lever is roster size: `sources/issuers.txt` holds 40 domains, and that is the entire lane |
| google | dork lane, `sources/google.py` | generic search failed five of five attempts here and invented two deadlines that nearly shipped as confirmed finds. Only specific phrasings work. Fixed query budget, and it emits leads, never finds |
| linkedin | signal lane, blocked | hosts the signals that precede solicitations - grant awards, new digital-director hires - not solicitations themselves. Output belongs in a watchlist, not a GO list |
| web | nonprofit and commercial issuers only, `sources/web.py` | website and CMS scope, screened over the other adapters' JSON |
| scout | discovery, `sources/scout.py` | reachability gate first; emits candidate sources, never opportunities |

## What compounds, and what does not

Three append-only files feed the next run:

- `SOURCES.md` - sources accumulate and never leave, so ground swept grows
- `BOARD-LEDGER.md` - a longer ledger means fewer re-judgements
- `KILL-PATTERNS.md` - a learned phrase screens out its whole kind for free thereafter

Append-only is what makes the never-delete rule structural rather than an instruction
an agent might forget.

**This is not exponential, and should not be described as such.** Coverage compounds
and cost per run falls. Hit rate barely moves - better sourcing raises the number of
shots, not the hit rate. The real cap is no delivered public-sector past performance,
and no agent count fixes that. `KILL-PATTERNS.md` is the only piece that compounds on
the quality axis rather than the volume axis, which is exactly why it is worth having.
