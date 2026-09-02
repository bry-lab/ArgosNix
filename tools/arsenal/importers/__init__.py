"""Provenance importers. One module per upstream distribution.

Every importer is a generator of (Tool | None, warning | None) pairs. It must be
safe to re-run: `Catalog.upsert` guarantees hand-curated fields survive, and
importers only ever fill blanks and extend provenance.

Run order matters. blackarch -> kali -> remnux -> athena, because that is
descending order of metadata quality, and the first importer to supply a field
wins it.
"""

from . import athena, blackarch, kali, remnux  # noqa: F401

ALL = {
    "blackarch": blackarch,
    "kali": kali,
    "remnux": remnux,
    "athena": athena,
}
