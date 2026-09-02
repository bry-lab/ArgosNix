# Roadmap

Phased so that each phase ships something useful on its own. If the project
stops after any phase, what exists is still worth having.

## Phase 0 — the catalog  (no packaging at all)

Importers, taxonomy, dedupe, coverage dashboard. Zero derivations written.

Deliverable: a machine-readable map of ~3,000 security tools across four
distributions, deduplicated by upstream, with a per-distro coverage number.
**This does not currently exist anywhere and is useful even at 0% packaged.**

It also tells you exactly how big the real job is before you commit to it.

## Phase 1 — profiles over what nixpkgs already has

Roughly a quarter of the catalog. `nix develop .#osint` works. NixOS module with
capability wrappers. Cache set up. This is a usable product for a meaningful
subset of people on day one.

Exit criterion: three profiles at >90% of their catalogued tools.

## Phase 2 — the tier-2 backlog

Batch Go/Rust/Python packaging with `nix-init`, automated hash-bump PRs, nightly
full build on a real builder. This is where the coverage number moves.

Exit criterion: Kali and REMnux coverage above 80%.

## Phase 3 — images and the long tail

Live ISO, VM images, tier-3 hand packaging, community PRs, detonation VM
tooling. This is the point at which "replaces Kali" stops being aspirational.

## Explicitly out of scope

- Tier 4. Licensed commercial tools are catalogued, never packaged.
- Chasing BlackArch's full long tail. Hundreds of its packages are abandoned,
  single-commit or duplicates. Coverage of *maintained* tools is the metric that
  matters, not raw count.
- A custom kernel. Use nixpkgs'.

## Scope decision worth making early

**Kali + REMnux only** is a ~1,300-tool union and achievable by a small team in
months. **All four** is ~3,000 and is a multi-year community project. The
architecture supports both — the difference is whether you run the BlackArch
importer — but the two imply very different commitments. Decide before Phase 2.
