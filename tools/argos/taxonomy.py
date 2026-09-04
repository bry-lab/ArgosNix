"""The category taxonomy, and mapping upstream distro groups into it."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Category:
    key: str
    label: str
    description: str
    maps: tuple[str, ...]


@dataclass(slots=True)
class Taxonomy:
    categories: dict[str, Category]

    @classmethod
    def load(cls, root: Path) -> "Taxonomy":
        raw = tomllib.loads(
            (root / "catalog" / "taxonomy.toml").read_text(encoding="utf-8")
        )
        cats = {
            key: Category(
                key=key,
                label=body.get("label", key),
                description=body.get("description", ""),
                maps=tuple(body.get("maps", [])),
            )
            for key, body in raw.items()
        }
        return cls(categories=cats)

    def __iter__(self):
        return iter(self.categories.values())

    @property
    def keys(self) -> list[str]:
        return list(self.categories)

    def reverse_map(self) -> dict[str, list[str]]:
        """upstream group name -> our category keys."""
        index: dict[str, list[str]] = {}
        for cat in self.categories.values():
            for upstream in cat.maps:
                index.setdefault(upstream.lower(), []).append(cat.key)
        return index

    def resolve(self, upstream_groups: list[str], *, default: str = "utilities") -> list[str]:
        """Map a package's upstream groups onto our categories.

        Upstream taxonomies are noisy -- BlackArch routinely puts a tool in five
        groups -- so we cap at three and fall back to `utilities` rather than
        inventing a category.
        """
        index = self.reverse_map()
        out: list[str] = []
        for group in upstream_groups:
            for cat in index.get(group.lower().strip(), []):
                if cat not in out:
                    out.append(cat)
        return out[:3] or [default]
