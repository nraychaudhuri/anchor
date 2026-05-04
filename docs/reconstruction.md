# Reconstruction Brief — anchor

> This document is the sole input for an independent reconstruction agent.
> The agent must not have access to the original source code.
> It should produce an implementation that satisfies the ideology and constraints
> recorded here — free to diverge in all other respects.

---

## What you are building

Anchor is a Claude Code plugin with three skills:

**`/anchor:seed`** — Reads an existing codebase and all historical Claude Code transcripts to
build a canonical spec from scratch: structured JSON records of decisions, rules, tradeoffs,
and lineage for each module. Run once per project.

**`/anchor:companion`** — Loads the canonical spec into agent context at session start, detects
drift between new decisions and established rules, and runs a sidebar that captures decisions
made during the session into the spec automatically.

**`/anchor:pairmode`** — Bootstraps and manages a structured builder/reviewer methodology on
any project. Produces a full scaffold (CLAUDE.md, agent docs, settings, phase specs, CER
backlog) and enforces the build loop at every commit. Generates `docs/ideology.md` — a
conviction and constraint record that survives across implementations — and
`docs/reconstruction.md` — a handoff prompt that seeds an independent agent to produce a
competing implementation of the same project from ideology alone.

---

## Why it exists

Code is becoming cheap to generate. What's scarce is the spec — the record of what was
decided, why, and what must never be violated. Without it, agents drift. Developers forget.
Constraints agreed on two sessions ago are invisible today.

Anchor makes intent persistent. It captures decisions as you work, validates new actions
against prior ones, and makes the canonical spec the source of truth for every agent and
every session.

The n-tier reconstruction workflow extends this further: a prototype developed by a human
developer — working fast, making tradeoffs, building habits — can have its architectural
intent extracted into ideology and brief artifacts. Those artifacts can then seed one or more
pairmode build processes that run largely autonomously with respect to architectural decisions,
producing competing implementations. The results can be inspected for backportable ideas,
used to leapfrog the prototype, or ported to other stacks with very little additional effort.
The human provides the intent; the agents compete on implementation.

---

---

## Non-negotiable ideology

> These convictions and constraints must be expressed in any correct implementation.
> An implementation that contradicts them is not this project.

### Convictions



- We prefer codifying policy over implicit convention, because persistent memory of decisions, specs, and constraints is the only thing that survives agent drift and developer forgetfulness across sessions.

- We prefer rationale-bearing decisions over bare rules, because a constraint without a reason will be violated by the first agent that encounters a situation the rule author did not anticipate.

- We prefer spec-first development over code-first development, because correctness can only be verified against an intent that is recorded somewhere.

- --



### Constraints



#### Never silently pass contradictions

**Rule:** anchor must never allow a development action to proceed without validating it against previous decisions recorded in the canonical spec.

**Why this constraint exists:** The value of a persistent memory system is precisely that it catches what humans and agents forget. A system that misses contradictions provides false confidence, which is worse than no system.


#### Hooks are thin relays only

**Rule:** Hook scripts must emit to the pipe and exit. No API calls, no spec writes, no blocking logic in hooks.

**Why this constraint exists:** The sidebar owns all heavy work. The hook-pipe-sidebar separation is the core architectural boundary in anchor. Violating it collapses two roles into one and makes the system unauditable.


#### Sidebar owns all state writes

**Rule:** Only sidebar.py and skill scripts may write to spec files, openspec directories, or .companion/ state. Hooks write only to the pipe.

**Why this constraint exists:** Single-writer ownership is the only reliable way to prevent race conditions in a system with concurrent hook events and sidebar processing.




---

## What must survive any implementation



- The canonical spec format: spec.json with module, summary, business_rules, non_negotiables, tradeoffs, conflicts, and lineage. Any re-implementation must read and write this format.

- The rationale-bearing decision record: every non-negotiable and tradeoff must carry its reason and accepted cost, not just the rule itself.

- The hook-pipe-sidebar architecture: hooks are thin relays; the sidebar owns all extraction and state writing. This separation must survive any re-implementation.

- Append-only lessons: methodology improvements are never destructively edited — only extended and status-updated.



---

## What you are free to change

> These are fingerprints of the original implementation, not constraints.
> You are encouraged to find better approaches.



- Implementation language (Python is a fingerprint, not a conviction).

- Template engine (Jinja2 is convenient, not architecturally required).

- File layout within skills/ — the public interface is the SKILL.md contract, not the internal directory structure.

- Test framework — pytest is a preference, not a constraint.

- The Rich TUI in sidebar.py — the sidebar's display is cosmetic; its pipe-reading and extraction loop are not.

- --



---

## Comparison rubric

> After building, your implementation will be evaluated against the original on
> these dimensions. Optimise for them explicitly.


_(not yet specified — populate docs/ideology.md Comparison basis)_


---

## What you should question

> The original implementation made these choices under time or knowledge constraints.
> You are encouraged to find better solutions and justify them against the convictions above.



- Whether Jinja2 templates are the right abstraction for scaffold generation — a code-generation approach with structured types might be more refactorable.

- Whether the two-hop product.json → config.json → spec_location path is worth the indirection, or whether a single config file suffices.

- Whether the lessons.json append-only format scales, or whether a database-backed store would serve audit and review better at larger lesson volumes.



---

## Instructions for the reconstruction agent

1. Read this document in full before writing any code.
2. Build a working implementation that satisfies the ideology above.
3. For every non-negotiable constraint: explicitly state how your implementation satisfies it.
4. For every "should question" item: either improve on it or justify why you kept the
   original approach, citing the relevant conviction.
5. For every comparison dimension: document your approach and how it scores against the rubric.
6. Do not look at the original source code. If you have seen it, declare that before starting.
7. When done, produce a `RECONSTRUCTION.md` at your project root scoring your implementation
   against each comparison dimension.

*Generated from `docs/ideology.md` and `docs/brief.md` by `/anchor:pairmode reconstruct`.*
*Original project: anchor*
*Generated: 2026-04-24*
