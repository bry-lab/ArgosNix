"""REMnux importer.

REMnux is SaltStack states rather than a package repo, so there is no index to
diff against -- the states *are* the manifest. Directory layout under the
states tree doubles as the category, which is convenient, and the `pkg.installed`
/ `pip.installed` / `cmd.run` declarations tell us the builder.

REMnux is the smallest of the four sources but contributes the most *unique*
tools: its malware and document-analysis coverage barely overlaps with Kali or
BlackArch, so expect a high add rate and a low merge rate here.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..catalog import Tool
from ..identity import normalise, slugify
from ..taxonomy import Taxonomy

REPO = "https://github.com/REMnux/salt-states.git"
CLONE = Path(".cache/repos/remnux")

_PKG_BLOCK = re.compile(
    r"^(?P<name>[\w.\-/]+):\s*\n(?P<body>(?:[ \t]+.*\n?)+)", re.MULTILINE
)
_SOURCE = re.compile(r"https?://[^\s'\"]+")

DIR_TO_GROUP = {
    "malware": "remnux-malware",
    "documents": "remnux-documents",
    "memory": "remnux-memory",
    "network": "remnux-network",
    "reversing": "remnux-reversing",
    "scripts": "remnux-scripts",
    "static": "remnux-malware",
    "dynamic": "remnux-malware",
    "browser": "remnux-scripts",
}

BUILDER_BY_STATE = {
    "pip.installed": "python",
    "gem.installed": "ruby",
    "npm.installed": "node",
    "pkg.installed": None,
    "cmd.run": None,
}


def sync(*, offline: bool = False) -> Path:
    CLONE.parent.mkdir(parents=True, exist_ok=True)
    if CLONE.is_dir():
        if not offline:
            subprocess.run(["git", "-C", str(CLONE), "pull", "--ff-only"],
                           check=True, capture_output=True)
        return CLONE
    if offline:
        raise FileNotFoundError(f"{CLONE} absent and --offline was requested")
    subprocess.run(["git", "clone", "--depth", "1", REPO, str(CLONE)], check=True)
    return CLONE


def collect(taxonomy: Taxonomy, *, offline: bool = False, limit: int | None = None):
    root = sync(offline=offline)
    count = 0
    for path in sorted(root.rglob("*.sls")):
        rel = path.relative_to(root)
        groups = [DIR_TO_GROUP[p] for p in rel.parts if p in DIR_TO_GROUP]
        text = path.read_text(encoding="utf-8", errors="replace")

        for match in _PKG_BLOCK.finditer(text):
            if limit and count >= limit:
                return
            name = match.group("name").split("/")[-1]
            body = match.group("body")
            if name.startswith(("include", "remnux", "{%")):
                continue

            builder = None
            for state, hint in BUILDER_BY_STATE.items():
                if state in body:
                    builder = hint
                    break
            else:
                continue  # not a package-installing block

            source = _SOURCE.search(body)
            identity = normalise(source.group(0) if source else None, fallback=name)
            tool = Tool(
                id=slugify(name),
                upstream=identity.url,
                categories=taxonomy.resolve(groups, default="malware-analysis"),
                tier=3,
                builder=builder,
                provenance={"remnux": name},
            )
            count += 1
            yield tool, (
                None if not identity.is_synthetic
                else f"{name} ({rel}): no source URL in state, needs manual upstream"
            )
