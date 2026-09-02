"""Profile resolution.

This mirrors nix/profiles.nix exactly. Two implementations of the same logic is
a smell, but the alternative is making the CLI shell out to nix for every
query, and contributors on macOS without nix installed still need to be able to
ask "what is in the dfir profile". The `profiles-resolve` flake check evaluates
every profile through the Nix path, so a divergence fails CI.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .catalog import Catalog, Tool

DEFAULT_TIERS = (1, 2, 3)


@dataclass(slots=True)
class Profile:
    name: str
    description: str = ""
    categories: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    tiers: tuple[int, ...] = DEFAULT_TIERS
    unfree: bool = False

    @property
    def is_wildcard(self) -> bool:
        return "*" in self.categories


def load(root: Path) -> dict[str, Profile]:
    raw = tomllib.loads(
        (root / "catalog" / "profiles.toml").read_text(encoding="utf-8")
    )
    return {
        name: Profile(
            name=name,
            description=body.get("description", ""),
            categories=list(body.get("categories", [])),
            extra=list(body.get("extra", [])),
            exclude=list(body.get("exclude", [])),
            tiers=tuple(body.get("tiers", DEFAULT_TIERS)),
            unfree=bool(body.get("unfree", False)),
        )
        for name, body in raw.items()
    }


def resolve(profile: Profile, catalog: Catalog) -> list[Tool]:
    """Tools a profile should contain, in catalog-id order.

    Unpackaged tools are included here on purpose -- the CLI wants to show them
    as gaps. nix/profiles.nix filters them out, because a missing attribute is
    an evaluation error rather than a warning.
    """
    excluded = set(profile.exclude)
    selected: dict[str, Tool] = {}

    for tool in catalog:
        if tool.id in excluded:
            continue
        if tool.tier not in profile.tiers:
            continue
        if tool.unfree and not profile.unfree:
            continue
        if tool.status == "superseded":
            continue
        in_scope = profile.is_wildcard or any(
            c in profile.categories for c in tool.categories
        )
        if in_scope:
            selected[tool.id] = tool

    for extra_id in profile.extra:
        tool = catalog.tools.get(extra_id)
        if tool and tool.id not in excluded:
            selected[tool.id] = tool

    return sorted(selected.values(), key=lambda t: t.id)


def summarise(profile: Profile, catalog: Catalog) -> dict:
    tools = resolve(profile, catalog)
    packaged = [t for t in tools if t.packaged]
    return {
        "name": profile.name,
        "description": profile.description,
        "tools": len(tools),
        "packaged": len(packaged),
        "missing": len(tools) - len(packaged),
        "percent": round(100 * len(packaged) / len(tools), 1) if tools else 0.0,
    }
