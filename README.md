# rfp-swarm

A parallel multi-agent pipeline for sourcing awardable software, AI and web
solicitations.

**No server. No database. No hosting.** Code and screening rules live here, state
and findings live in Google Drive, compute is a Claude session.

## What is in this repo

**Code and architecture only.** No solicitations, no found opportunities, no board
folders, no client data - see `.gitignore`, which is the fence.

| | |
|---|---|
| `ARCHITECTURE.md` | the design: topology, the anti-duplication mechanism, what compounds |
| `PROTOCOL.md` | how a run executes, and the `BLOCKED` record - how an agent asks a question |
| `BRIEF.md` | the one-page screening brief every sourcing agent loads |
| `SOURCES.md` | the source registry. The dispatcher's input, and an append-only learning file |
| `KILL-PATTERNS.md` | learned kill phrases, appended every time a bid dies |
| `dispatcher.py` | deterministic source-to-agent partition |
| `sources/` | the source adapters, standard library only |
| `sources/google.py` | search-lane query generator - emits dorks, never calls WebSearch itself |
| `sources/web.py` | website/CMS screen over other adapters' JSON, nonprofit + commercial issuers |
| `sources/scout.py` | reachability gate for candidate new sources, before one earns a SOURCES.md row |
| `board.py` | token-overlap dedupe against work already done |
| `docs.py` | document retrieval and text extraction - runs after the verdict gate, never before |

## Run it

    python dispatcher.py              # the assignment table
    python test_dispatcher.py         # the partition is disjoint, fences attached

    python sources/sam.py             # federal
    python sources/bidnet.py --pages 8
    python sources/nyscr.py           # all categories
    python sources/ungm.py
    python sources/issuers.py

Standard library only. No dependencies, no pip install.

## The two files this repo does NOT carry

`RAMEDIA.md` and `RULES.md` are gitignored. They hold the firm's FEIN, direct
phone numbers, client reference contacts, the never-claim list and the open
compliance gaps - material that must not sit in a public repo. `RAMEDIA.example.md`
shows the shape. Keep the real one local.

## Relationship to rfp-sweep

`Srimanvas/rfp-sweep` (private) is where the adapters started and still runs the
existing weekday cloud routine. Nothing there has been changed or removed. This
repo is the orchestration layer and the intended home going forward; cutting the
cloud routine over is a separate, deliberate step.
