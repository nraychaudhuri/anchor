# Ideology — anchor

> This document captures the **intent layer** beneath the implementation.
> It records convictions, tradeoffs, and constraints in a form that survives across
> implementations, agents, and sessions.
>
> A reconstruction agent given only this document and `docs/brief.md` should be able to
> produce an implementation that is recognizably this project — different in form, identical
> in values.
>
> Fill this in before the first story if starting fresh. Fill it in by extracting from the
> existing implementation if a prototype already exists.

---

## Core convictions

> What does this project believe? State each conviction as a positive claim: "we prefer X over Y
> because Z." These are not rules — they are the values from which rules derive.
> A conviction should be strong enough to resolve a tradeoff when two good options conflict.

<!--
Examples:
- "We prefer explicit configuration over inferred defaults, because configuration that can be
  read is configuration that can be understood by the next agent."
- "We prefer correctness over performance at this stage, because an incorrect fast system
  cannot be trusted to optimize."
- "We prefer small composable functions over large orchestrators, because the unit of
  replaceability matters more than the unit of convenience."

Add one conviction per bullet. State the preference and the reason. Three to seven convictions
is the right range — fewer suggests the ideology is underdeveloped; more suggests it is not
actually a set of convictions but a list of preferences.
-->



- We prefer codifying policy over implicit convention, because persistent memory of decisions, specs, and constraints is the only thing that survives agent drift and developer forgetfulness across sessions.

- We prefer rationale-bearing decisions over bare rules, because a constraint without a reason will be violated by the first agent that encounters a situation the rule author did not anticipate.

- We prefer spec-first development over code-first development, because correctness can only be verified against an intent that is recorded somewhere.



---

## Value hierarchy

> When values conflict, which wins? Record the priority order and the reasoning.
> This section is most useful when populated from real conflict — a moment when two
> good values pointed in opposite directions and a decision was made.

<!--
Format each entry as:
  [Higher value] over [lower value] — [the situation where this matters] — [why]

Examples:
- "Auditability over convenience — when logging a decision requires extra code, write
  the extra code. A system that cannot explain itself cannot be trusted."
- "Backward compatibility over refactoring clarity — at this stage, existing integrations
  must not break. Clean-up is for a future phase when the API surface is stable."
- "Reversibility over speed — prefer designs where bad decisions can be undone. Move fast
  in a direction that can be walked back."
-->



- Decision fidelity over convenience — when recording a decision requires extra structure, write the structure. A system that silently drops context cannot be trusted.

- Validation against prior decisions over speed — new actions must be checked against the canonical spec before proceeding. A fast but drifting agent is worse than a slow but coherent one.

- Persistent intent over implementation detail — the spec captures why, not how. Implementations are replaceable; the reasoning behind them is not.



---

## Accepted constraints

> Non-negotiables with their rationale. Not just the rule — the reason the rule exists
> and what it protects. A constraint without a rationale will be violated by the first
> agent that encounters a situation the rule author did not anticipate.

<!--
Format each entry as:

### [Constraint name]

**Rule:** [What must never happen, or what must always be true]

**Protects:** [What breaks, degrades, or becomes untrustworthy if this constraint is violated]

**Rationale:** [Why this protection is worth the cost it imposes]

**Override path:** [Under what conditions, if any, can this constraint be deliberately overridden?
  If never: say "no override permitted." If conditional: describe the gate.]
-->



### Never silently pass contradictions

**Rule:** anchor must never allow a development action to proceed without validating it against previous decisions recorded in the canonical spec.

**Protects:** The core contract of the system. If anchor lets contradictions pass silently, developers lose trust in the spec and stop using it — making the entire system worthless.

**Rationale:** The value of a persistent memory system is precisely that it catches what humans and agents forget. A system that misses contradictions provides false confidence, which is worse than no system.

**Override path:** A developer may explicitly acknowledge a conflict and record an override reason in spec.json conflicts before proceeding. Silent bypass is never permitted.


### Hooks are thin relays only

**Rule:** Hook scripts must emit to the pipe and exit. No API calls, no spec writes, no blocking logic in hooks.

**Protects:** Session performance and architectural clarity. Hooks that block or write state create race conditions, slow sessions, and violate the layered architecture.

**Rationale:** The sidebar owns all heavy work. The hook-pipe-sidebar separation is the core architectural boundary in anchor. Violating it collapses two roles into one and makes the system unauditable.

**Override path:** No override permitted. If a hook needs to do more work, that work belongs in the sidebar, triggered by a pipe message.


### Sidebar owns all state writes

**Rule:** Only sidebar.py and skill scripts may write to spec files, openspec directories, or .companion/ state. Hooks write only to the pipe.

**Protects:** Data integrity and auditability. If hooks write state directly, the sidebar's view of the world diverges from actual state, causing silent corruption.

**Rationale:** Single-writer ownership is the only reliable way to prevent race conditions in a system with concurrent hook events and sidebar processing.

**Override path:** No override permitted.




---

## Prototype fingerprints

> If this ideology document was written after a prototype already exists, record the patterns,
> habits, and choices in the prototype that reflect the developer's style rather than the
> project's values. A reconstruction agent should understand which patterns are free to change.
>
> If this document was written before any prototype: leave this section blank and fill it
> in during or after the first implementation.

<!--
The goal is to distinguish "this is how we believe the system should work" from "this is
how I happen to build things." A reconstruction agent that inherits only the fingerprints
without knowing they are fingerprints will treat them as constraints. Name them explicitly
so they can be questioned.

Format:

### [Pattern name]

**Observed in prototype:** [Where in the codebase this pattern appears]

**Why it exists:** [Developer preference? Convenience? Legacy? Genuine conviction?]

**Free to change?** Yes / Conditional / No — [reason]
-->



### Python everywhere

**Observed in prototype:** All skill scripts, hook scripts, and tests are Python. No JavaScript, no shell scripts for logic.

**Why it exists:** Developer preference and consistency. uv makes Python fast to bootstrap.

**Free to change?** Conditional — the canonical spec format (spec.json) and pipe protocol must remain stable regardless of implementation language. The language itself is free to change.


### Jinja2 for template rendering

**Observed in prototype:** All pairmode scaffold templates use Jinja2 (.j2 extension).

**Why it exists:** Developer familiarity and expressiveness. Jinja2 handles conditionals and loops that plain string templates cannot.

**Free to change?** Yes — any templating system that produces the same output is acceptable.




---

## Reconstruction guidance

> Instructions for an agent reconstructing this system from ideology alone — without access
> to the original source code.

### Must preserve

> These elements are non-negotiable. An implementation that omits or contradicts them is
> not this project.



- The canonical spec format: spec.json with module, summary, business_rules, non_negotiables, tradeoffs, conflicts, and lineage. Any re-implementation must read and write this format.

- The rationale-bearing decision record: every non-negotiable and tradeoff must carry its reason and accepted cost, not just the rule itself.

- The hook-pipe-sidebar architecture: hooks are thin relays; the sidebar owns all extraction and state writing. This separation must survive any re-implementation.

- Append-only lessons: methodology improvements are never destructively edited — only extended and status-updated.



### Should question

> These elements are present in the current implementation but may not be the best approach.
> A reconstruction agent is encouraged to find a better solution — and should justify the
> change against the core convictions above.



- Whether Jinja2 templates are the right abstraction for scaffold generation — a code-generation approach with structured types might be more refactorable.

- Whether the two-hop product.json → config.json → spec_location path is worth the indirection, or whether a single config file suffices.

- Whether the lessons.json append-only format scales, or whether a database-backed store would serve audit and review better at larger lesson volumes.



### Free to change

> Implementation details the reconstruction agent should feel no obligation to preserve.
> These were choices, not values.



- Implementation language (Python is a fingerprint, not a conviction).

- Template engine (Jinja2 is convenient, not architecturally required).

- File layout within skills/ — the public interface is the SKILL.md contract, not the internal directory structure.

- Test framework — pytest is a preference, not a constraint.

- The Rich TUI in sidebar.py — the sidebar's display is cosmetic; its pipe-reading and extraction loop are not.



---

## Comparison basis

> When two implementations are compared against this ideology, these are the dimensions that
> matter. Used by the comparison rubric to evaluate which implementation is better aligned
> with intent.

<!--
List three to five dimensions. Each should be a quality that can be assessed from reading
the code — not a feature checklist. Examples:
- "Constraint traceability: can a reader determine why a given protection exists?"
- "Intent legibility: does the code explain what it is protecting and why?"
- "Lesson integration: does the system make it easy to learn from failures?"
-->



- **Decision fidelity:** Does the implementation reliably capture and surface contradictions with prior decisions? A system that misses conflicts fails its core contract.

- **Rationale preservation:** Do recorded decisions carry their why? An implementation that stores rules without rationale degrades into a list of arbitrary constraints.

- **Architectural layering:** Is the hook-pipe-sidebar separation maintained? Collapse of this boundary is the most common failure mode.

- **Blank-slate reconstructability:** Given only the ideology and brief, could a new agent produce a system that satisfies the same canonical spec contract?



---

*This document is a companion to `docs/brief.md` (what and why) and `docs/architecture.md`
(how). Together they form the complete ideology record for anchor.*

*Last reviewed: 2026-04-24*