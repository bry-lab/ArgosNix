"""BlackArch importer.

Best of the four sources by a wide margin: every package is a PKGBUILD with a
machine-readable `url=`, `license=`, `groups=` and `pkgdesc=`, and the ~50
`blackarch-*` groups are already a usable taxonomy. Start here when
bootstrapping the catalog -- the other three importers are then mostly diffs
against what this produces.

Strategy is a shallow clone rather than the GitHub API: ~2,800 packages means
~2,800 API calls and a rate limit, versus one clone of a few hundred MB.

PKGBUILDs are bash. We deliberately do NOT execute them. The fields we want are
overwhelmingly literal assignments, and a regex parser that skips the 3% it
cannot understand is far preferable to sourcing untrusted shell from a security
tooling repo. Skipped entries are reported, not silently dropped.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..catalog import Tool
from ..identity import normalise, slugify
from ..taxonomy import Taxonomy

REPO = "https://github.com/BlackArch/blackarch.git"
CLONE = Path(".cache/repos/blackarch")

_ASSIGN = re.compile(
    r"^(?P<key>pkgname|pkgdesc|url|license|groups|arch)\s*=\s*(?P<val>.*)$",
    re.MULTILINE,
)
_ARRAY = re.compile(r"^\((?P<body>.*)\)$", re.DOTALL)
_WORD = re.compile(r"'([^']*)'|\"([^\"]*)\"|(\S+)")

BUILDER_HINTS = {
    "go": re.compile(r"\bgo (build|install)\b|go\.mod"),
    "rust": re.compile(r"\bcargo (build|install)\b|Cargo\.toml"),
    "python": re.compile(r"python3? (setup\.py|-m build|-m installer)|pyproject\.toml"),
    "python2": re.compile(r"python2 setup\.py"),
    "ruby": re.compile(r"\bgem (build|install)\b"),
    "node": re.compile(r"\bnpm (install|run)\b|package\.json"),
    "cmake": re.compile(r"\bcmake\b"),
    "autotools": re.compile(r"\./configure\b|autoreconf"),
    "make": re.compile(r"^\s*make\b", re.MULTILINE),
}


def sync(*, offline: bool = False) -> Path:
    """Shallow-clone or update the BlackArch tree."""
    CLONE.parent.mkdir(parents=True, exist_ok=True)
    if CLONE.is_dir():
        if not offline:
            subprocess.run(
                ["git", "-C", str(CLONE), "fetch", "--depth", "1", "origin", "master"],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(CLONE), "reset", "--hard", "FETCH_HEAD"],
                check=True, capture_output=True,
            )
        return CLONE
    if offline:
        raise FileNotFoundError(f"{CLONE} absent and --offline was requested")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--filter=blob:none", REPO, str(CLONE)],
        check=True,
    )
    return CLONE


def parse_pkgbuild(text: str) -> dict[str, list[str] | str]:
    out: dict[str, list[str] | str] = {}
    for match in _ASSIGN.finditer(text):
        key, val = match.group("key"), match.group("val").strip()
        arr = _ARRAY.match(val)
        if arr:
            words = [
                (a or b or c)
                for a, b, c in _WORD.findall(arr.group("body"))
                if (a or b or c)
            ]
            out[key] = [w for w in words if not w.startswith("#")]
        else:
            out[key] = val.strip("'\"")
    return out


def guess_builder(text: str) -> str | None:
    for name, pattern in BUILDER_HINTS.items():
        if pattern.search(text):
            return name
    return None


def collect(taxonomy: Taxonomy, *, offline: bool = False, limit: int | None = None):
    """Yield (Tool, warning|None) for every BlackArch package."""
    root = sync(offline=offline)
    pkgbuilds = sorted(root.glob("packages/*/PKGBUILD"))
    if limit:
        pkgbuilds = pkgbuilds[:limit]

    for path in pkgbuilds:
        text = path.read_text(encoding="utf-8", errors="replace")
        fields = parse_pkgbuild(text)

        raw_name = fields.get("pkgname") or path.parent.name
        name = raw_name[0] if isinstance(raw_name, list) else raw_name
        pkg = path.parent.name

        url = fields.get("url")
        if isinstance(url, list):
            url = url[0] if url else None
        if url and "$" in url:
            url = None  # unresolved bash variable; not worth guessing

        groups = fields.get("groups") or []
        if isinstance(groups, str):
            groups = [groups]
        categories = taxonomy.resolve(list(groups))

        licenses = fields.get("license") or []
        if isinstance(licenses, str):
            licenses = [licenses]

        desc = fields.get("pkgdesc")
        if isinstance(desc, list):
            desc = desc[0] if desc else None

        identity = normalise(url, fallback=name)
        tool = Tool(
            id=slugify(name),
            upstream=identity.url,
            description=(desc or None),
            license=(licenses[0] if licenses else None),
            categories=categories,
            tier=3,
            builder=guess_builder(text),
            provenance={"blackarch": pkg},
        )
        warning = None
        if identity.is_synthetic:
            warning = f"{pkg}: no usable url= in PKGBUILD"
        elif not groups:
            warning = f"{pkg}: no groups=, category is a guess"
        yield tool, warning
