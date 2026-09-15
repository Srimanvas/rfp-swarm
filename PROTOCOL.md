# PROTOCOL.md - how a run executes

## Who the coordinator is

**The interactive Claude session, not an agent inside a workflow.**

This is forced, not stylistic. A background workflow cannot ask a question mid-run:
it fires, executes to completion and returns. An agent buried inside it that meets an
unknown has only two moves, guess or fail silently, and both are forbidden here. The
session is the one component that can turn to the user and ask.

## Phases

| phase | who | notes |
|---|---|---|
| 0 | code | unthrottle - the funnel fixes. No agents run until this lands |
| 1 | `dispatcher.py` | one disjoint source per agent. Checkpoint 1 |
| 2 | sourcing agents, parallel, **uncapped in count** | each runs its adapter or its lane. Checkpoint 2 |
| 3 | probe agents, **uncapped in count** | one per new source that clears the reachability gate |
| 4 | consolidator | cross-source merge via `board.py`. Checkpoint 3 |
| 5 | verdict | viability gates, reference gate, build-vs-buy. Loads the full context pack |
| 6 | scribe, **exactly one, serial** | Drive + local + appends the learning files |

## The three dedupe checkpoints

Dedupe fires at three different times, because dedupe only at the end is too late -
by then every agent has already spent budget on the same row.

1. **Before the run.** The dispatcher partitions. Two agents cannot receive the same
   source, so the commonest duplication is unrepresentable rather than merely
   discouraged.
2. **During the run.** Every agent checks `BOARD-LEDGER.md` before reporting anything
   as a fresh find, and says "already on board" instead.
3. **After the run.** The consolidator merges across sources, because the same
   solicitation legitimately appears on BidNet and on the issuer's own page. Matching
   is `board.py` token-overlap: deterministic, tested, and it flags rather than drops,
   so a false positive cannot eat a real find.

## BLOCKED - how an agent asks a question

An agent that meets anything the brief does not cover has exactly one legal move.
It may not infer, may not pick the likely answer, and may not retry past two attempts.

    BLOCKED
      agent:          src:bidnet
      source:         bidnet
      question:       <the specific unknown, as one answerable question>
      tried:          <what was attempted, so it is not repeated>
      options:        <candidate answers, if any are visible>
      cost_if_wrong:  <what breaks if this is guessed>

**An agent may never resolve its own BLOCKED.** It emits the record and stops that
branch. Other branches continue.

### What triggers one

- A fact the brief does not contain - a rate, a reference, a certification, an
  eligibility answer
- A judgement the architecture does not cover - a source neither clearly in nor
  clearly out of a lane
- A gate that reads ambiguously - "public sector experience preferred" sitting
  between PASS and FAIL
- **Two failed attempts.** No retry loops, no working around a login wall
- Anything that would cost money, create an account, or submit something

### What the coordinator does with them

Batches every `BLOCKED` from the run into **one** question set. Sixteen agents under
a strict no-inference rule produce many questions; asked one at a time that is
unusable, asked as one set it is a short review. Answers are appended to the context
pack so the same question is never asked twice.

**The honest cost:** the first run returns more questions and fewer verdicts than a
run allowed to guess. That is the intended trade. A hallucinated eligibility verdict
does not announce itself - it quietly wastes a week of bid work.

## Token fences

Uncapped in **count** for sourcing and source-discovery agents. Never uncapped in
**cost per agent** - one badly-scoped agent outspends twenty disciplined ones.

| fence | rule |
|---|---|
| script-first | if a source has an adapter, run it and report. Do not browse |
| no documents in sourcing | return title, URL, issuer, code, date. Full text only after the verdict gate |
| structured returns | fixed-field records. No prose, no narration, no raw HTML |
| split context | sourcing agents load `BRIEF.md`. Only the verdict step loads full `RAMEDIA.md` |
| WebSearch monopoly | only the `google` agent may call it, on a fixed allowance. Every other agent is forbidden |
| browser singleton | browser-driven sources run one at a time |
| two-strike rule | two failures then `BLOCKED`. Known-unfixable sources are not retried at all |

Rationale for "no documents in sourcing", measured 2026-08-26: BidNet's free scope
summary killed **20 of 35** candidates as product mandates before a single document
was opened.

## Never delete anything

Create, modify, rename, move. Never delete, trash, truncate or overwrite-to-nothing.

In Drive that means `create_file` and `update_file` only, **never `trash_file`**.
Drive's `update_file` cannot rewrite content - title and parent only - so everything
mutable is modelled as append-only dated files. That makes the rule structural rather
than an instruction an agent might forget, and it is why there is exactly one scribe:
parallel writers would race their creates and fork the ledger.
