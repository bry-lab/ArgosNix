"""Kali importer.

One APT index gives us everything: package name, Homepage, Description and the
dependency sets of the `kali-tools-*` metapackages. That last part is the
valuable bit -- Kali's metapackage split *is* their curated taxonomy, and it is
far cleaner than BlackArch's groups, so we let it win on category assignment
where the two disagree.

We resolve one hop of dependencies from each metapackage. Deeper resolution
pulls in libc and the rest of Debian; the tools we want are direct dependencies
by construction.
"""

from __future__ import annotations

import gzip
import re

from ..catalog import Tool
from ..http import get
from ..identity import normalise, slugify
from ..taxonomy import Taxonomy

MIRROR = "https://http.kali.org/kali"
SUITE = "kali-rolling"
COMPONENT = "main"
ARCH = "amd64"

# kali-tools-* metapackage suffix -> upstream group name used in taxonomy.maps
METAPACKAGES = {
    "information-gathering": "kali-information-gathering",
    "vulnerability": "kali-exploitation-tools",
    "web": "kali-web",
    "database": "kali-web",
    "passwords": "kali-passwords",
    "wireless": "kali-802-11",
    "reverse-engineering": "kali-reverse-engineering",
    "exploitation": "kali-exploitation-tools",
    "social-engineering": "kali-exploitation-tools",
    "sniffing-spoofing": "kali-sniffing-spoofing",
    "post-exploitation": "kali-post-exploitation",
    "forensics": "kali-forensics",
    "reporting": "kali-reporting-tools",
    "windows-resources": "kali-windows-resources",
    "crypto-stego": "kali-crypto-stego",
    "sdr": "kali-sdr",
    "hardware": "kali-hardware",
    "fuzzing": "kali-web",
    "voip": "kali-sniffing-spoofing",
    "detect": "kali-forensics",
    "protect": "kali-forensics",
}

_VERSIONED = re.compile(r"\s*\(.*?\)")
_ALTERNATIVE = re.compile(r"\s*\|\s*")


def fetch_index() -> str:
    url = f"{MIRROR}/dists/{SUITE}/{COMPONENT}/binary-{ARCH}/Packages.gz"
    return gzip.decompress(get(url)).decode("utf-8", errors="replace")


def parse_index(text: str) -> dict[str, dict[str, str]]:
    """Debian control paragraphs -> {package: {field: value}}."""
    packages: dict[str, dict[str, str]] = {}
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        fields: dict[str, str] = {}
        key = None
        for line in block.splitlines():
            if line.startswith((" ", "\t")) and key:
                fields[key] += " " + line.strip()
            elif ":" in line:
                key, _, val = line.partition(":")
                key = key.strip()
                fields[key] = val.strip()
        name = fields.get("Package")
        if name:
            packages[name] = fields
    return packages


def _depends(field: str) -> list[str]:
    out = []
    for part in field.split(","):
        part = _VERSIONED.sub("", part).strip()
        if not part:
            continue
        # 'foo | bar' -> take the first alternative, it is Kali's preference
        out.append(_ALTERNATIVE.split(part)[0].strip())
    return out


def collect(taxonomy: Taxonomy, *, limit: int | None = None):
    index = parse_index(fetch_index())
    groups: dict[str, set[str]] = {}

    for suffix, upstream_group in METAPACKAGES.items():
        meta = index.get(f"kali-tools-{suffix}")
        if not meta:
            yield None, f"metapackage kali-tools-{suffix} not in index (renamed?)"
            continue
        for dep in _depends(meta.get("Depends", "")) + _depends(meta.get("Recommends", "")):
            if dep.startswith("kali-"):
                continue
            groups.setdefault(dep, set()).add(upstream_group)

    for count, (pkg, upstream_groups) in enumerate(sorted(groups.items())):
        if limit and count >= limit:
            return
        fields = index.get(pkg, {})
        homepage = fields.get("Homepage")
        identity = normalise(homepage, fallback=pkg)
        tool = Tool(
            id=slugify(pkg),
            upstream=identity.url,
            description=(fields.get("Description") or "").strip()[:200] or None,
            categories=taxonomy.resolve(sorted(upstream_groups)),
            tier=3,
            provenance={"kali": pkg},
        )
        yield tool, (None if not identity.is_synthetic else f"{pkg}: no Homepage in index")
