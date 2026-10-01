# Argos

A catalog of security tools organized into categories and packed and delivered as Nix profiles you can install anywhere, all in one place

```sh
nix develop github:bry-lab/ArgosNix#osint      # or #webapp, #ad, #dfir, #malware…
nix profile install github:bry-lab/ArgosNix#network
nix build github:bry-lab/ArgosNix#iso          # a live system, not just a shell
```

## Why this exists

Security tooling is scattered across ecosystems, heavily duplicated, and hard to
reproduce. Covering two specialisms — say OSINT and malware analysis — usually
means running two operating systems. A reproducible toolset for an engagement
means pinning a rolling release and hoping. Adding a few tools of your own means
maintaining a Dockerfile.

Nix fixes all three problems, and the packaging was the only thing standing in
the way. So the catalog is the project. The flake is a thin generator over it.

## Status — read this before relying on it

This is honest about what it is. See [docs/COVERAGE.md](docs/COVERAGE.md), which
is regenerated nightly:

- Every tool in the catalog is mapped to its upstream and deduplicated by where
  the code lives. **That mapping is useful on its own.**
- Roughly a quarter of the catalog is already in nixpkgs and works today.
- The rest is a packaging backlog, tiered by difficulty. `argos missing --tier 2`
  is the contributor queue.
- Some tools will never be here: Burp Pro, Cobalt Strike, Nessus and friends are
  licensed and not redistributable. They are catalogued as tier 4 with a note,
  so the coverage number stays honest.

**It is not complete today.** It is production-ready for specific profiles now
and more of them each month, and you can always see exactly what is missing.

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
tools/argos/      the CLI: importers, validation, coverage
templates/        per-engagement scaffold
examples/         a ready-to-copy NixOS configuration.nix
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
nix run .#argos -- profile              # every profile and its coverage
nix run .#argos -- profile ad --all     # what is in it, including gaps
```

## Using it: load and offload a package set

A "package set" is a profile. Loading one means putting its tools on your `PATH`;
offloading means taking them back off. Nothing is ever installed globally unless
you ask for it.

```sh
# Peek before you load — what is in a set, and what (if anything) is missing:
nix run github:bry-lab/ArgosNix#argos -- profile dfir --all

# Load into a throwaway shell. Nothing touches your system; the tools are on
# PATH only inside this shell:
nix develop github:bry-lab/ArgosNix#dfir
#   ...work with the forensics tools...
exit                     # offload — your PATH is clean again, system untouched
```

Rule of thumb: use the throwaway shell for a session, and `nix profile` (below)
when you want tools to stick around. Replace the `github:bry-lab/ArgosNix` prefix
with `.` when you are inside a local clone (`nix develop .#dfir`).

### Keeping tools around: `nix profile` as a package manager

If you want tools installed the way a normal package manager installs them —
present across shells and reboots until you remove them — use `nix profile`. It
takes Argos profiles and plain nixpkgs packages side by side:

```sh
# install (load) — stays until you remove it
nix profile install github:bry-lab/ArgosNix#revuln
nix profile install nixpkgs#nmap nixpkgs#gdb nixpkgs#ghidra

# whole Argos sets stack and de-duplicate against each other
nix profile install github:bry-lab/ArgosNix#osint github:bry-lab/ArgosNix#webapp

nix profile list             # see what's installed
nix profile remove ghidra    # remove (offload) one, by name from the list
nix profile upgrade --all    # update everything to the latest
nix profile rollback         # undo the last change if something breaks
```

One catch: removing a tool does not free disk space immediately. Nix keeps a
history of old profile versions — that is what makes `rollback` work — and the
store's automatic cleanup will not touch anything still referenced by that
history. To actually reclaim the space:

```sh
nix profile wipe-history --older-than 7d   # drop old profile generations
nix store gc                               # then collect the now-unused paths
```

## Nix hosts and non-Nix hosts

Every command in this README is the same on every machine. The only variable is
whether Nix — and NixOS — is already there. Nothing here uses your system package
manager, and nothing needs root beyond installing Nix itself.

| Your host | What you do | What you get |
| --- | --- | --- |
| **NixOS** | The module (below), or the same `nix develop` / `profile` commands | Everything, including capabilities: `security.wrappers`, drivers, udev |
| **Any other Linux with Nix** | The exact commands above | Binaries + reproducibility; capabilities degrade to `sudo`/`setcap` |
| **Any Linux without Nix** | Install Nix once (below), then you *are* a Nix host | Same as the row above — identical commands, identical results |

So a laptop running Ubuntu, Debian, Fedora, Arch (or WSL) uses Argos exactly the
way a native NixOS box does — install Nix, then run the same lines. You do not
convert your machine to NixOS and you do not install tools into your OS.

```sh
# Turn a non-Nix Linux host into a Nix host (pick one):

# Determinate Systems installer — recommended, enables flakes out of the box:
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install

# ...or the official installer, then enable flakes yourself:
sh <(curl -L https://nixos.org/nix/install) --daemon
mkdir -p ~/.config/nix
echo 'experimental-features = nix-command flakes' >> ~/.config/nix/nix.conf
```

Open a new shell after installing, and `nix develop github:bry-lab/ArgosNix#osint`
behaves the same on Ubuntu as it does on NixOS.

On NixOS you additionally get the module, which is the one thing a plain
`nix develop` cannot do — see below.

## The capability problem

A devShell can put `nmap` on your PATH. It cannot give it `CAP_NET_RAW`, load a
monitor-mode driver, or write a udev rule for your Proxmark. That was always the
real value of a security distro, and a flake alone does not replace it.

So each catalog entry declares what privileges it needs, and the NixOS module
turns that into `security.wrappers`, driver selection and udev rules
automatically:

```nix
programs.argos = {
  enable = true;
  profiles = [ "network" "ad" "wireless" ];
  users = [ "you" ];
  hardware.wireless = true;
  hardware.sdr = true;
};
```

On non-NixOS Linux you get the binaries and not the capabilities. The shell
tells you which tools are affected rather than letting you find out
mid-engagement.

A complete, copy-ready base system that wires this up — Nix settings, automatic
garbage collection, VM guest niceties and the `programs.argos` block above —
lives in [examples/configuration.nix](examples/configuration.nix).

## Binary cache

A binary cache is strongly recommended before building large profiles from
source — that can take hours and tens of gigabytes. The good news is that
`cache.nixos.org` already covers the tier-1 tools (most of the catalog), so many
profiles need no extra setup at all.

Argos's own derivations — the tools nixpkgs lacks — are not yet served from a
public cache. When you have one, point at it like this (substitute your real URL
and key):

```nix
nix.settings = {
  substituters = [ "https://cache.nixos.org" "https://YOUR-CACHE.cachix.org" ];
  trusted-public-keys = [ "YOUR-CACHE.cachix.org-1:YOUR-PUBLIC-KEY" ];
};
```

Unfree packages are never pushed to a cache. You build those yourself, which is
the price of them being unfree.

## Per-engagement pinning

The reason to do any of this in Nix:

```sh
nix flake init -t github:bry-lab/ArgosNix#engagement
nix flake lock && nix flake archive     # pin, then fetch the whole closure
git add flake.lock && git commit
```

Six months later, when a finding is disputed, `nix develop` rebuilds the exact
toolchain that produced it — same nuclei templates, same sqlmap, same
everything, whether or not the upstream repos still exist.

## Contributing

The most valuable contribution is not code. It is packaging one tool from
`argos missing --tier 2` and, when it is broadly useful,
[sending it to nixpkgs](docs/UPSTREAMING.md) rather than here.

```sh
nix develop .#dev
argos missing --tier 2 --category web
argos new sometool --upstream https://github.com/x/y --builder go
nix-init --url https://github.com/x/y
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Scope and legality

These are dual-use tools. Everything here is packaging of software that is
already publicly available; nothing is a novel capability. Use it against
systems you are authorised to test. Licensed commercial software is catalogued
but never redistributed.

## Licence

The repo is MIT. Every packaged tool keeps its own licence — see the `license`
field on each catalog entry.
