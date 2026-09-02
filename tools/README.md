# arsenal

Catalog tooling. Stdlib-only Python 3.11+, no install required:

```sh
cd tools && python3 -m arsenal.cli --help
# or, from the repo root:
nix develop .#dev   # puts `arsenal` on PATH
```

## Bootstrapping the catalog from scratch

Run in this order. The order matters: the first importer to supply a field wins
it, and metadata quality descends left to right.

```sh
arsenal import blackarch     # ~2,800 packages, best metadata, ~10 min
arsenal import kali          # ~600, cleanest taxonomy
arsenal import remnux        # ~700, mostly unique, worst metadata
arsenal import athena        # mostly merges into blackarch
arsenal validate
arsenal verify --promote     # resolve everything nixpkgs already has
arsenal coverage --write
```

Importers are idempotent. Re-running never clobbers hand-curated fields -- it
can only fill blanks and extend `provenance`. That invariant lives in
`Catalog.upsert` and there are tests for it; do not weaken it.

## Working the backlog

```sh
arsenal missing --tier 2 --category web   # what to package next, best-first
arsenal new mytool --upstream https://github.com/x/y --builder go
nix-init --url https://github.com/x/y     # fills in the hashes
```

`arsenal missing` sorts by how many source distros ship a tool. Something in
three distros is worth your afternoon; something in one is probably not.
