"""denylist_deriver.py — Derive a deny list from spec modules.

Takes a list of spec module dicts (each the content of a spec.json) and a
module_paths dict mapping module name → list of path strings (from
.companion/modules.json), then returns a flat list of deny rule dicts.

Each rule dict has the shape::

    {
        "path_pattern": str,       # e.g. "Edit(src/services/auth/**)"
        "non_negotiable": str,     # full text of the triggering non-negotiable
        "module": str,             # module name the rule came from
    }

One dict is emitted per tool × path combination (Edit + Write → two dicts per
path).

Trigger keywords (any match → protect the module's paths):
  "must never", "must not", "protected", "immutable", "isolation", "never"

Concept keywords that extend protection to paths containing that word in their
path string:
  "auth", "schema", "engine"

The deriver does NOT write comments into settings.json (JSON does not support
comments).  bootstrap.py is responsible for writing both the settings.json deny
array and a companion settings.deny-rationale.json file.
"""

from __future__ import annotations

_PROTECTION_KEYWORDS: tuple[str, ...] = (
    "must never",
    "must not",
    "protected",
    "immutable",
    "isolation",
    "never",
)

_CONCEPT_KEYWORDS: tuple[str, ...] = ("auth", "schema", "engine")

_DENY_TOOLS: tuple[str, ...] = ("Edit", "Write")


def _nn_triggers_protection(non_negotiable: str) -> bool:
    """Return True if the non-negotiable text contains any protection keyword."""
    lower = non_negotiable.lower()
    return any(kw in lower for kw in _PROTECTION_KEYWORDS)


def _nn_mentions_concept(non_negotiable: str, concept: str) -> bool:
    """Return True if the non-negotiable text mentions the given concept word."""
    return concept in non_negotiable.lower()


def _make_rules(path: str, non_negotiable: str, module: str) -> list[dict]:
    """Emit one Edit and one Write deny rule for the given path."""
    path = path.rstrip("/")
    return [
        {
            "path_pattern": f"{tool}({path}/**)",
            "non_negotiable": non_negotiable,
            "module": module,
        }
        for tool in _DENY_TOOLS
    ]


def derive_denylist(
    modules: list[dict],
    module_paths: dict[str, list[str]],
) -> list[dict]:
    """Return deny rules derived from spec module non-negotiables.

    Parameters
    ----------
    modules:
        List of spec.json dicts (each has at minimum "module" and
        "non_negotiables" keys).
    module_paths:
        Mapping of module name → list of path strings (from modules.json).
        Paths should be directory-level strings like "src/services/auth".

    Returns
    -------
    list of dicts, each with keys "path_pattern", "non_negotiable", "module".
    Duplicates (same path_pattern + non_negotiable) are deduplicated.
    """
    rules: list[dict] = []
    seen: set[tuple[str, str]] = set()  # (path_pattern, non_negotiable)

    def _add(path_pattern: str, non_negotiable: str, module_name: str) -> None:
        key = (path_pattern, non_negotiable)
        if key not in seen:
            seen.add(key)
            rules.append(
                {
                    "path_pattern": path_pattern,
                    "non_negotiable": non_negotiable,
                    "module": module_name,
                }
            )

    for module in modules:
        module_name: str = module.get("module", "unknown")
        paths: list[str] = module_paths.get(module_name, [])

        for nn in module.get("non_negotiables", []):
            if not _nn_triggers_protection(nn):
                continue

            # Protect all paths belonging to this module.
            for path in paths:
                clean = path.rstrip("/")
                for tool in _DENY_TOOLS:
                    _add(f"{tool}({clean}/**)", nn, module_name)

            # Concept-based cross-module path matching: if the non-negotiable
            # mentions a concept keyword, also protect paths in *any* module
            # whose path string contains that concept word.
            for concept in _CONCEPT_KEYWORDS:
                if not _nn_mentions_concept(nn, concept):
                    continue
                # Scan all module paths for paths that contain the concept word.
                for other_module_name, other_paths in module_paths.items():
                    for path in other_paths:
                        if concept in path.lower():
                            clean = path.rstrip("/")
                            for tool in _DENY_TOOLS:
                                _add(f"{tool}({clean}/**)", nn, module_name)

    return rules
