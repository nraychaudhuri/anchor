# Brief — anchor

> This is a one-page project brief. It answers **what** and **why**.
> Design decisions and implementation choices belong in `docs/architecture.md`.

---

## What this project produces

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

## Core beliefs

- We prefer codified policy over implicit convention, because persistent memory of decisions
  is the only thing that survives agent drift and developer forgetfulness across sessions.
- We prefer rationale-bearing records over bare rules, because a constraint without its reason
  will be violated by the first agent that encounters a situation the rule author did not anticipate.
- We prefer spec-first development over code-first development, because correctness can only
  be verified against an intent that is recorded somewhere.
- We prefer captured intent over captured code, because implementations are replaceable;
  the reasoning behind them is not.

---

## Accepted tradeoffs

- **Hook-pipe-sidebar separation** — hooks are deliberately thin relays; all heavy work
  runs in the sidebar. This means the sidebar must be running to extract decisions in real
  time. The cost: a separate terminal process the developer must manage. The benefit:
  hooks exit in milliseconds and can never corrupt state.
- **Python-only stack** — consistency and uv's fast bootstrap were preferred over polyglot
  flexibility. The cost: contributors must use Python. The benefit: one language, one test
  runner, one dependency manager across all skills.
- **Append-only lessons** — lessons.json is never destructively edited. The cost: stale
  lessons accumulate and must be manually marked incorporated. The benefit: the full
  methodology history is always auditable.

---

## Constraints

- Hooks must never make API calls, block, or write to spec files directly.
- The canonical spec format (`spec.json`) must remain stable — external tools and future
  agents depend on being able to read it without knowing anchor's internals.
- Bootstrap must never overwrite existing project files without explicit user confirmation.

---

## Not in scope

- A hosted or SaaS version of anchor — it is a local Claude Code plugin.
- Real-time collaboration between multiple developers on the same spec simultaneously.
- Automatic conflict resolution — conflicts are flagged for developer decision, not resolved
  by the system.

---

## What a second implementation must preserve

- The canonical spec format: `spec.json` with `module`, `summary`, `business_rules`,
  `non_negotiables`, `tradeoffs`, `conflicts`, and `lineage`. Any re-implementation must
  read and write this format.
- The rationale-bearing decision record: every non-negotiable and tradeoff must carry its
  reason and accepted cost, not just the rule itself.
- The hook-pipe-sidebar architecture: hooks are thin relays; the sidebar owns all extraction
  and state writing. This separation must survive any re-implementation.
- Append-only lessons: methodology improvements are never destructively edited.
- Validation before action: new development actions must be checked against prior decisions.
  Silent bypass of this check is not permitted.

---

## Operator contact

david@halfhorse.com

---

_These three documents should be sufficient for any model or toolchain to cold-start this project and reproduce a valid variant without prior session context._

- `docs/brief.md` — what and why (operator intent)
- `docs/architecture.md` — how and architectural decisions
- Current phase file from `docs/phases/` (or `docs/phase-prompts.md` for legacy projects)
