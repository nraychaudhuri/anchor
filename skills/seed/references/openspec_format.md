# Spec Format Reference

## Directory Structure

```
<spec_location>/
  openspec/
    specs/
      <module-name>/
        spec.json        ← canonical spec per module (machine-readable)
    changes/
      <session-id>/
        proposal.md      ← human-readable: what was planned
        design.md        ← human-readable: tradeoffs and decisions
        extraction.json  ← structured extraction used by reconciler
    conflicts_pending.json
```

## spec.json Format

Each module has one `spec.json`. This is the source of truth the Architect,
Historian, and Validator all read from.

```json
{
  "module": "auth",
  "last_updated": "2026-03-29",
  "summary": "Concise description of what this module does and owns. 2-4 sentences. Architecture and behavior level only.",
  "business_rules": [
    "All API endpoints except /public require a valid JWT",
    "JWT must include company_id for multi-tenant routing"
  ],
  "non_negotiables": [
    "Google refresh tokens must be stored encrypted, never in plaintext",
    "Rate limiting cannot be disabled in production"
  ],
  "tradeoffs": [
    {
      "decision": "HS256 over RS256 for JWT signing",
      "reason": "Simpler at current scale, no need for public key distribution",
      "accepted_cost": "Cannot verify tokens without the shared secret"
    }
  ],
  "conflicts": [],
  "lineage": [
    {
      "session_id": "8fdc6432-...",
      "summary": "Auth design session — JWT structure and MFA",
      "date": "2026-03-15",
      "resume": "claude --resume 8fdc6432-...",
      "what_changed": "Established JWT claims structure and MFA flow",
      "key_decisions": [
        "JWT includes company_id for multi-tenant routing",
        "WebAuthn as primary MFA, TOTP as fallback"
      ]
    }
  ]
}
```

## Field Rules

**summary** — rewritten each reconcile run. Architecture level only. No implementation details.

**business_rules** — plain strings at product/architecture level.
  Good: "Orders are immutable after confirmation"
  Bad: "DynamoDB PutItem with ConditionExpression checks status field"

**non_negotiables** — absolute constraints. The project's "allergies".

**tradeoffs** — keep these forever. They explain why the code looks the way it does.

**conflicts** — populated by reconciler when sessions contradict each other.
Resolve by editing spec.json and removing the conflict entry.

**lineage** — append-only. One entry per planning session that touched this module.
Never modified after written. The resume field links back to the exact session.

## changes/ directory (human-readable session history)

proposal.md and design.md stay as markdown — for humans to read.
extraction.json is what the reconciler uses.

### proposal.md
```markdown
# <Session purpose>

## Session
- ID: `<session-id>`
- Summary: "<summary>"
- Date: <date>
- Project: <project path>
- Resume: `claude --resume <session-id>`

## What Was Planned
<brief description>

## Options Considered and Rejected
- <option>: <reason rejected>
```

### design.md
```markdown
# Design Decisions

## Tradeoffs
### <Decision>
**Chose:** ...  **Because:** ...  **Accepted cost:** ...

## Ruled Out
### <Option>
**Rejected:** ...  **Because:** ...
```
