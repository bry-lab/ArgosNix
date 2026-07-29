# nix-arsenal

The tooling from Kali, BlackArch, REMnux and Athena OS — deduplicated into one
catalog, organised by what you are actually trying to do, and delivered as Nix
profiles you can install anywhere, pin per engagement, and rebuild byte-for-byte
in two years.

```sh
nix develop github:OWNER/nix-arsenal#osint      # or #webapp, #ad, #dfir, #malware…
nix profile install github:OWNER/nix-arsenal#network
nix build github:OWNER/nix-arsenal#iso          # a live system, not just a shell
```

## Why this exists

Four distributions, ~3,000 unique tools between them, and enormous overlap. If
you do OSINT and malware analysis you run two operating systems. If you want a
reproducible toolset for an engagement you are pinning a rolling release and
hoping. If you want to add three tools to Kali you are maintaining a Dockerfile.

Nix fixes all three problems, and the packaging was the only thing standing in
the way. So the catalog is the project. The flake is a thin generator over it.

## Status — read this before relying on it

This is honest about what it is. See [docs/COVERAGE.md](docs/COVERAGE.md), which
is regenerated nightly:

- Every tool in the catalog is mapped to its upstream and its source distros.
  **That mapping did not previously exist anywhere and is useful on its own.**
- Roughly a quarter of the union is already in nixpkgs and works today.
- The rest is a packaging backlog, tiered by difficulty and prioritised by how
  many distros ship it. `arsenal missing --tier 2` is the contributor queue.
- Some tools will never be here: Burp Pro, Cobalt Strike, Nessus and friends are
  licensed and not redistributable. They are catalogued as tier 4 with a note,
  so the coverage number stays honest.

**It does not fully replace Kali or REMnux today.** It replaces them for
specific profiles now and more of them each month, and unlike those distros you
can see exactly what is missing.

## How it is organised

```
catalog/          the source of truth: tools, taxonomy, profiles (TOML)
  tools/*.toml    one entry per tool, sharded by first letter
  taxonomy.toml   ~20 categories, ours, mapped from upstream groups
  profiles.toml   what a profile contains
nix/              reads the catalog, generates everything
pkgs/by-name/     derivations for tools nixpkgs lacks
modules/          NixOS + home-manager: capabilities, drivers, udev
images/           live ISO / VM / qcow definitions
tools/arsenal/    the CLI: importers, validation, coverage
templates/        per-engagement scaffold
```

**Nothing hand-lists packages in a `.nix` file.** Edit `catalog/`, and the
flake follows. If you find yourself editing a package list in Nix, the tooling
has failed and that is a bug.

### Categories vs profiles

Categories are how the catalog is organised (`web`, `active-directory`,
`malware-analysis`, …). Profiles are how you use it — `osint`, `webapp`, `ad`,
`redteam`, `dfir`, `malware`, `revuln`, `cloud`, `mobile`, `wireless`, `radio`,
`crypto`, `defense`, `ctf`, `full`. A profile composes categories, so OSINT and
web testing share their recon tooling instead of two lists drifting apart.

```sh
nix run .#arsenal -- profile              # every profile and its coverage
nix run .#arsenal -- profile ad --all     # what is in it, including gaps
```

## The capability problem

A devShell can put `nmap` on your PATH. It cannot give it `CAP_NET_RAW`, load a
monitor-mode driver, or write a udev rule for your Proxmark. That was always the
real value of a security distro, and a flake alone does not replace it.

So each catalog entry declares what privileges it needs, and the NixOS module
turns that into `security.wrappers`, driver selection and udev rules
automatically:

```nix
programs.arsenal = {
  enable = true;
  profiles = [ "network" "ad" "wireless" ];
  users = [ "you" ];
  hardware.wireless = true;
  hardware.sdr = true;
};
```

On macOS or non-NixOS Linux you get the binaries and not the capabilities. The
shell tells you which tools are affected rather than letting you find out
mid-engagement.

## Binary cache

**Do not use this without a cache.** Building a full profile from source takes
hours and tens of gigabytes. `cache.nixos.org` covers the tier-1 tools; our own
derivations come from `arsenal.cachix.org`:

```nix
nix.settings = {
  substituters = [ "https://arsenal.cachix.org" ];
  trusted-public-keys = [ "arsenal.cachix.org-1:REPLACE_ME" ];
};
```

Unfree packages are never pushed to the cache. You build those yourself, which
is the price of them being unfree.

## Per-engagement pinning

The reason to do any of this in Nix:

```sh
nix flake init -t github:OWNER/nix-arsenal#engagement
nix flake lock && nix flake archive     # pin, then fetch the whole closure
git add flake.lock && git commit
```

Six months later, when a finding is disputed, `nix develop` rebuilds the exact
toolchain that produced it — same nuclei templates, same sqlmap, same
everything, whether or not the upstream repos still exist.

## Contributing

The most valuable contribution is not code. It is packaging one tool from
`arsenal missing --tier 2` and, when it is broadly useful,
[sending it to nixpkgs](docs/UPSTREAMING.md) rather than here.

```sh
nix develop .#dev
arsenal missing --tier 2 --category web
arsenal new sometool --upstream https://github.com/x/y --builder go
nix-init --url https://github.com/x/y
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Scope and legality

These are dual-use tools. Everything here is packaging of software that is
already publicly available and shipped by four existing distributions; nothing
is a novel capability. Use it against systems you are authorised to test.
Licensed commercial software is catalogued but never redistributed.

## Licence

The repo is MIT. Every packaged tool keeps its own licence — see the `license`
field on each catalog entry.
