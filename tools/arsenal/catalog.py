"""Load, validate, merge and write the tool catalog.

Deliberately stdlib-only. This runs in CI, in a Nix build sandbox and on
whatever laptop a contributor has, and a dependency tree is a liability for
something whose entire job is to be boring and reproducible.

Storage is one TOML file per leading letter under catalog/tools/. That keeps
diffs reviewable and merge conflicts local -- a single 3,000-entry file would
be unmergeable in practice.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Iterator

from .identity import Identity, is_valid_id, normalise, shard_for

VALID_TIERS = {1, 2, 3, 4}
VALID_BUILDERS = {
    "go", "rust", "python", "python2", "ruby", "node", "cmake",
    "autotools", "make", "script", "java", "dotnet", "other",
}
VALID_CAPS = {"raw-socket", "net-admin", "packet-capture", "usb", "kvm", "root"}
VALID_STATUS = {"active", "unmaintained", "archived", "superseded"}
DISTROS = ("kali", "blackarch", "remnux", "athena")

# Order matters: this is the on-disk field order, chosen so a diff reads well.
FIELD_ORDER = [
    "upstream", "description", "license", "categories", "tier", "nixpkgs",
    "local", "builder", "unfree", "platforms", "capabilities", "alternatives",
    "aliases", "status", "notes", "provenance",
]


@dataclass(slots=True)
class Tool:
    id: str
    upstream: str
    categories: list[str] = field(default_factory=list)
    tier: int = 3
    description: str | None = None
    license: str | None = None
    nixpkgs: str | None = None
    local: str | None = None
    builder: str | None = None
    unfree: bool = False
    platforms: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    status: str = "active"
    notes: str | None = None
    provenance: dict[str, str] = field(default_factory=dict)

    @property
    def identity(self) -> Identity:
        return normalise(self.upstream, fallback=self.id)

    @property
    def attr(self) -> str | None:
        """The Nix attribute that provides this tool, if any."""
        if self.tier == 1 and self.nixpkgs:
            return self.nixpkgs
        if self.local:
            return self.local
        return None

    @property
    def packaged(self) -> bool:
        return self.attr is not None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key in FIELD_ORDER:
            val = getattr(self, key)
            if val in (None, "", [], {}, False):
                continue
            if key == "status" and val == "active":
                continue
            out[key] = val
        return out


class CatalogError(Exception):
    pass


@dataclass(slots=True)
class Catalog:
    tools: dict[str, Tool] = field(default_factory=dict)

    # -- io ---------------------------------------------------------------

    @classmethod
    def load(cls, root: Path) -> "Catalog":
        cat = cls()
        tools_dir = root / "catalog" / "tools"
        if not tools_dir.is_dir():
            return cat
        for path in sorted(tools_dir.glob("*.toml")):
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
            for tool_id, body in raw.items():
                if tool_id in cat.tools:
                    raise CatalogError(f"duplicate id {tool_id!r} (second in {path})")
                cat.tools[tool_id] = _tool_from(tool_id, body, path)
        return cat

    def save(self, root: Path) -> list[Path]:
        tools_dir = root / "catalog" / "tools"
        tools_dir.mkdir(parents=True, exist_ok=True)
        shards: dict[str, list[Tool]] = {}
        for tool in self.tools.values():
            shards.setdefault(shard_for(tool.id), []).append(tool)

        written: list[Path] = []
        for shard, tools in sorted(shards.items()):
            path = tools_dir / f"{shard}.toml"
            body = [
                "# Generated and maintained by `arsenal` -- see tools/README.md.",
                "# Hand edits are fine; run `arsenal fmt` afterwards to normalise.",
                "",
            ]
            for tool in sorted(tools, key=lambda t: t.id):
                body.append(f"[{_key(tool.id)}]")
                for key, val in tool.to_dict().items():
                    if key == "provenance":
                        continue
                    body.append(f"{key} = {_toml_value(val)}")
                if tool.provenance:
                    prov = ", ".join(
                        f"{d} = {_toml_value(tool.provenance[d])}"
                        for d in DISTROS
                        if d in tool.provenance
                    )
                    body.append(f"provenance = {{ {prov} }}")
                body.append("")
            path.write_text("\n".join(body), encoding="utf-8")
            written.append(path)

        # Drop shards that no longer have entries.
        for path in tools_dir.glob("*.toml"):
            if path not in written:
                path.unlink()
        return written

    # -- access -----------------------------------------------------------

    def __iter__(self) -> Iterator[Tool]:
        return iter(self.tools.values())

    def __len__(self) -> int:
        return len(self.tools)

    def by_identity(self) -> dict[str, Tool]:
        index: dict[str, Tool] = {}
        for tool in self.tools.values():
            index[tool.identity.url] = tool
        return index

    def by_alias(self) -> dict[str, Tool]:
        index: dict[str, Tool] = {}
        for tool in self.tools.values():
            for name in [tool.id, *tool.aliases, *tool.provenance.values()]:
                index.setdefault(name.lower(), tool)
        return index

    def in_category(self, category: str) -> list[Tool]:
        return sorted(
            (t for t in self.tools.values() if category in t.categories),
            key=lambda t: t.id,
        )

    # -- mutation ---------------------------------------------------------

    def upsert(self, incoming: Tool, *, source: str | None = None) -> tuple[Tool, str]:
        """Merge an importer-produced Tool into the catalog.

        Returns (tool, action) where action is 'added', 'merged' or 'unchanged'.
        Existing hand-curated fields always win; importers may only fill blanks
        and extend provenance. That rule is what makes re-running an importer
        safe.
        """
        by_ident = self.by_identity()
        by_alias = self.by_alias()

        existing: Tool | None = None
        if not incoming.identity.is_synthetic:
            existing = by_ident.get(incoming.identity.url)
        if existing is None:
            for name in [incoming.id, *incoming.aliases]:
                existing = by_alias.get(name.lower())
                if existing is not None:
                    break

        if existing is None:
            tool_id = incoming.id
            suffix = 2
            while tool_id in self.tools:
                tool_id = f"{incoming.id}-{suffix}"
                suffix += 1
            self.tools[tool_id] = replace(incoming, id=tool_id)
            return self.tools[tool_id], "added"

        changed = False
        for key in ("description", "license", "builder", "notes"):
            if getattr(existing, key) in (None, "") and getattr(incoming, key):
                setattr(existing, key, getattr(incoming, key))
                changed = True

        for cat in incoming.categories:
            if cat not in existing.categories and len(existing.categories) < 4:
                existing.categories.append(cat)
                changed = True

        for alias in [incoming.id, *incoming.aliases]:
            if alias != existing.id and alias not in existing.aliases:
                existing.aliases.append(alias)
                changed = True

        for distro, name in incoming.provenance.items():
            if existing.provenance.get(distro) != name:
                existing.provenance[distro] = name
                changed = True

        if source and existing.upstream.startswith("urn:") and not incoming.identity.is_synthetic:
            existing.upstream = incoming.upstream
            changed = True

        return existing, "merged" if changed else "unchanged"

    # -- validation -------------------------------------------------------

    def validate(self, categories: Iterable[str]) -> list[str]:
        known = set(categories)
        errors: list[str] = []
        seen_identity: dict[str, str] = {}

        for tool in sorted(self.tools.values(), key=lambda t: t.id):
            where = f"{tool.id}:"
            if not is_valid_id(tool.id):
                errors.append(f"{where} id must match [a-z0-9][a-z0-9._+-]*")
            if tool.tier not in VALID_TIERS:
                errors.append(f"{where} tier {tool.tier} not in {sorted(VALID_TIERS)}")
            if not tool.categories:
                errors.append(f"{where} needs at least one category")
            if len(tool.categories) > 4:
                errors.append(f"{where} more than 4 categories is meaningless")
            for cat in tool.categories:
                if cat not in known:
                    errors.append(f"{where} unknown category {cat!r}")
            if tool.tier == 1 and not tool.nixpkgs:
                errors.append(f"{where} tier 1 requires a `nixpkgs` attribute")
            if tool.tier == 4 and tool.attr:
                errors.append(f"{where} tier 4 must not claim a package attribute")
            if tool.builder and tool.builder not in VALID_BUILDERS:
                errors.append(f"{where} unknown builder {tool.builder!r}")
            if tool.status not in VALID_STATUS:
                errors.append(f"{where} unknown status {tool.status!r}")
            for cap in tool.capabilities:
                if cap not in VALID_CAPS:
                    errors.append(f"{where} unknown capability {cap!r}")
            for distro in tool.provenance:
                if distro not in DISTROS:
                    errors.append(f"{where} unknown distro {distro!r} in provenance")
            for alt in tool.alternatives:
                if alt not in self.tools:
                    errors.append(f"{where} alternative {alt!r} is not a catalog id")

            ident = tool.identity
            if not ident.is_synthetic:
                prior = seen_identity.get(ident.url)
                if prior:
                    errors.append(
                        f"{where} shares upstream {ident.url} with {prior!r} "
                        f"-- merge them or differentiate the upstream"
                    )
                else:
                    seen_identity[ident.url] = tool.id

        return errors


def _tool_from(tool_id: str, body: dict[str, Any], path: Path) -> Tool:
    unknown = set(body) - set(FIELD_ORDER)
    if unknown:
        raise CatalogError(f"{path}: {tool_id} has unknown keys {sorted(unknown)}")
    if "upstream" not in body:
        raise CatalogError(f"{path}: {tool_id} is missing `upstream`")
    return Tool(
        id=tool_id,
        upstream=body["upstream"],
        categories=list(body.get("categories", [])),
        tier=int(body.get("tier", 3)),
        description=body.get("description"),
        license=body.get("license"),
        nixpkgs=body.get("nixpkgs"),
        local=body.get("local"),
        builder=body.get("builder"),
        unfree=bool(body.get("unfree", False)),
        platforms=list(body.get("platforms", [])),
        capabilities=list(body.get("capabilities", [])),
        alternatives=list(body.get("alternatives", [])),
        aliases=list(body.get("aliases", [])),
        status=body.get("status", "active"),
        notes=body.get("notes"),
        provenance=dict(body.get("provenance", {})),
    )


def _key(name: str) -> str:
    return name if is_valid_id(name) and "." not in name else f'"{name}"'


def _toml_value(val: Any) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, str):
        escaped = val.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(val, list):
        return "[" + ", ".join(_toml_value(v) for v in val) + "]"
    raise CatalogError(f"cannot serialise {val!r}")
