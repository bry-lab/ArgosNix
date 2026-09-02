"""Athena OS importer.

Athena re-exports most of BlackArch, so run this last: it should mostly produce
merges that add an `athena` provenance entry to tools you already have, plus a
small set of Athena-specific packages. If your add-rate here is high, the
BlackArch import probably failed.

Athena publishes a pacman repository; parsing the repo database is far more
stable than scraping their package tree, because the .db format has not changed
in fifteen years.
"""

from __future__ import annotations

import io
import tarfile

from ..catalog import Tool
from ..http import get
from ..identity import normalise, slugify
from ..taxonomy import Taxonomy

# VERIFY BEFORE FIRST RUN: Athena has moved its repo host before. Check
# /etc/pacman.conf on a current Athena install if this 404s.
DB_URL = "https://repo.athenaos.org/x86_64/athena.db.tar.gz"


def parse_desc(text: str) -> dict[str, list[str]]:
    """A pacman `desc` entry: %FIELD%\\nvalue\\n\\n%FIELD%\\n..."""
    fields: dict[str, list[str]] = {}
    key = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("%") and line.endswith("%"):
            key = line.strip("%")
            fields[key] = []
        elif line and key:
            fields[key].append(line)
    return fields


def collect(taxonomy: Taxonomy, *, limit: int | None = None):
    blob = get(DB_URL)
    count = 0
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        for member in tar:
            if not member.name.endswith("/desc"):
                continue
            if limit and count >= limit:
                return
            handle = tar.extractfile(member)
            if handle is None:
                continue
            fields = parse_desc(handle.read().decode("utf-8", errors="replace"))
            name = (fields.get("NAME") or [member.name.split("/")[0]])[0]
            url = (fields.get("URL") or [None])[0]
            groups = fields.get("GROUPS") or []
            desc = (fields.get("DESC") or [None])[0]
            licenses = fields.get("LICENSE") or []

            identity = normalise(url, fallback=name)
            count += 1
            yield Tool(
                id=slugify(name),
                upstream=identity.url,
                description=desc,
                license=(licenses[0] if licenses else None),
                categories=taxonomy.resolve(groups),
                tier=3,
                provenance={"athena": name},
            ), (None if not identity.is_synthetic else f"{name}: no URL in repo db")
