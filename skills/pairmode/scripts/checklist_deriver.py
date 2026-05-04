"""checklist_deriver.py — Derive a checklist from spec modules.

Takes a list of spec module dicts (each the content of a spec.json) and
returns a flat list of checklist items.

  - non_negotiables  → severity CRITICAL
  - business_rules   → severity HIGH

Universal items (PROTECTED FILES, STORY SCOPE, BUILD GATE) are NOT returned;
they are appended by templates directly via hardcoded Jinja2 code.

Deduplication: if the same rule text appears in multiple modules the items
are merged into one entry whose `module` field lists all source module names
joined by ", ".
"""

from __future__ import annotations


def derive_checklist(modules: list[dict]) -> list[dict]:
    """Return spec-derived checklist items from a list of spec module dicts.

    Each item is a dict::

        {
            "name": str,         # rule text (first 60 chars for display)
            "description": str,  # full rule text
            "severity": str,     # "CRITICAL" or "HIGH"
            "source": str,       # "non_negotiable" or "business_rule"
            "module": str,       # module name(s), comma-separated if merged
        }

    Deduplication is case-sensitive and based on the exact rule text.
    """
    # keyed by (source, rule_text) → list of module names
    seen: dict[tuple[str, str], list[str]] = {}

    for module in modules:
        module_name: str = module.get("module", "unknown")

        for rule in module.get("non_negotiables", []):
            key = ("non_negotiable", rule)
            seen.setdefault(key, [])
            if module_name not in seen[key]:
                seen[key].append(module_name)

        for rule in module.get("business_rules", []):
            key = ("business_rule", rule)
            seen.setdefault(key, [])
            if module_name not in seen[key]:
                seen[key].append(module_name)

    # Emit non_negotiables (CRITICAL) first, then business_rules (HIGH).
    # Within each group the order matches first-seen insertion order.
    result: list[dict] = []

    for source in ("non_negotiable", "business_rule"):
        severity = "CRITICAL" if source == "non_negotiable" else "HIGH"
        for (src, rule_text), module_names in seen.items():
            if src != source:
                continue
            result.append(
                {
                    "name": rule_text[:60],
                    "description": rule_text,
                    "severity": severity,
                    "source": source,
                    "module": ", ".join(module_names),
                }
            )

    return result
