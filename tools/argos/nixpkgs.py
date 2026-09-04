"""Resolve catalog entries against nixpkgs to promote them to tier 1.

`nix search` is the source of truth rather than a hardcoded list, because
attribute names churn (crackmapexec -> netexec was a rename in both nixpkgs and
upstream). Running `argos verify` in CI is what stops the catalog rotting.
"""

from __future__ import annotations

import json
import subprocess
from functools import lru_cache

from .catalog import Catalog, Tool
from .identity import slugify


@lru_cache(maxsize=1)
def search_index(flake: str = "nixpkgs") -> dict[str, dict]:
    """{attrPath: {pname, version, description}} for all of nixpkgs.

    Takes ~30s and a few hundred MB of RAM the first time. Cached by nix
    afterwards.
    """
    try:
        proc = subprocess.run(
            ["nix", "search", "--json", flake, "^"],
            check=True, capture_output=True, text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("nix is not on PATH; `argos verify` needs it") from exc
    raw = json.loads(proc.stdout or "{}")
    # keys look like legacyPackages.x86_64-linux.nmap
    return {k.split(".", 2)[-1]: v for k, v in raw.items()}


def exists(attr: str, index: dict[str, dict]) -> bool:
    return attr in index


def suggest(tool: Tool, index: dict[str, dict]) -> str | None:
    """Best-guess nixpkgs attribute for an unpackaged tool."""
    candidates = [tool.id, *tool.aliases, *tool.provenance.values()]
    for cand in candidates:
        slug = slugify(cand)
        for attr in (slug, slug.replace("-", ""), f"python3Packages.{slug}"):
            if attr in index:
                return attr
    # last resort: match on pname
    for attr, meta in index.items():
        if meta.get("pname") and slugify(meta["pname"]) == slugify(tool.id):
            return attr
    return None


def verify(catalog: Catalog, *, promote: bool = False) -> tuple[list[str], list[str]]:
    """Check tier-1 claims and optionally promote tier 2/3 entries that landed.

    Returns (errors, promotions).
    """
    index = search_index()
    errors: list[str] = []
    promotions: list[str] = []

    for tool in catalog:
        if tool.tier == 1:
            if not tool.nixpkgs or not exists(tool.nixpkgs, index):
                errors.append(
                    f"{tool.id}: claims nixpkgs.{tool.nixpkgs} which does not exist"
                )
            continue
        if tool.tier in (2, 3):
            found = suggest(tool, index)
            if found:
                promotions.append(f"{tool.id} -> nixpkgs.{found}")
                if promote:
                    tool.tier = 1
                    tool.nixpkgs = found
                    tool.builder = None
    return errors, promotions
